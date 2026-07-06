#!/usr/bin/env bash
set -euo pipefail

ROOT="${V2XVERSE_ROOT:-/home/jy/adas/external/V2Xverse}"
ENV_BIN="${V2XVERSE_ENV_BIN:-/home/jy/adas/_envs/v2xverse/bin}"
cd "$ROOT"

export PATH="$ENV_BIN:$PATH"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export WANDB_PROJECT="${WANDB_PROJECT:-v2xverse-codriving-zero-shot}"
JOB_FILE="${JOB_FILE:-experiments/v2xverse_codriving_diag/jobs_phase0_farm9.tsv}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_ROOT="${OUT_ROOT:-$ROOT/experiments/v2xverse_codriving_diag/results/phase0_farm9_$STAMP}"

python experiments/v2xverse_codriving_diag/launch_local_queue.py \
  --repo-root "$ROOT" \
  --jobs "$JOB_FILE" \
  --gpus "${V2X_GPU_LIST:-1,2}" \
  --out-root "$OUT_ROOT" \
  --workers "${V2X_WORKERS:-0}" \
  --wandb-mode "${WANDB_MODE:-auto}"

python experiments/v2xverse_codriving_diag/aggregate_results.py --root "$OUT_ROOT"

if [ "${RUN_PHASE1_AFTER:-1}" = "1" ]; then
  PHASE1_STAMP="$(date +%Y%m%d_%H%M%S)"
  PHASE1_OUT_ROOT="${PHASE1_OUT_ROOT:-$ROOT/experiments/v2xverse_codriving_diag/results/phase1_pilot_farm9_$PHASE1_STAMP}"
  python experiments/v2xverse_codriving_diag/launch_local_queue.py \
    --repo-root "$ROOT" \
    --jobs "${PHASE1_JOB_FILE:-experiments/v2xverse_codriving_diag/jobs_phase1_pilot_farm9.tsv}" \
    --gpus "${V2X_GPU_LIST:-1,2}" \
    --out-root "$PHASE1_OUT_ROOT" \
    --workers "${V2X_WORKERS:-0}" \
    --wandb-mode "${WANDB_MODE:-auto}"
  python experiments/v2xverse_codriving_diag/aggregate_results.py --root "$PHASE1_OUT_ROOT"
fi
