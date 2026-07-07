#!/usr/bin/env bash
set -euo pipefail

ROOT="${V2XVERSE_ROOT:-/home/jy/adas/external/V2Xverse}"
ENV_BIN="${V2XVERSE_ENV_BIN:-/home/jy/adas/_envs/v2xverse/bin}"
cd "$ROOT"

export PATH="$ENV_BIN:$PATH"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export WANDB_PROJECT="${WANDB_PROJECT:-v2xverse-codriving-zero-shot}"
JOB_FILE="${JOB_FILE:-experiments/v2xverse_codriving_diag/jobs_phase1_full_farm_shared.tsv}"
HOST_TAG="${V2X_HOST_TAG:-$(hostname)}"

STAMP="${V2X_FULL_SWEEP_ID:-$(date +%Y%m%d_%H%M%S)}"
OUT_ROOT="${OUT_ROOT:-$ROOT/experiments/v2xverse_codriving_diag/results/phase1_full_farm_shared_$STAMP}"
EXTRA_ARGS=()
if [ -n "${V2X_MAX_SAMPLES:-}" ]; then
  EXTRA_ARGS+=(--max-samples "$V2X_MAX_SAMPLES")
fi

python experiments/v2xverse_codriving_diag/launch_shared_queue.py \
  --repo-root "$ROOT" \
  --jobs "$JOB_FILE" \
  --gpus "$V2X_GPU_LIST" \
  --out-root "$OUT_ROOT" \
  --host-id "$HOST_TAG" \
  --workers "${V2X_WORKERS:-0}" \
  --wandb-mode "${WANDB_MODE:-auto}" \
  --idle-poll-seconds "${V2X_SHARED_IDLE_POLL_SECONDS:-300}" \
  "${EXTRA_ARGS[@]}"

python experiments/v2xverse_codriving_diag/aggregate_results.py --root "$OUT_ROOT"
