#!/usr/bin/env bash
set -euo pipefail

ROOT="${V2XVERSE_ROOT:-/home/jy/adas/external/V2Xverse}"
QUEUE_ROOT="${QUEUE_ROOT:-${OUT_ROOT:-}}"
if [ -z "$QUEUE_ROOT" ]; then
  echo "set QUEUE_ROOT to the shared queue result root" >&2
  exit 2
fi

POLL_SECONDS="${V2X_POSTPROCESS_POLL_SECONDS:-600}"
ONCE="${V2X_POSTPROCESS_ONCE:-0}"
EXIT_ON_DRAIN="${V2X_POSTPROCESS_EXIT_ON_DRAIN:-0}"
BASELINE_ROOTS_TEXT="${V2X_BASELINE_ROOTS:-experiments/v2xverse_codriving_diag/results/phase0_farm1_20260706_085007:experiments/v2xverse_codriving_diag/results/phase0_farm9_20260706_085007:experiments/v2xverse_codriving_diag/results/phase0_empirical_baselines/phase0_clean_best_single_source_empirical_seed0}"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*"
}

baseline_args() {
  local old_ifs="$IFS"
  IFS=':'
  for root in $BASELINE_ROOTS_TEXT; do
    [ -n "$root" ] || continue
    printf '%s\n' "--baseline-root"
    printf '%s\n' "$root"
  done
  IFS="$old_ifs"
}

active_rows() {
  awk -F, 'NR > 1 && ($2 == "pending" || $2 == "running" || $2 == "offloaded") {n++} END {print n+0}' "$QUEUE_ROOT/shared_queue_status.csv"
}

cd "$ROOT"

while true; do
  mapfile -t BASE_ARGS < <(baseline_args)
  log "postprocess start queue_root=$QUEUE_ROOT"
  python3 experiments/v2xverse_codriving_diag/postprocess_done_runs.py \
    --queue-root "$QUEUE_ROOT" \
    --final-on-drain \
    "${BASE_ARGS[@]}"
  log "postprocess done active_rows=$(active_rows)"

  if [ "$ONCE" = "1" ]; then
    exit 0
  fi
  if [ "$EXIT_ON_DRAIN" = "1" ] && [ "$(active_rows)" -eq 0 ]; then
    log "queue drained; exiting postprocess monitor"
    exit 0
  fi
  sleep "$POLL_SECONDS"
done
