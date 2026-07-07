#!/usr/bin/env bash
set -euo pipefail

# Run this on a controller host that can SSH to both FARM and CPS.
# It waits for free CPS GPUs, claims pending jobs from the FARM shared queue,
# launches those jobs on CPS, then recovers/merges finished CPS batches.

FARM_HOST="${FARM_HOST:-FARM9}"
CPS_HOST="${CPS_HOST:-cps_workstation}"
FARM_ROOT="${FARM_ROOT:-/home/jy/adas/external/V2Xverse}"
CPS_ROOT="${CPS_ROOT:-/data/adas/e2e/external/V2Xverse}"
QUEUE_ROOT="${QUEUE_ROOT:?set QUEUE_ROOT to the active FARM shared queue root}"
JOBS_FILE="${JOBS_FILE:-experiments/v2xverse_codriving_diag/jobs_phase1_full_farm_shared.tsv}"
FARM_PYTHON="${FARM_PYTHON:-python3}"
CPS_RESULTS_ROOT="${CPS_RESULTS_ROOT:-/data/adas/e2e/experiments/v2xverse_codriving_diag/results}"
LOCAL_TMP="${LOCAL_TMP:-/tmp/v2xverse_cps_offload}"
SSH_OPTS=(-n -o ConnectTimeout=10)

MIN_FREE_MIB="${V2X_MIN_FREE_MEM_MIB:-20000}"
MAX_USED_MIB="${V2X_MAX_USED_MEM_MIB:-${V2X_FREE_MEM_LIMIT_MIB:-0}}"
UTIL_LIMIT_PCT="${V2X_FREE_UTIL_LIMIT_PCT:-20}"
POLL_SECONDS="${V2X_GPU_POLL_SECONDS:-300}"
MAX_GPUS="${V2X_MAX_GPUS:-2}"
BATCHES="${V2X_CPS_OFFLOAD_BATCHES:-0}"
JOBS_PER_GPU="${V2X_CPS_OFFLOAD_JOBS_PER_GPU:-2}"
MAX_JOBS_PER_BATCH="${V2X_CPS_OFFLOAD_MAX_JOBS_PER_BATCH:-0}"
CPS_OFFLOAD_PREFIX="${V2X_CPS_OFFLOAD_PREFIX:-phase1_full_cps_offload}"

mkdir -p "$LOCAL_TMP"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*"
}

memory_rule() {
  if [ "${MAX_USED_MIB:-0}" != "0" ]; then
    printf 'free>=%sMiB used<=%sMiB' "$MIN_FREE_MIB" "$MAX_USED_MIB"
  else
    printf 'free>=%sMiB' "$MIN_FREE_MIB"
  fi
}

active_cps_offload_gpus() {
  ssh "${SSH_OPTS[@]}" "$CPS_HOST" \
    "pgrep -af 'launch_local_queue.py .*$CPS_OFFLOAD_PREFIX' | awk '{for (i=1; i<=NF; i++) { if (\$i == \"--gpus\") { n=split(\$(i+1), g, \",\"); for (j=1; j<=n; j++) print g[j]; } }}' | sort -u | paste -sd, -" \
    || true
}

select_free_gpus() {
  local active_gpus active_lookup
  active_gpus="$(active_cps_offload_gpus)"
  active_lookup=",$active_gpus,"
  ssh "${SSH_OPTS[@]}" "$CPS_HOST" \
    "nvidia-smi --query-gpu=index,memory.used,memory.free,utilization.gpu --format=csv,noheader,nounits" \
    | awk -F, -v min_free="$MIN_FREE_MIB" -v max_used="$MAX_USED_MIB" -v util="$UTIL_LIMIT_PCT" -v max="$MAX_GPUS" -v active="$active_lookup" '
      {
        gsub(/ /, "", $1); gsub(/ /, "", $2); gsub(/ /, "", $3); gsub(/ /, "", $4);
        if (index(active, "," $1 ",") == 0 && $3 >= min_free && (max_used <= 0 || $2 <= max_used) && $4 <= util) {
          if (count > 0) {
            printf(",");
          }
          printf("%s", $1);
          count++;
          if (count >= max) {
            exit;
          }
        }
      }
    '
}

count_gpus() {
  if [ -z "$1" ]; then
    echo 0
  else
    awk -F, '{print NF}' <<< "$1"
  fi
}

claim_count_for_gpus() {
  local gpu_count="$1"
  local count=$((gpu_count * JOBS_PER_GPU))
  if [ "$count" -lt "$gpu_count" ]; then
    count="$gpu_count"
  fi
  if [ "$MAX_JOBS_PER_BATCH" != "0" ] && [ "$count" -gt "$MAX_JOBS_PER_BATCH" ]; then
    count="$MAX_JOBS_PER_BATCH"
  fi
  echo "$count"
}

release_batch() {
  local ids_file="$1"
  local remote_ids="/tmp/$(basename "$ids_file")"
  scp "$ids_file" "$FARM_HOST:$remote_ids" >/dev/null
  ssh "${SSH_OPTS[@]}" "$FARM_HOST" "cd '$FARM_ROOT' && $FARM_PYTHON experiments/v2xverse_codriving_diag/offload_shared_jobs.py release --queue-root '$QUEUE_ROOT' --host-id cps --status offloaded --status running --run-id-file '$remote_ids'"
}

cps_batch_active() {
  local batch="$1"
  ssh "${SSH_OPTS[@]}" "$CPS_HOST" "pgrep -af '${CPS_OFFLOAD_PREFIX}_$batch' | grep -E 'launch_phase1_full_cps.sh|launch_local_queue.py|run_planner_diag.py' >/dev/null"
}

release_cps_out() {
  local batch="$1"
  local cps_out="$2"
  local ids_file="$LOCAL_TMP/release_cps_offload_$batch.ids"

  ssh "${SSH_OPTS[@]}" "$FARM_HOST" "awk -F, 'NR > 1 && \$3 == \"cps\" && (\$2 == \"offloaded\" || \$2 == \"running\") && \$8 == \"$cps_out\" {print \$1}' '$QUEUE_ROOT/shared_queue_status.csv'" > "$ids_file"
  if [ ! -s "$ids_file" ]; then
    log "CPS recovery batch=$batch release skipped: no matching FARM rows"
    return
  fi
  log "CPS recovery batch=$batch releasing claimed rows"
  release_batch "$ids_file"
}

recover_cps_batches() {
  local batches cps_out batch local_status farm_status
  batches="$(ssh "${SSH_OPTS[@]}" "$FARM_HOST" "awk -F, 'NR > 1 && \$3 == \"cps\" && (\$2 == \"offloaded\" || \$2 == \"running\") && index(\$8, \"$CPS_OFFLOAD_PREFIX\") > 0 {print \$8}' '$QUEUE_ROOT/shared_queue_status.csv' | sort -u" || true)"
  if [ -z "$batches" ]; then
    return
  fi

  while IFS= read -r cps_out; do
    [ -n "$cps_out" ] || continue
    batch="$(basename "$cps_out" | sed "s/^${CPS_OFFLOAD_PREFIX}_//")"
    local_status="$LOCAL_TMP/launcher_status_cps_offload_$batch.csv"
    farm_status="/tmp/launcher_status_cps_offload_$batch.csv"

    if ! ssh "${SSH_OPTS[@]}" "$CPS_HOST" "[ -f '$cps_out/launcher_status.csv' ]"; then
      if cps_batch_active "$batch"; then
        log "CPS recovery batch=$batch status=missing_status active=1"
      else
        log "CPS recovery batch=$batch status=missing_status active=0"
        release_cps_out "$batch" "$cps_out"
      fi
      continue
    fi
    if ssh "${SSH_OPTS[@]}" "$CPS_HOST" "grep -q ',running,' '$cps_out/launcher_status.csv'"; then
      log "CPS recovery batch=$batch status=running"
      continue
    fi
    if ! ssh "${SSH_OPTS[@]}" "$CPS_HOST" "grep -Eq ',(done|failed),' '$cps_out/launcher_status.csv'"; then
      if cps_batch_active "$batch"; then
        log "CPS recovery batch=$batch status=empty active=1"
      else
        log "CPS recovery batch=$batch status=empty active=0"
        release_cps_out "$batch" "$cps_out"
      fi
      continue
    fi

    scp "$CPS_HOST:$cps_out/launcher_status.csv" "$local_status" >/dev/null
    scp "$local_status" "$FARM_HOST:$farm_status" >/dev/null
    ssh "${SSH_OPTS[@]}" "$FARM_HOST" "cd '$FARM_ROOT' && $FARM_PYTHON experiments/v2xverse_codriving_diag/offload_shared_jobs.py merge --queue-root '$QUEUE_ROOT' --launcher-status '$farm_status' --host-id cps"
    log "CPS recovery batch=$batch merged"
  done <<< "$batches"
}

launched_batches=0
while true; do
  if [ "$BATCHES" != "0" ] && [ "$launched_batches" -ge "$BATCHES" ]; then
    log "launched requested CPS offload batches=$launched_batches"
    exit 0
  fi

  recover_cps_batches

  GPUS="$(select_free_gpus || true)"
  GPU_COUNT="$(count_gpus "$GPUS")"
  if [ "$GPU_COUNT" -eq 0 ]; then
    log "CPS offload waiting: free_gpus=none $(memory_rule) util<=${UTIL_LIMIT_PCT}%"
    sleep "$POLL_SECONDS"
    continue
  fi
  CLAIM_COUNT="$(claim_count_for_gpus "$GPU_COUNT")"

  BATCH="$(date +%Y%m%d_%H%M%S)"
  FARM_JOBS="$FARM_ROOT/experiments/v2xverse_codriving_diag/results/jobs_${CPS_OFFLOAD_PREFIX}_$BATCH.tsv"
  CPS_JOBS="$CPS_ROOT/experiments/v2xverse_codriving_diag/jobs_${CPS_OFFLOAD_PREFIX}_$BATCH.tsv"
  CPS_OUT="$CPS_RESULTS_ROOT/${CPS_OFFLOAD_PREFIX}_$BATCH"
  LOCAL_JOBS="$LOCAL_TMP/jobs_${CPS_OFFLOAD_PREFIX}_$BATCH.tsv"
  LOCAL_IDS="$LOCAL_TMP/jobs_${CPS_OFFLOAD_PREFIX}_$BATCH.ids"
  LOCAL_STATUS="$LOCAL_TMP/launcher_status_${CPS_OFFLOAD_PREFIX}_$BATCH.csv"
  FARM_STATUS="/tmp/launcher_status_cps_offload_$BATCH.csv"

  log "claiming CPS offload batch=$BATCH gpus=$GPUS gpu_count=$GPU_COUNT claim_count=$CLAIM_COUNT jobs_per_gpu=$JOBS_PER_GPU"
  CLAIM_OUTPUT="$(ssh "${SSH_OPTS[@]}" "$FARM_HOST" "cd '$FARM_ROOT' && $FARM_PYTHON experiments/v2xverse_codriving_diag/offload_shared_jobs.py claim --queue-root '$QUEUE_ROOT' --jobs '$JOBS_FILE' --count '$CLAIM_COUNT' --out-jobs '$FARM_JOBS' --host-id cps --remote-out-root '$CPS_OUT'")"
  log "$CLAIM_OUTPUT"
  CLAIMED="$(awk -F'[ =]' '/claimed=/{print $2}' <<< "$CLAIM_OUTPUT" | tail -1)"
  if [ "${CLAIMED:-0}" -eq 0 ]; then
    log "no pending jobs available for CPS offload"
    exit 0
  fi

  scp "$FARM_HOST:$FARM_JOBS" "$LOCAL_JOBS" >/dev/null
  awk 'NR > 1 {print $1}' "$LOCAL_JOBS" > "$LOCAL_IDS"
  scp "$LOCAL_JOBS" "$CPS_HOST:$CPS_JOBS" >/dev/null

  log "launching CPS offload batch=$BATCH on GPUs=$GPUS"
  if ! ssh "${SSH_OPTS[@]}" "$CPS_HOST" "cd '$CPS_ROOT' && mkdir -p '$CPS_RESULTS_ROOT' && JOB_FILE='$CPS_JOBS' OUT_ROOT='$CPS_OUT' V2X_GPU_LIST='$GPUS' nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase1_full_cps.sh > '$CPS_RESULTS_ROOT/${CPS_OFFLOAD_PREFIX}_$BATCH.log' 2>&1 & echo \$! > '$CPS_RESULTS_ROOT/${CPS_OFFLOAD_PREFIX}_$BATCH.pid'"; then
    log "failed to launch CPS offload batch=$BATCH; releasing claimed rows"
    release_batch "$LOCAL_IDS"
    sleep "$POLL_SECONDS"
    continue
  fi
  launched_batches=$((launched_batches + 1))
  log "launched CPS offload batch=$BATCH launched_batches=$launched_batches"
  sleep "$POLL_SECONDS"
done
