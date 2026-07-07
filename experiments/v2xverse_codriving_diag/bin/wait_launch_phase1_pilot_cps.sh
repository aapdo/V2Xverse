#!/usr/bin/env bash
set -euo pipefail

ROOT="${V2XVERSE_ROOT:-/data/adas/e2e/external/V2Xverse}"
RESULTS_ROOT="${RESULTS_ROOT:-/data/adas/e2e/experiments/v2xverse_codriving_diag/results}"
mkdir -p "$RESULTS_ROOT"

MEM_LIMIT_MIB="${V2X_FREE_MEM_LIMIT_MIB:-2048}"
UTIL_LIMIT_PCT="${V2X_FREE_UTIL_LIMIT_PCT:-20}"
POLL_SECONDS="${V2X_GPU_POLL_SECONDS:-300}"
MAX_GPUS="${V2X_MAX_GPUS:-1}"

select_free_gpus() {
  nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader,nounits \
    | awk -F, -v mem="$MEM_LIMIT_MIB" -v util="$UTIL_LIMIT_PCT" -v max="$MAX_GPUS" '
      {
        gsub(/ /, "", $1); gsub(/ /, "", $2); gsub(/ /, "", $3);
        if (($2 + 0) <= (mem + 0) && ($3 + 0) <= (util + 0)) {
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

while true; do
  GPUS="$(select_free_gpus || true)"
  if [ -n "$GPUS" ]; then
    export V2X_GPU_LIST="$GPUS"
    echo "$(date -Is) launching phase1 pilot on CPS GPUs=$V2X_GPU_LIST"
    exec bash "$ROOT/experiments/v2xverse_codriving_diag/bin/launch_phase1_pilot_cps.sh"
  fi
  echo "$(date -Is) no free CPS GPU; waiting ${POLL_SECONDS}s (mem<=${MEM_LIMIT_MIB}MiB util<=${UTIL_LIMIT_PCT}%)"
  sleep "$POLL_SECONDS"
done
