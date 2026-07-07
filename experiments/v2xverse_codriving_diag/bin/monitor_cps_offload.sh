#!/usr/bin/env bash
set -euo pipefail

# Run this on a controller host that can SSH to both FARM and CPS.
# It waits for free CPS GPUs, claims pending jobs from the FARM shared queue,
# runs those jobs on CPS, then merges CPS launcher_status.csv back to FARM.

FARM_HOST="${FARM_HOST:-FARM9}"
CPS_HOST="${CPS_HOST:-cps_workstation}"
FARM_ROOT="${FARM_ROOT:-/home/jy/adas/external/V2Xverse}"
CPS_ROOT="${CPS_ROOT:-/data/adas/e2e/external/V2Xverse}"
QUEUE_ROOT="${QUEUE_ROOT:?set QUEUE_ROOT to the active FARM shared queue root}"
FARM_PYTHON="${FARM_PYTHON:-python3}"
CPS_RESULTS_ROOT="${CPS_RESULTS_ROOT:-/data/adas/e2e/experiments/v2xverse_codriving_diag/results}"
LOCAL_TMP="${LOCAL_TMP:-/tmp/v2xverse_cps_offload}"

MIN_FREE_MIB="${V2X_MIN_FREE_MEM_MIB:-20000}"
MAX_USED_MIB="${V2X_MAX_USED_MEM_MIB:-${V2X_FREE_MEM_LIMIT_MIB:-0}}"
UTIL_LIMIT_PCT="${V2X_FREE_UTIL_LIMIT_PCT:-20}"
POLL_SECONDS="${V2X_GPU_POLL_SECONDS:-300}"
MAX_GPUS="${V2X_MAX_GPUS:-2}"
BATCHES="${V2X_CPS_OFFLOAD_BATCHES:-0}"
JOBS_PER_GPU="${V2X_CPS_OFFLOAD_JOBS_PER_GPU:-2}"
MAX_JOBS_PER_BATCH="${V2X_CPS_OFFLOAD_MAX_JOBS_PER_BATCH:-0}"

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

select_free_gpus() {
  ssh -o ConnectTimeout=10 "$CPS_HOST" \
    "nvidia-smi --query-gpu=index,memory.used,memory.free,utilization.gpu --format=csv,noheader,nounits" \
    | awk -F, -v min_free="$MIN_FREE_MIB" -v max_used="$MAX_USED_MIB" -v util="$UTIL_LIMIT_PCT" -v max="$MAX_GPUS" '
      {
        gsub(/ /, "", $1); gsub(/ /, "", $2); gsub(/ /, "", $3); gsub(/ /, "", $4);
        if ($3 >= min_free && (max_used <= 0 || $2 <= max_used) && $4 <= util) {
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
  ssh "$FARM_HOST" "cd '$FARM_ROOT' && $FARM_PYTHON experiments/v2xverse_codriving_diag/offload_shared_jobs.py release --queue-root '$QUEUE_ROOT' --host-id cps --run-id-file '$remote_ids'"
}

completed_batches=0
while true; do
  if [ "$BATCHES" != "0" ] && [ "$completed_batches" -ge "$BATCHES" ]; then
    log "completed requested CPS offload batches=$completed_batches"
    exit 0
  fi

  GPUS="$(select_free_gpus || true)"
  GPU_COUNT="$(count_gpus "$GPUS")"
  if [ "$GPU_COUNT" -eq 0 ]; then
    log "CPS offload waiting: free_gpus=none $(memory_rule) util<=${UTIL_LIMIT_PCT}%"
    sleep "$POLL_SECONDS"
    continue
  fi
  CLAIM_COUNT="$(claim_count_for_gpus "$GPU_COUNT")"

  BATCH="$(date +%Y%m%d_%H%M%S)"
  FARM_JOBS="$FARM_ROOT/experiments/v2xverse_codriving_diag/results/jobs_phase1_full_cps_offload_$BATCH.tsv"
  CPS_JOBS="$CPS_ROOT/experiments/v2xverse_codriving_diag/jobs_phase1_full_cps_offload_$BATCH.tsv"
  CPS_OUT="$CPS_RESULTS_ROOT/phase1_full_cps_offload_$BATCH"
  LOCAL_JOBS="$LOCAL_TMP/jobs_phase1_full_cps_offload_$BATCH.tsv"
  LOCAL_IDS="$LOCAL_TMP/jobs_phase1_full_cps_offload_$BATCH.ids"
  LOCAL_STATUS="$LOCAL_TMP/launcher_status_cps_offload_$BATCH.csv"
  FARM_STATUS="/tmp/launcher_status_cps_offload_$BATCH.csv"

  log "claiming CPS offload batch=$BATCH gpus=$GPUS gpu_count=$GPU_COUNT claim_count=$CLAIM_COUNT jobs_per_gpu=$JOBS_PER_GPU"
  CLAIM_OUTPUT="$(ssh "$FARM_HOST" "cd '$FARM_ROOT' && $FARM_PYTHON experiments/v2xverse_codriving_diag/offload_shared_jobs.py claim --queue-root '$QUEUE_ROOT' --jobs experiments/v2xverse_codriving_diag/jobs_phase1_full_farm_shared.tsv --count '$CLAIM_COUNT' --out-jobs '$FARM_JOBS' --host-id cps --remote-out-root '$CPS_OUT'")"
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
  ssh "$CPS_HOST" "cd '$CPS_ROOT' && mkdir -p '$CPS_RESULTS_ROOT' && JOB_FILE='$CPS_JOBS' OUT_ROOT='$CPS_OUT' V2X_GPU_LIST='$GPUS' nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase1_full_cps.sh > '$CPS_RESULTS_ROOT/phase1_full_cps_offload_$BATCH.log' 2>&1 & echo \$! > '$CPS_RESULTS_ROOT/phase1_full_cps_offload_$BATCH.pid'"

  while ssh "$CPS_HOST" "pid=\$(cat '$CPS_RESULTS_ROOT/phase1_full_cps_offload_$BATCH.pid' 2>/dev/null || true); [ -n \"\$pid\" ] && kill -0 \"\$pid\" 2>/dev/null"; do
    log "CPS offload batch=$BATCH still running"
    sleep "$POLL_SECONDS"
  done

  if ssh "$CPS_HOST" "[ -f '$CPS_OUT/launcher_status.csv' ]"; then
    scp "$CPS_HOST:$CPS_OUT/launcher_status.csv" "$LOCAL_STATUS" >/dev/null
    scp "$LOCAL_STATUS" "$FARM_HOST:$FARM_STATUS" >/dev/null
    ssh "$FARM_HOST" "cd '$FARM_ROOT' && $FARM_PYTHON experiments/v2xverse_codriving_diag/offload_shared_jobs.py merge --queue-root '$QUEUE_ROOT' --launcher-status '$FARM_STATUS' --host-id cps"
    completed_batches=$((completed_batches + 1))
    log "merged CPS offload batch=$BATCH completed_batches=$completed_batches"
  else
    log "missing CPS launcher_status for batch=$BATCH; releasing claimed rows"
    release_batch "$LOCAL_IDS"
  fi
done
