#!/usr/bin/env bash
set -euo pipefail

# Controller-side helper. It installs one waiter per allowed FARM GPU so an
# idle host can rejoin the shared queue after an older launcher exits.

FARM_ROOT="${FARM_ROOT:-/home/jy/adas/external/V2Xverse}"
OUT_ROOT="${OUT_ROOT:?set OUT_ROOT to the active FARM shared queue root}"
JOB_FILE="${JOB_FILE:-experiments/v2xverse_codriving_diag/jobs_phase1_full_farm_shared.tsv}"
RESULTS_ROOT="${RESULTS_ROOT:-$FARM_ROOT/experiments/v2xverse_codriving_diag/results}"
QUEUE_TAG="${V2X_QUEUE_TAG:-$(basename "$OUT_ROOT")}"
POLL_SECONDS="${V2X_GPU_POLL_SECONDS:-300}"
MEM_LIMIT_MIB="${V2X_FREE_MEM_LIMIT_MIB:-2048}"
UTIL_LIMIT_PCT="${V2X_FREE_UTIL_LIMIT_PCT:-20}"

start_waiter() {
  local ssh_host="$1"
  local host_tag="$2"
  local gpu="$3"
  local log_path="$RESULTS_ROOT/${QUEUE_TAG}_${host_tag}_gpu${gpu}_backstop_waiter.log"
  local pid_path="$RESULTS_ROOT/${QUEUE_TAG}_${host_tag}_gpu${gpu}_backstop_waiter.pid"

  ssh -n "$ssh_host" "if [ -f '$pid_path' ] && kill -0 \$(cat '$pid_path') 2>/dev/null; then exit 0; fi; cd '$FARM_ROOT' || exit 1; JOB_FILE='$JOB_FILE' OUT_ROOT='$OUT_ROOT' V2X_HOST_TAG='$host_tag' V2X_ALLOWED_GPUS='$gpu' V2X_MIN_GPUS=1 V2X_MAX_GPUS=1 V2X_GPU_POLL_SECONDS='$POLL_SECONDS' V2X_FREE_MEM_LIMIT_MIB='$MEM_LIMIT_MIB' V2X_FREE_UTIL_LIMIT_PCT='$UTIL_LIMIT_PCT' V2X_WAIT_FOR_EXISTING_SHARED_LAUNCHER=1 nohup bash experiments/v2xverse_codriving_diag/bin/wait_launch_phase1_full_farm_shared.sh > '$log_path' 2>&1 < /dev/null & echo \$! > '$pid_path'"
  printf 'ensured %s gpu%s backstop log=%s pid=%s\n' "$host_tag" "$gpu" "$log_path" "$pid_path"
}

start_waiter FARM2 farm2 0
start_waiter FARM2 farm2 1
start_waiter FARM6 farm6 0
start_waiter FARM6 farm6 1
start_waiter FARM6 farm6 2
start_waiter FARM7 farm7 0
start_waiter FARM7 farm7 1
start_waiter FARM7 farm7 2
start_waiter FARM8 farm8 0
start_waiter FARM8 farm8 1
start_waiter FARM8 farm8 2
start_waiter FARM8 farm8 3
start_waiter FARM9 farm9 1
start_waiter FARM9 farm9 2
