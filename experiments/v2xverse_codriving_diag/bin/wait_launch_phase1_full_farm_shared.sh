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
WAIT_FOR_EXISTING_SHARED_LAUNCHER="${V2X_WAIT_FOR_EXISTING_SHARED_LAUNCHER:-0}"

active_shared_launcher() {
  local out_root="${OUT_ROOT:-}"
  local host_tag="${V2X_HOST_TAG:-$(hostname)}"
  [ -n "$out_root" ] || return 1
  pgrep -af "launch_shared_queue.py" \
    | awk -v out_root="$out_root" -v host_tag="$host_tag" '
      index($0, "--out-root " out_root) > 0 && index($0, "--host-id " host_tag) > 0 {
        found = 1;
      }
      END {
        exit found ? 0 : 1;
      }
    '
}

busy_gpus() {
  local uuids
  uuids="$(nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader,nounits 2>/dev/null \
    | awk '{gsub(/ /, ""); if ($0 != "" && $0 != "[NotSupported]") print $0}' \
    | sort -u || true)"
  [ -n "$uuids" ] || return 0
  nvidia-smi --query-gpu=index,uuid --format=csv,noheader,nounits \
    | awk -F, -v uuids="$uuids" '
      BEGIN {
        n = split(uuids, a, "\n");
        for (i = 1; i <= n; i++) {
          if (a[i] != "") busy_uuid[a[i]] = 1;
        }
      }
      {
        gsub(/ /, "", $1); gsub(/ /, "", $2);
        if (busy_uuid[$2]) print $1;
      }
    '
}

select_free_gpus() {
  local busy_lookup
  busy_lookup=",$(busy_gpus | paste -sd, -),"
  nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader,nounits \
    | awk -F, -v mem="$MEM_LIMIT_MIB" -v util="$UTIL_LIMIT_PCT" -v max="$MAX_GPUS" -v allowed="$ALLOWED_GPUS" -v busy="$busy_lookup" '
      BEGIN {
        split(allowed, a, ",");
        for (i in a) {
          if (a[i] != "") ok[a[i]] = 1;
        }
        use_allowed = length(allowed) > 0;
      }
      {
        gsub(/ /, "", $1); gsub(/ /, "", $2); gsub(/ /, "", $3);
        if (index(busy, "," $1 ",") == 0 && (!use_allowed || ok[$1]) && ($2 + 0) <= (mem + 0) && ($3 + 0) <= (util + 0)) {
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
  if [ "$WAIT_FOR_EXISTING_SHARED_LAUNCHER" = "1" ] && active_shared_launcher; then
    echo "$(date -Is) shared FARM full waiting: active launcher still owns ${V2X_HOST_TAG:-$(hostname)} out_root=${OUT_ROOT:-unset}"
    sleep "$POLL_SECONDS"
    continue
  fi

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
