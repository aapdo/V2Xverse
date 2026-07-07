#!/usr/bin/env bash
set -euo pipefail

# Controller-side monitor. It normally waits for the active FARM shared queue to
# drain, but can also start the objective queue once the active queue is in its
# tail: no pending/offloaded rows remain and only already-running jobs are left.
# Objective FARM workers are started as per-GPU waiters so they only attach to
# GPUs that are actually free.

FARM_ROOT="${FARM_ROOT:-/home/jy/adas/external/V2Xverse}"
FARM_STATUS_HOST="${FARM_STATUS_HOST:-FARM9}"
CURRENT_QUEUE_ROOT="${CURRENT_QUEUE_ROOT:?set CURRENT_QUEUE_ROOT to the active shared queue root}"
OBJECTIVE_JOB_FILE="${OBJECTIVE_JOB_FILE:-experiments/v2xverse_codriving_diag/jobs_objective_full.tsv}"
OBJECTIVE_STAMP="${OBJECTIVE_STAMP:-$(date +%Y%m%d_%H%M%S)}"
OBJECTIVE_OUT_ROOT="${OBJECTIVE_OUT_ROOT:-$FARM_ROOT/experiments/v2xverse_codriving_diag/results/objective_full_farm_shared_$OBJECTIVE_STAMP}"
RESULTS_ROOT="${FARM_ROOT}/experiments/v2xverse_codriving_diag/results"
POLL_SECONDS="${V2X_CHAIN_POLL_SECONDS:-300}"
START_ON_TAIL_ONLY="${V2X_CHAIN_START_ON_TAIL_ONLY:-1}"
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

queue_ready_for_next() {
  local counts active pending offloaded
  if ! counts="$(queue_counts)" || [ -z "$counts" ]; then
    log "current queue count check failed or returned empty; retrying"
    return 1
  fi
  pending="$(awk -F= 'BEGIN{x=0} $1=="pending" {x=$2 + 0} END {print x}' <<< "$counts")"
  offloaded="$(awk -F= 'BEGIN{x=0} $1=="offloaded" {x=$2 + 0} END {print x}' <<< "$counts")"
  active="$(awk -F= '$1=="pending" || $1=="running" || $1=="offloaded" {s += $2} END {print s+0}' <<< "$counts")"
  log "current queue counts: ${counts//$'\n'/ }"
  if [ "$active" -eq 0 ]; then
    QUEUE_TRANSITION_REASON="drained"
    return 0
  fi
  if [ "$START_ON_TAIL_ONLY" = "1" ] && [ "$pending" -eq 0 ] && [ "$offloaded" -eq 0 ]; then
    QUEUE_TRANSITION_REASON="tail-only"
    return 0
  fi
  return 1
}

launch_farm_waiter() {
  local ssh_host="$1"
  local host_tag="$2"
  local gpu="$3"
  local log_path="$RESULTS_ROOT/objective_full_${host_tag}_gpu${gpu}_waiter_$OBJECTIVE_STAMP.log"
  local pid_path="$RESULTS_ROOT/objective_full_${host_tag}_gpu${gpu}_waiter_$OBJECTIVE_STAMP.pid"
  ssh "${SSH_OPTS[@]}" "$ssh_host" "if [ -f '$pid_path' ] && kill -0 \$(cat '$pid_path') 2>/dev/null; then exit 0; fi; cd '$FARM_ROOT' || exit 1; JOB_FILE='$OBJECTIVE_JOB_FILE' OUT_ROOT='$OBJECTIVE_OUT_ROOT' V2X_HOST_TAG='$host_tag' V2X_ALLOWED_GPUS='$gpu' V2X_MIN_GPUS='1' V2X_MAX_GPUS='1' V2X_WAIT_FOR_EXISTING_SHARED_LAUNCHER='0' nohup bash experiments/v2xverse_codriving_diag/bin/wait_launch_phase1_full_farm_shared.sh > '$log_path' 2>&1 < /dev/null & echo \$! > '$pid_path'"
  log "ensured objective $host_tag waiter gpu=$gpu"
}

launch_farm_waiters() {
  launch_farm_waiter FARM2 farm2 0
  launch_farm_waiter FARM2 farm2 1
  launch_farm_waiter FARM6 farm6 0
  launch_farm_waiter FARM6 farm6 1
  launch_farm_waiter FARM6 farm6 2
  launch_farm_waiter FARM7 farm7 0
  launch_farm_waiter FARM7 farm7 1
  launch_farm_waiter FARM7 farm7 2
  launch_farm_waiter FARM8 farm8 0
  launch_farm_waiter FARM8 farm8 1
  launch_farm_waiter FARM8 farm8 2
  launch_farm_waiter FARM8 farm8 3
  launch_farm_waiter FARM9 farm9 1
  launch_farm_waiter FARM9 farm9 2
  launch_farm_waiter FARM1 farm1 1
  launch_farm_waiter FARM1 farm1 2
  launch_farm_waiter FARM1 farm1 3
}

launch_postprocess_monitor() {
  local log_path="$RESULTS_ROOT/objective_full_postprocess_$OBJECTIVE_STAMP.log"
  local pid_path="$RESULTS_ROOT/objective_full_postprocess_$OBJECTIVE_STAMP.pid"
  ssh "${SSH_OPTS[@]}" "$FARM_STATUS_HOST" "if [ -f '$pid_path' ] && kill -0 \$(cat '$pid_path') 2>/dev/null; then exit 0; fi; cd '$FARM_ROOT' || exit 1; QUEUE_ROOT='$OBJECTIVE_OUT_ROOT' V2X_POSTPROCESS_EXIT_ON_DRAIN='1' nohup bash experiments/v2xverse_codriving_diag/bin/monitor_done_postprocess.sh > '$log_path' 2>&1 < /dev/null & echo \$! > '$pid_path'"
  log "ensured objective postprocess monitor"
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
    launch_farm_waiters
  fi
  launch_postprocess_monitor
  configure_cps_monitor
}

while true; do
  if queue_ready_for_next; then
    log "current queue ready for next queue reason=$QUEUE_TRANSITION_REASON; launching objective full queue"
    launch_objective_queue
    exit 0
  fi
  sleep "$POLL_SECONDS"
done
