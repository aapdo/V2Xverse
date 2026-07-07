#!/usr/bin/env bash
set -euo pipefail

# Controller-side monitor. Wait for one FARM shared queue to drain, then launch
# the objective full queue on FARM hosts and point CPS offload at the new queue.

FARM_ROOT="${FARM_ROOT:-/home/jy/adas/external/V2Xverse}"
FARM_STATUS_HOST="${FARM_STATUS_HOST:-FARM9}"
CURRENT_QUEUE_ROOT="${CURRENT_QUEUE_ROOT:?set CURRENT_QUEUE_ROOT to the active shared queue root}"
OBJECTIVE_JOB_FILE="${OBJECTIVE_JOB_FILE:-experiments/v2xverse_codriving_diag/jobs_objective_full.tsv}"
OBJECTIVE_STAMP="${OBJECTIVE_STAMP:-$(date +%Y%m%d_%H%M%S)}"
OBJECTIVE_OUT_ROOT="${OBJECTIVE_OUT_ROOT:-$FARM_ROOT/experiments/v2xverse_codriving_diag/results/objective_full_farm_shared_$OBJECTIVE_STAMP}"
RESULTS_ROOT="${FARM_ROOT}/experiments/v2xverse_codriving_diag/results"
POLL_SECONDS="${V2X_CHAIN_POLL_SECONDS:-300}"
SSH_OPTS=(-n -o ConnectTimeout=10)

CPS_QUEUE_ROOT_FILE="${CPS_QUEUE_ROOT_FILE:-/Users/jy/.codex/v2x_cps_offload_queue_root}"
CPS_JOBS_FILE_FILE="${CPS_JOBS_FILE_FILE:-/Users/jy/.codex/v2x_cps_offload_jobs_file}"
CPS_PREFIX_FILE="${CPS_PREFIX_FILE:-/Users/jy/.codex/v2x_cps_offload_prefix}"
CPS_LAUNCH_AGENT="${CPS_LAUNCH_AGENT:-com.jy.v2x.cps-offload}"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*"
}

queue_counts() {
  ssh "${SSH_OPTS[@]}" "$FARM_STATUS_HOST" "python3 - <<'PY'
import csv
from collections import Counter
p = '$CURRENT_QUEUE_ROOT/shared_queue_status.csv'
c = Counter()
with open(p, newline='') as f:
    for row in csv.DictReader(f):
        c[row.get('status', '')] += 1
for k in sorted(c):
    print(f'{k}={c[k]}')
PY"
}

queue_drained() {
  local counts active
  counts="$(queue_counts)"
  active="$(awk -F= '$1=="pending" || $1=="running" || $1=="offloaded" {s += $2} END {print s+0}' <<< "$counts")"
  log "current queue counts: ${counts//$'\n'/ }"
  [ "$active" -eq 0 ]
}

launch_farm_host() {
  local ssh_host="$1"
  local host_tag="$2"
  local gpus="$3"
  local log_path="$RESULTS_ROOT/objective_full_${host_tag}_launcher_$OBJECTIVE_STAMP.log"
  local pid_path="$RESULTS_ROOT/objective_full_${host_tag}_launcher_$OBJECTIVE_STAMP.pid"
  ssh "${SSH_OPTS[@]}" "$ssh_host" "cd '$FARM_ROOT' && JOB_FILE='$OBJECTIVE_JOB_FILE' OUT_ROOT='$OBJECTIVE_OUT_ROOT' V2X_HOST_TAG='$host_tag' V2X_GPU_LIST='$gpus' nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm_shared.sh > '$log_path' 2>&1 & echo \$! > '$pid_path'"
  log "launched objective queue on $host_tag gpus=$gpus"
}

launch_farm1_waiter() {
  local log_path="$RESULTS_ROOT/objective_full_farm1_waiter_$OBJECTIVE_STAMP.log"
  local pid_path="$RESULTS_ROOT/objective_full_farm1_waiter_$OBJECTIVE_STAMP.pid"
  ssh "${SSH_OPTS[@]}" FARM1 "cd '$FARM_ROOT' && JOB_FILE='$OBJECTIVE_JOB_FILE' OUT_ROOT='$OBJECTIVE_OUT_ROOT' V2X_HOST_TAG='farm1' V2X_ALLOWED_GPUS='1,2,3' V2X_MIN_GPUS='3' nohup bash experiments/v2xverse_codriving_diag/bin/wait_launch_phase1_full_farm_shared.sh > '$log_path' 2>&1 & echo \$! > '$pid_path'"
  log "launched objective FARM1 waiter"
}

configure_cps_monitor() {
  printf '%s\n' "$OBJECTIVE_OUT_ROOT" > "$CPS_QUEUE_ROOT_FILE"
  printf '%s\n' "$OBJECTIVE_JOB_FILE" > "$CPS_JOBS_FILE_FILE"
  printf '%s\n' "objective_full_cps_offload" > "$CPS_PREFIX_FILE"
  launchctl kickstart -k "gui/$(id -u)/$CPS_LAUNCH_AGENT" || true
  log "pointed CPS offload monitor at $OBJECTIVE_OUT_ROOT"
}

launch_objective_queue() {
  if ssh "${SSH_OPTS[@]}" "$FARM_STATUS_HOST" "[ -f '$OBJECTIVE_OUT_ROOT/shared_queue_status.csv' ]"; then
    log "objective queue already exists: $OBJECTIVE_OUT_ROOT"
  else
    launch_farm_host FARM2 farm2 0,1
    launch_farm_host FARM6 farm6 0,1,2
    launch_farm_host FARM7 farm7 0,1,2
    launch_farm_host FARM8 farm8 0,1,2,3
    launch_farm_host FARM9 farm9 1,2
    launch_farm1_waiter
  fi
  configure_cps_monitor
}

while true; do
  if queue_drained; then
    log "current queue drained; launching objective full queue"
    launch_objective_queue
    exit 0
  fi
  sleep "$POLL_SECONDS"
done
