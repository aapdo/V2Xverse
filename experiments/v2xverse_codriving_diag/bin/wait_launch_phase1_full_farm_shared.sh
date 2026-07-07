#!/usr/bin/env bash
set -euo pipefail

ROOT="${V2XVERSE_ROOT:-/home/jy/adas/external/V2Xverse}"
RESULTS_ROOT="${RESULTS_ROOT:-$ROOT/experiments/v2xverse_codriving_diag/results}"
mkdir -p "$RESULTS_ROOT"

MEM_LIMIT_MIB="${V2X_FREE_MEM_LIMIT_MIB:-2048}"
UTIL_LIMIT_PCT="${V2X_FREE_UTIL_LIMIT_PCT:-20}"
POLL_SECONDS="${V2X_GPU_POLL_SECONDS:-300}"
MIN_GPUS="${V2X_MIN_GPUS:-1}"
MAX_GPUS="${V2X_MAX_GPUS:-99}"
ALLOWED_GPUS="${V2X_ALLOWED_GPUS:-}"

select_free_gpus() {
  nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader,nounits \
    | awk -F, -v mem="$MEM_LIMIT_MIB" -v util="$UTIL_LIMIT_PCT" -v max="$MAX_GPUS" -v allowed="$ALLOWED_GPUS" '
      BEGIN {
        split(allowed, a, ",");
        for (i in a) {
          if (a[i] != "") ok[a[i]] = 1;
        }
        use_allowed = length(allowed) > 0;
      }
      {
        gsub(/ /, "", $1); gsub(/ /, "", $2); gsub(/ /, "", $3);
        if ((!use_allowed || ok[$1]) && $2 <= mem && $3 <= util) {
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

while true; do
  GPUS="$(select_free_gpus || true)"
  GPU_COUNT="$(count_gpus "$GPUS")"
  if [ "$GPU_COUNT" -ge "$MIN_GPUS" ]; then
    export V2X_GPU_LIST="$GPUS"
    echo "$(date -Is) launching shared FARM full queue on ${V2X_HOST_TAG:-$(hostname)} GPUs=$V2X_GPU_LIST"
    exec bash "$ROOT/experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm_shared.sh"
  fi
  echo "$(date -Is) shared FARM full waiting: free_gpus=${GPUS:-none} count=$GPU_COUNT min=$MIN_GPUS allowed=${ALLOWED_GPUS:-all} mem<=${MEM_LIMIT_MIB}MiB util<=${UTIL_LIMIT_PCT}%"
  sleep "$POLL_SECONDS"
done
