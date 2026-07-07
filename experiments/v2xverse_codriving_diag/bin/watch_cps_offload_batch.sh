#!/usr/bin/env bash
set -euo pipefail

# Recovery watcher for a CPS offload batch that has already been launched.
# Use this if the main monitor is interrupted after claim/launch but before merge.

BATCH="${BATCH:?set BATCH, e.g. 20260707_130301}"
QUEUE_ROOT="${QUEUE_ROOT:?set QUEUE_ROOT to the active FARM shared queue root}"
FARM_HOST="${FARM_HOST:-FARM9}"
CPS_HOST="${CPS_HOST:-cps_workstation}"
FARM_ROOT="${FARM_ROOT:-/home/jy/adas/external/V2Xverse}"
CPS_RESULTS_ROOT="${CPS_RESULTS_ROOT:-/data/adas/e2e/experiments/v2xverse_codriving_diag/results}"
LOCAL_TMP="${LOCAL_TMP:-/tmp/v2xverse_cps_offload}"
FARM_PYTHON="${FARM_PYTHON:-python3}"
POLL_SECONDS="${V2X_GPU_POLL_SECONDS:-300}"
SSH_OPTS=(-n -o ConnectTimeout=10)

CPS_OUT="$CPS_RESULTS_ROOT/phase1_full_cps_offload_$BATCH"
LOCAL_STATUS="$LOCAL_TMP/launcher_status_cps_offload_$BATCH.csv"
FARM_STATUS="/tmp/launcher_status_cps_offload_$BATCH.csv"
LOCAL_JOBS="$LOCAL_TMP/jobs_phase1_full_cps_offload_$BATCH.tsv"
LOCAL_IDS="$LOCAL_TMP/jobs_phase1_full_cps_offload_$BATCH.ids"
FARM_JOBS="$FARM_ROOT/experiments/v2xverse_codriving_diag/results/jobs_phase1_full_cps_offload_$BATCH.tsv"

mkdir -p "$LOCAL_TMP"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*"
}

release_batch() {
  if [ ! -f "$LOCAL_IDS" ]; then
    scp "$FARM_HOST:$FARM_JOBS" "$LOCAL_JOBS" >/dev/null
    awk 'NR > 1 {print $1}' "$LOCAL_JOBS" > "$LOCAL_IDS"
  fi
  local remote_ids="/tmp/$(basename "$LOCAL_IDS")"
  scp "$LOCAL_IDS" "$FARM_HOST:$remote_ids" >/dev/null
  ssh "${SSH_OPTS[@]}" "$FARM_HOST" "cd '$FARM_ROOT' && $FARM_PYTHON experiments/v2xverse_codriving_diag/offload_shared_jobs.py release --queue-root '$QUEUE_ROOT' --host-id cps --run-id-file '$remote_ids'"
}

batch_state() {
  if ssh "${SSH_OPTS[@]}" "$CPS_HOST" "test -f '$CPS_OUT/launcher_status.csv' && grep -q ',running,' '$CPS_OUT/launcher_status.csv'"; then
    echo "running"
    return
  fi
  if ssh "${SSH_OPTS[@]}" "$CPS_HOST" "test -f '$CPS_OUT/launcher_status.csv' && grep -Eq ',(done|failed),' '$CPS_OUT/launcher_status.csv'"; then
    echo "finished"
    return
  fi
  if ssh "${SSH_OPTS[@]}" "$CPS_HOST" "pid=\$(cat '$CPS_RESULTS_ROOT/phase1_full_cps_offload_$BATCH.pid' 2>/dev/null || true); [ -n \"\$pid\" ] && kill -0 \"\$pid\" 2>/dev/null"; then
    echo "starting"
    return
  fi
  echo "missing"
}

log "watching CPS offload batch=$BATCH"
while true; do
  STATE="$(batch_state)"
  case "$STATE" in
    running|starting)
      log "CPS offload batch=$BATCH state=$STATE"
      sleep "$POLL_SECONDS"
      ;;
    finished)
      log "CPS offload batch=$BATCH state=finished"
      break
      ;;
    *)
      log "CPS offload batch=$BATCH state=$STATE"
      break
      ;;
  esac
done

if ssh "${SSH_OPTS[@]}" "$CPS_HOST" "[ -f '$CPS_OUT/launcher_status.csv' ]"; then
  scp "$CPS_HOST:$CPS_OUT/launcher_status.csv" "$LOCAL_STATUS" >/dev/null
  scp "$LOCAL_STATUS" "$FARM_HOST:$FARM_STATUS" >/dev/null
  ssh "${SSH_OPTS[@]}" "$FARM_HOST" "cd '$FARM_ROOT' && $FARM_PYTHON experiments/v2xverse_codriving_diag/offload_shared_jobs.py merge --queue-root '$QUEUE_ROOT' --launcher-status '$FARM_STATUS' --host-id cps"
  log "merged CPS offload batch=$BATCH"
else
  log "missing CPS launcher_status for batch=$BATCH; releasing claimed rows"
  release_batch
fi
