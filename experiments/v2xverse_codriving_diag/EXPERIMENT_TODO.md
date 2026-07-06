# V2Xverse + CoDriving Zero-Shot Experiment TODO

## 0. Fixed Assumptions

- Training is out of scope. Every run uses the released CoDriving checkpoints as-is.
- Git source of truth: `https://github.com/aapdo/V2Xverse`, branch `codex/v2xverse-diagnostics`.
- wandb project: `v2xverse-codriving-zero-shot`.
- FARM1 GPU 0 and FARM9 GPU 0 are reserved and must not be used.
- FARM machines share `/home/jy/adas/external/V2Xverse`; CPS uses separate `/data` storage.

## 1. Machine Layout

- FARM repo: `/home/jy/adas/external/V2Xverse`
- FARM env: `/home/jy/adas/_envs/v2xverse/bin`
- FARM dataset: `/home/jy/adas/external/V2Xverse/dataset/dataset_v2xverse`
- FARM checkpoints:
  - perception: `/home/jy/adas/external/V2Xverse/checkpoints/codriving/perception`
  - planner: `/home/jy/adas/external/V2Xverse/checkpoints/codriving/planner/codriving_planner.ckpt`
- CPS repo: `/data/adas/e2e/external/V2Xverse`
- CPS env: `/data/adas/e2e/envs/v2xverse/bin`
- CPS dataset: `/data/adas/e2e/datasets/V2Xverse/dataset/dataset_v2xverse`
- CPS experiment mirror/results root: `/data/adas/e2e/experiments/v2xverse_codriving_diag`
- CPS checkpoints:
  - perception: `/data/adas/e2e/external/V2Xverse/checkpoints/codriving/perception`
  - planner: `/data/adas/e2e/external/V2Xverse/checkpoints/codriving/planner/codriving_planner.ckpt`
- CPS watcher:
  - pid file: `/data/adas/e2e/experiments/v2xverse_codriving_diag/results/phase1_pilot_cps_waiter.pid`
  - log file: `/data/adas/e2e/experiments/v2xverse_codriving_diag/results/phase1_pilot_cps_waiter.log`
  - default free-GPU threshold: memory used `<=2048MiB`, utilization `<=20%`

## 2. Config Files

- Planner/perception harness: `experiments/v2xverse_codriving_diag/run_planner_diag.py`
- Queue launcher: `experiments/v2xverse_codriving_diag/launch_local_queue.py`
- Result aggregation: `experiments/v2xverse_codriving_diag/aggregate_results.py`
- Job generation: `experiments/v2xverse_codriving_diag/make_jobs.py`
- CoDriving config loaded by the harness: `codriving/hypes_yaml/codriving/end2end_codriving.yaml`
- Perception checkpoint config: `checkpoints/codriving/perception/config.yaml`
- Phase 0 jobs: `experiments/v2xverse_codriving_diag/jobs_phase0.tsv`
- FARM phase 0 split jobs:
  - `experiments/v2xverse_codriving_diag/jobs_phase0_farm1.tsv`
  - `experiments/v2xverse_codriving_diag/jobs_phase0_farm9.tsv`
- Phase 1 pilot jobs: `experiments/v2xverse_codriving_diag/jobs_phase1_pilot.tsv`
- FARM phase 1 pilot split jobs:
  - `experiments/v2xverse_codriving_diag/jobs_phase1_pilot_farm1.tsv`
  - `experiments/v2xverse_codriving_diag/jobs_phase1_pilot_farm9.tsv`
- Full phase 1 sweep candidates: `experiments/v2xverse_codriving_diag/jobs_phase1_full.tsv`

## 3. Phase 0 Baselines

- [x] `ego_only`: no cooperative source.
- [x] `clean_all`: all cooperative sources.
- [x] `clean_rsu_only`: only RSU cooperative sources.
- [x] `clean_vehicle_only`: only vehicle cooperative sources.
- [x] `null_all_missing_flag`: cooperative sources marked missing.
- [x] `null_rsu_only`: RSU payload nulled, vehicles clean.
- [x] `null_all_image`: retry after sentinel zero-payload fix.
- [x] `null_vehicle_only`: retry after sentinel zero-payload fix.

Result roots:

- FARM1 phase 0: `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase0_farm1_20260706_085007`
- FARM9 phase 0: `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase0_farm9_20260706_085007`

Required completion artifact per root:

- `combined/summary.csv`
- `combined/RESULTS.md`

## 4. Phase 1 Pilot Sweep

Purpose: validate representative physical/corruption families before launching the full Cartesian sweep.

- [ ] `latency_det/s1/all_shifted`
- [ ] `latency_det/s3/all_shifted`
- [ ] `latency_jitter/s3/all_shifted`
- [ ] `latency_jitter/stress/rsu_shifted_only`
- [ ] `frame_lost_hold/s2/rsu_shifted_only`
- [ ] `frame_lost_hold/s2/vehicle_shifted_only`
- [ ] `frame_lost_zero/s3/all_shifted`
- [ ] `packet_drop/s3/all_shifted`
- [ ] `bandwidth_cap/s3/all_shifted`
- [ ] `fov_left_loss/s3/rsu_shifted_only`
- [ ] `fov_right_loss/s3/vehicle_shifted_only`
- [ ] `pose_noise/s3/all_shifted`
- [ ] `camera_crash/s3/rsu_shifted_only`
- [ ] `color_quant/s3/rsu_shifted_only`
- [ ] `jpeg/s3/rsu_shifted_only`
- [ ] `compound_avail/mid/all_shifted`
- [ ] `compound_lcf/mid/all_shifted`
- [ ] `compound_photo_comm/mid/all_shifted`

Launchers:

- FARM1: `experiments/v2xverse_codriving_diag/bin/launch_phase1_pilot_farm1.sh`
- FARM9: `experiments/v2xverse_codriving_diag/bin/launch_phase1_pilot_farm9.sh`
- CPS immediate/free-GPU launcher: `experiments/v2xverse_codriving_diag/bin/wait_launch_phase1_pilot_cps.sh`

Default result roots:

- FARM1: `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_pilot_farm1_<stamp>`
- FARM9: `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_pilot_farm9_<stamp>`
- CPS: `/data/adas/e2e/experiments/v2xverse_codriving_diag/results/phase1_pilot_cps_<stamp>`

## 5. Phase 1 Full Sweep

Purpose: run the complete source-aware physical/corruption diagnostic once pilot results confirm that hooks are stable.

- [ ] Families: `latency_det`, `latency_jitter`, `frame_lost_hold`, `frame_lost_zero`, `packet_drop`, `bandwidth_cap`, `fov_center`, `fov_left_loss`, `fov_right_loss`, `fov_top_loss`, `fov_bottom_loss`, `camera_crash`, `resolution`, `pose_noise`, `color_quant`, `brightness`, `darkness`, `contrast`, `motion_blur`, `defocus_blur`, `jpeg`, `fog`, `rain`, `snow`.
- [ ] Severities: `s1`, `s2`, `s3`, `stress`.
- [ ] Application modes: `all_shifted`, `rsu_shifted_only`, `vehicle_shifted_only`.
- [ ] Compound families: `compound_lcf`, `compound_avail`, `compound_photo_comm`.
- [ ] Compound severities: `mild`, `mid`, `severe`, `stress`.

Job file:

- `experiments/v2xverse_codriving_diag/jobs_phase1_full.tsv`

Recommended execution policy:

- Start with `V2X_MAX_SAMPLES=128` smoke on one free GPU.
- If every pilot/full-smoke job produces `summary.json`, remove `V2X_MAX_SAMPLES` and run full dataset.
- Aggregate each machine root immediately after completion.

## 6. Logs and Outputs

Each run directory should contain:

- `run.log`: local execution log.
- `manifest.csv`: run metadata.
- `per_sample_planning.csv`: ADE/FDE per sample.
- `per_sample_perception.csv`: perception metrics per sample when available.
- `per_sample_agent.csv`: per-agent diagnostic fields when available.
- `summary.json`: run-level aggregate used by `aggregate_results.py`.
- `wandb/`: local wandb cache.

Each launcher root should contain:

- `launcher_status.csv`: job-level launcher status.
- `combined/summary.csv`: aggregate across completed jobs.
- `combined/RESULTS.md`: human-readable result table.

## 7. Current Operational TODO

- [x] Finish FARM1 `phase0_null_all_image_seed0` retry.
- [x] Finish FARM9 `phase0_null_vehicle_only_seed0` retry.
- [x] Aggregate both phase 0 roots after retries complete.
- [x] Keep FARM phase 0 launchers configured to automatically start phase 1 pilot after successful phase 0.
- [x] Finish CPS repo/checkpoint/env setup.
- [x] Start CPS phase 1 pilot watcher if no GPU is immediately free.
- [x] Confirm first CPS phase 1 sample reaches `progress 25/...`.
- [x] Commit and push every harness/doc change before relying on CPS, because FARM and CPS use separate storage.

Last checked: 2026-07-07 03:36 KST. FARM1 retry `phase0_null_all_image_seed0` completed cleanly after reaching `progress 3550/3560`: `summary.json`, `combined/summary.csv`, and `combined/RESULTS.md` are present under `phase0_farm1_20260706_085007`, with recent hard error pattern count 0. Both FARM phase 0 retry roots are now aggregated. The FARM1 chained command launched phase1 pilot root `phase1_pilot_farm1_20260706_183438`; launcher status is `running=3`, first phase1 progress reached `progress 25/3560`, and `summary.json` count is 0. FARM9 phase1 pilot root `phase1_pilot_farm9_20260706_181437` is running with launcher status `running=2`, latest phase1 progress `progress 525/3560`, and `summary.json` count 0. CPS watcher PID `2611377` remains active after launching `phase1_pilot_cps_20260707_025118` on GPU 0; the active first CPS phase1 job reached `progress 975/3560`, `summary.json` count is 0, and the only recent matching lines are non-fatal delayed-source replacement warnings.
