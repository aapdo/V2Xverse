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
SSH_STREAM_OPTS=(-o ConnectTimeout=10)

MIN_FREE_MIB="${V2X_MIN_FREE_MEM_MIB:-20000}"
MAX_USED_MIB="${V2X_MAX_USED_MEM_MIB:-${V2X_FREE_MEM_LIMIT_MIB:-0}}"
UTIL_LIMIT_PCT="${V2X_FREE_UTIL_LIMIT_PCT:-20}"
POLL_SECONDS="${V2X_GPU_POLL_SECONDS:-300}"
MAX_GPUS="${V2X_MAX_GPUS:-2}"
BATCHES="${V2X_CPS_OFFLOAD_BATCHES:-0}"
JOBS_PER_GPU="${V2X_CPS_OFFLOAD_JOBS_PER_GPU:-1}"
MAX_JOBS_PER_BATCH="${V2X_CPS_OFFLOAD_MAX_JOBS_PER_BATCH:-0}"
CPS_OFFLOAD_PREFIX="${V2X_CPS_OFFLOAD_PREFIX:-phase1_full_cps_offload}"
ONE_BATCH_PER_GPU="${V2X_CPS_OFFLOAD_ONE_BATCH_PER_GPU:-1}"

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
        if (index(active, "," $1 ",") == 0 && ($3 + 0) >= (min_free + 0) && ((max_used + 0) <= 0 || ($2 + 0) <= (max_used + 0)) && ($4 + 0) <= (util + 0)) {
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

cps_queue_has_active_claims() {
  ssh "${SSH_OPTS[@]}" "$FARM_HOST" \
    "awk -F, 'NR > 1 && \$3 == \"cps\" && (\$2 == \"offloaded\" || \$2 == \"running\") {found=1} END {exit found ? 0 : 1}' '$QUEUE_ROOT/shared_queue_status.csv'" \
    >/dev/null 2>&1
}

batch_stamp() {
  local gpus="${1//,/_}"
  printf '%s_%s_g%s' "$(date +%Y%m%d_%H%M%S)" "$$" "$gpus"
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

release_missing_cps_status_rows() {
  local batch="$1"
  local cps_out="$2"
  local local_status="$3"
  local farm_claimed="$LOCAL_TMP/claimed_cps_offload_$batch.ids"
  local status_ids="$LOCAL_TMP/status_cps_offload_$batch.ids"
  local missing_ids="$LOCAL_TMP/missing_cps_offload_$batch.ids"

  ssh "${SSH_OPTS[@]}" "$FARM_HOST" "awk -F, 'NR > 1 && \$3 == \"cps\" && (\$2 == \"offloaded\" || \$2 == \"running\") && \$8 == \"$cps_out\" {print \$1}' '$QUEUE_ROOT/shared_queue_status.csv'" > "$farm_claimed"
  if [ ! -s "$farm_claimed" ]; then
    return
  fi

  awk -F, 'NR > 1 && $1 != "" {print $1}' "$local_status" | sort -u > "$status_ids"
  sort -u "$farm_claimed" | comm -23 - "$status_ids" > "$missing_ids"
  if [ ! -s "$missing_ids" ]; then
    return
  fi

  if cps_batch_active "$batch"; then
    log "CPS recovery batch=$batch has status-missing rows but batch is still active; not releasing"
    return
  fi

  log "CPS recovery batch=$batch releasing rows missing from inactive launcher_status"
  release_batch "$missing_ids"
}

copy_cps_results_to_farm() {
  local batch="$1"
  local cps_out="$2"
  local local_status="$3"
  local ids_file="$LOCAL_TMP/copy_cps_results_$batch.ids"
  local ids

  awk -F, 'NR > 1 && ($3 == "done" || $3 == "failed") && $1 != "" {print $1}' "$local_status" > "$ids_file"
  if [ ! -s "$ids_file" ]; then
    return
  fi

  ids="$(paste -sd' ' "$ids_file")"
  log "CPS recovery batch=$batch copying result dirs to FARM: $ids"
  ssh "${SSH_OPTS[@]}" "$CPS_HOST" "cd '$cps_out' && tar -czf - --ignore-failed-read $ids" \
    | ssh "${SSH_STREAM_OPTS[@]}" "$FARM_HOST" "mkdir -p '$QUEUE_ROOT' && tar -xzf - -C '$QUEUE_ROOT'"
}

recover_cps_batches() {
  local batches cps_out batch local_status farm_status has_running has_finished
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
    if ! scp "$CPS_HOST:$cps_out/launcher_status.csv" "$local_status" >/dev/null; then
      log "CPS recovery batch=$batch status=copy_failed"
      continue
    fi

    has_running=0
    has_finished=0
    if grep -q ',running,' "$local_status"; then
      has_running=1
    fi
    if grep -Eq ',(done|failed),' "$local_status"; then
      has_finished=1
    fi

    if [ "$has_running" -eq 0 ] && [ "$has_finished" -eq 0 ]; then
      if cps_batch_active "$batch"; then
        log "CPS recovery batch=$batch status=empty active=1"
      else
        log "CPS recovery batch=$batch status=empty active=0"
        release_cps_out "$batch" "$cps_out"
      fi
      continue
    fi

    if [ "$has_finished" -eq 1 ]; then
      copy_cps_results_to_farm "$batch" "$cps_out" "$local_status"
    fi
    scp "$local_status" "$FARM_HOST:$farm_status" >/dev/null
    ssh "${SSH_OPTS[@]}" "$FARM_HOST" "cd '$FARM_ROOT' && $FARM_PYTHON experiments/v2xverse_codriving_diag/offload_shared_jobs.py merge --queue-root '$QUEUE_ROOT' --launcher-status '$farm_status' --host-id cps"
    release_missing_cps_status_rows "$batch" "$cps_out" "$local_status"
    if [ "$has_running" -eq 1 ]; then
      log "CPS recovery batch=$batch merged_partial status=running"
    else
      log "CPS recovery batch=$batch merged"
    fi
  done <<< "$batches"
}

launch_cps_batch() {
  local batch_gpus="$1"
  local gpu_count="$2"
  local claim_count batch farm_jobs cps_jobs cps_out local_jobs local_ids
  local claim_output claimed

  claim_count="$(claim_count_for_gpus "$gpu_count")"
  batch="$(batch_stamp "$batch_gpus")"
  farm_jobs="$FARM_ROOT/experiments/v2xverse_codriving_diag/results/jobs_${CPS_OFFLOAD_PREFIX}_$batch.tsv"
  cps_jobs="$CPS_ROOT/experiments/v2xverse_codriving_diag/jobs_${CPS_OFFLOAD_PREFIX}_$batch.tsv"
  cps_out="$CPS_RESULTS_ROOT/${CPS_OFFLOAD_PREFIX}_$batch"
  local_jobs="$LOCAL_TMP/jobs_${CPS_OFFLOAD_PREFIX}_$batch.tsv"
  local_ids="$LOCAL_TMP/jobs_${CPS_OFFLOAD_PREFIX}_$batch.ids"

  log "claiming CPS offload batch=$batch gpus=$batch_gpus gpu_count=$gpu_count claim_count=$claim_count jobs_per_gpu=$JOBS_PER_GPU"
  if ! claim_output="$(ssh "${SSH_OPTS[@]}" "$FARM_HOST" "cd '$FARM_ROOT' && $FARM_PYTHON experiments/v2xverse_codriving_diag/offload_shared_jobs.py claim --queue-root '$QUEUE_ROOT' --jobs '$JOBS_FILE' --count '$claim_count' --out-jobs '$farm_jobs' --host-id cps --remote-out-root '$cps_out'")"; then
    log "failed to claim CPS offload batch=$batch"
    return 1
  fi
  log "$claim_output"
  claimed="$(awk -F'[ =]' '/claimed=/{print $2}' <<< "$claim_output" | tail -1)"
  if [ "${claimed:-0}" -eq 0 ]; then
    log "no pending jobs available for CPS offload"
    return 2
  fi

  if ! scp "$FARM_HOST:$farm_jobs" "$local_jobs" >/dev/null; then
    log "failed to fetch claimed CPS job TSV for batch=$batch; releasing claimed rows"
    release_cps_out "$batch" "$cps_out"
    return 1
  fi
  awk 'NR > 1 {print $1}' "$local_jobs" > "$local_ids"
  if ! scp "$local_jobs" "$CPS_HOST:$cps_jobs" >/dev/null; then
    log "failed to copy CPS job TSV for batch=$batch; releasing claimed rows"
    release_batch "$local_ids"
    return 1
  fi

  log "launching CPS offload batch=$batch on GPUs=$batch_gpus"
  if ! ssh "${SSH_OPTS[@]}" "$CPS_HOST" "cd '$CPS_ROOT' || exit 1; mkdir -p '$CPS_RESULTS_ROOT' || exit 1; JOB_FILE='$cps_jobs' OUT_ROOT='$cps_out' V2X_GPU_LIST='$batch_gpus' nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase1_full_cps.sh > '$CPS_RESULTS_ROOT/${CPS_OFFLOAD_PREFIX}_$batch.log' 2>&1 < /dev/null & echo \$! > '$CPS_RESULTS_ROOT/${CPS_OFFLOAD_PREFIX}_$batch.pid'"; then
    log "failed to launch CPS offload batch=$batch; releasing claimed rows"
    release_batch "$local_ids"
    return 1
  fi
  launched_batches=$((launched_batches + 1))
  log "launched CPS offload batch=$batch launched_batches=$launched_batches"
  return 0
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

  no_pending=0
  if [ "$ONE_BATCH_PER_GPU" = "1" ]; then
    IFS=',' read -r -a gpu_items <<< "$GPUS"
    for gpu in "${gpu_items[@]}"; do
      [ -n "$gpu" ] || continue
      if launch_cps_batch "$gpu" 1; then
        :
      else
        rc=$?
        if [ "$rc" -eq 2 ]; then
          no_pending=1
          break
        fi
      fi
      if [ "$BATCHES" != "0" ] && [ "$launched_batches" -ge "$BATCHES" ]; then
        log "launched requested CPS offload batches=$launched_batches"
        exit 0
      fi
    done
  else
    if launch_cps_batch "$GPUS" "$GPU_COUNT"; then
      :
    else
      rc=$?
      if [ "$rc" -eq 2 ]; then
        no_pending=1
      fi
    fi
  fi

  if [ "$no_pending" -eq 1 ]; then
    if cps_queue_has_active_claims; then
      log "no pending jobs remain, but CPS claims are still active; continuing recovery loop"
      sleep "$POLL_SECONDS"
      continue
    fi
    log "no pending jobs remain and no active CPS claims"
    exit 0
  fi

  sleep "$POLL_SECONDS"
done
