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
- Full phase 1 sweep jobs: `experiments/v2xverse_codriving_diag/jobs_phase1_full.tsv`
- Full phase 1 machine splits:
  - FARM shared queue: `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm_shared.tsv` (`300` jobs)
  - FARM8: `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm8.tsv` (`66` jobs)
  - FARM6: `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm6.tsv` (`50` jobs)
  - FARM7: `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm7.tsv` (`50` jobs)
  - FARM1: `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm1.tsv` (`50` jobs)
  - FARM2: `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm2.tsv` (`33` jobs)
  - FARM9: `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm9.tsv` (`33` jobs)
  - CPS optional offload: `experiments/v2xverse_codriving_diag/jobs_phase1_full_cps.tsv` (`18` jobs)
- Full phase 1 launchers:
  - FARM shared immediate: `experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm_shared.sh`
  - FARM shared wait-until-free: `experiments/v2xverse_codriving_diag/bin/wait_launch_phase1_full_farm_shared.sh`
  - FARM2 immediate: `experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm2.sh`
  - FARM6 immediate: `experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm6.sh`
  - FARM7 immediate: `experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm7.sh`
  - FARM8 immediate: `experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm8.sh`
  - FARM9 immediate: `experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm9.sh`
  - FARM1 wait-until-free: `experiments/v2xverse_codriving_diag/bin/wait_launch_phase1_full_farm1.sh`
  - CPS immediate: `experiments/v2xverse_codriving_diag/bin/launch_phase1_full_cps.sh`
  - CPS wait-until-free: `experiments/v2xverse_codriving_diag/bin/wait_launch_phase1_full_cps.sh`

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

- [x] `latency_det/s1/all_shifted`
- [x] `latency_det/s3/all_shifted`
- [x] `latency_jitter/s3/all_shifted`
- [x] `latency_jitter/stress/rsu_shifted_only`
- [x] `frame_lost_hold/s2/rsu_shifted_only`
- [x] `frame_lost_hold/s2/vehicle_shifted_only`
- [ ] `frame_lost_zero/s3/all_shifted`
- [ ] `packet_drop/s3/all_shifted`
- [ ] `bandwidth_cap/s3/all_shifted`
- [ ] `fov_left_loss/s3/rsu_shifted_only`
- [ ] `fov_right_loss/s3/vehicle_shifted_only`
- [x] `pose_noise/s3/all_shifted`
- [x] `camera_crash/s3/rsu_shifted_only`
- [x] `color_quant/s3/rsu_shifted_only`
- [x] `jpeg/s3/rsu_shifted_only`
- [x] `compound_avail/mid/all_shifted`
- [x] `compound_lcf/mid/all_shifted`
- [x] `compound_photo_comm/mid/all_shifted`

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
- `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm_shared.tsv`
- `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm9.tsv`
- `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm1.tsv`
- `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm2.tsv`
- `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm6.tsv`
- `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm7.tsv`
- `experiments/v2xverse_codriving_diag/jobs_phase1_full_farm8.tsv`
- `experiments/v2xverse_codriving_diag/jobs_phase1_full_cps.tsv`

Machine split:

- FARM shared queue is the default execution mode for FARM hosts. FARM2/6/7/8/9 and later FARM1 all consume the same `300` pending-job queue, so a faster or earlier-freed host automatically takes more work.
- FARM8: `66` jobs on GPUs `0,1,2,3`.
- FARM6: `50` jobs on GPUs `0,1,2`.
- FARM7: `50` jobs on GPUs `0,1,2`.
- FARM1: `50` jobs on GPUs `1,2,3` after the remaining pilot jobs finish; GPU `0` remains reserved.
- FARM2: `33` jobs on GPUs `0,1`.
- FARM9: `33` jobs on GPUs `1,2`; GPU `0` remains reserved.
- CPS: optional offload only. Do not run CPS split concurrently while the FARM shared queue contains all `300` jobs, unless those jobs are explicitly removed or marked from the FARM queue first.

Default result roots:

- FARM2: `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm2_<stamp>`
- FARM6: `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm6_<stamp>`
- FARM7: `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm7_<stamp>`
- FARM8: `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm8_<stamp>`
- FARM9: `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm9_<stamp>`
- FARM1: `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm1_<stamp>`
- CPS: `/data/adas/e2e/experiments/v2xverse_codriving_diag/results/phase1_full_cps_<stamp>`

Recommended execution policy:

- Start with `V2X_MAX_SAMPLES=128` smoke on one free GPU.
- If every pilot/full-smoke job produces `summary.json`, remove `V2X_MAX_SAMPLES` and run full dataset.
- Aggregate each machine root immediately after completion.

Current executable full sweep covers `300` jobs:

- `24` non-compound families x `4` severities x `3` modes = `288` jobs.
- `3` compound families x `4` severities x `1` mode = `12` jobs.

Original objective coverage notes:

- Naming aliases currently used by the harness:
  - `clean_cav_only` -> `clean_vehicle_only`
  - `null_rsu_only_cav_clean` -> `null_rsu_only`
  - `null_cav_only_rsu_clean` -> `null_vehicle_only`
  - `cav_shifted_only_rsu_clean` -> `vehicle_shifted_only`
  - `packet_drop_input` -> `packet_drop`
- Already executable: `latency_det`, `latency_jitter`, `frame_lost_hold`, `packet_drop`, `bandwidth_cap`, FOV loss families, `camera_crash`, `pose_noise`, photometric/weather corruptions, and current compound families.
- Hook/job backlog for the exact original objective:
  - `clean_best_single_source`
  - `one_source_null_one_clean`
  - `topk_feature_cap`
  - `request_region_cap`
  - `pose_bias`
  - `pose_drift`
  - `calibration`
  - source-combination modes such as `shifted_source_full_clean_source_limited` and `clean_source_full_shifted_source_limited`

## 5.1 Original Stage Plan

This is the user-requested target plan from the goal objective. The current executable full sweep starts with the implemented subset above; the hook backlog must be added before claiming complete coverage of every item below.

- Stage 0 baseline/logging sanity:
  - `ego_only`
  - `clean_all`
  - `clean_rsu_only`
  - `clean_cav_only`
  - `clean_best_single_source`
  - `null_all_image`
  - `null_all_missing_flag`
  - `null_rsu_only_cav_clean`
  - `null_cav_only_rsu_clean`
- Stage 1 high-yield screening:
  - `latency_jitter_s3`, `latency_jitter_stress`
  - `frame_lost_hold_s2`, `frame_lost_hold_s3`, `frame_lost_hold_stress`
  - `packet_drop_s3`, `packet_drop_stress`
  - `fov_left_loss_s3`
  - `fov_right_loss_s2`, `fov_right_loss_s3`
  - `missing_camera_s2`, `missing_camera_s3`
  - `camera_crash_s2`, `camera_crash_s3`
  - modes: `all_shifted`, `rsu_shifted_only_cav_clean`, `cav_shifted_only_rsu_clean`
- Stage 2 full severity sweep for top families:
  - families: `latency_jitter`, `frame_lost_hold`, `packet_drop_input`, `fov_left_loss`, `fov_right_loss`, `missing_camera`, `camera_crash`, `latency_det`
  - severities: `s1`, `s2`, `s3`, `stress`
  - modes: `all_shifted`, `rsu_shifted_only_cav_clean`, `cav_shifted_only_rsu_clean`, `one_source_null_one_clean`
- Stage 3 bandwidth and request-map sweep:
  - families: `bandwidth_cap`, `topk_feature_cap`, `request_region_cap`
  - severities: `s1`, `s2`, `s3`, `stress`
  - modes: `all_sources_limited`, `rsu_limited_cav_full`, `cav_limited_rsu_full`, `shifted_source_full_clean_source_limited`, `clean_source_full_shifted_source_limited`
- Stage 4 pose/calibration protocol sweep:
  - families: `pose_noise`, `pose_bias`, `pose_drift`, `calibration`
  - severities: `s1`, `s2`, `s3`, `stress`
  - modes: `all_shifted`, `rsu_shifted_only_cav_clean`, `cav_shifted_only_rsu_clean`
- Stage 5 photometric full sweep:
  - families: `color_quant`, `resolution`, `jpeg`, `motion_blur`, `defocus_blur`, `darkness`, `brightness`, `contrast`, `fog`, `rain`, `snow`
  - severities: `s1`, `s2`, `s3`, `stress`
  - modes: `all_shifted`, `rsu_shifted_only_cav_clean`, `cav_shifted_only_rsu_clean`
- Stage 6 compound selected sweep:
  - `compound_availability`: `latency_jitter + frame_lost_hold + packet_drop`
  - `compound_physical`: `latency + pose/calib + FOV`
  - `compound_photo_comm`: `photometric + bandwidth cap or frame lost`
  - modes: `all_shifted`, `rsu_shifted_only_cav_clean`, `cav_shifted_only_rsu_clean`

## 5.2 Mandatory Logging Target

Every open-loop run should ultimately log the fields below. Current files already cover the core planning fields and a subset of per-agent audit fields; the remaining communication/request-map, route-corridor, and delta-vs-baseline fields are backlog items.

- Planning: `sample_id`, `scenario_id`, `frame_id`, `setting`, `shift_family`, `severity`, `application_mode`, `shift_seed`, `ADE`, `FDE`, `ADE@1s`, `ADE@2s`, `ADE@3s`, `ADE@4s`, `FDE@final`, `delta_ADE_vs_clean_all`, `delta_ADE_vs_ego`, `delta_ADE_vs_null_all`, `delta_ADE_vs_clean_best_single_source`, `worse_than_clean_all`, `worse_than_ego`, `worse_than_null_all`, `worse_than_clean_best_single_source`, `delta_ADE_gt_0p2`, `delta_ADE_gt_0p5`, `delta_ADE_gt_1p0`.
- Perception: `mAP`, `AP_vehicle`, `AP_pedestrian`, `AP_cyclist`, `AP30`, `AP50`, `AP70`, `recall_vehicle`, `recall_pedestrian`, `precision_vehicle`, `precision_pedestrian`, `num_gt_vehicle`, `num_pred_vehicle`, `num_tp_vehicle`, `num_fp_vehicle`, `num_fn_vehicle`, `AP_near_gt_traj_5m`, `recall_near_gt_traj_5m`, `FN_near_gt_traj_5m`, `AP_route_corridor`, `recall_route_corridor`.
- Communication/request map: `agent_id`, `agent_type`, `agent_shifted`, `agent_selected`, `source_selected_by_request`, `source_attention_weight`, `source_fusion_weight`, `tx_bytes`, `tx_kb`, `num_transmitted_features`, `num_transmitted_tokens`, `num_selected_regions`, `bandwidth_budget`, `bandwidth_used_ratio`, `request_map_mean`, `request_map_max`, `request_map_entropy`, `request_topk_overlap_gt_future`, `request_topk_overlap_route`, `request_topk_overlap_near_actor`.
- Transform audit: `delay_frames`, `delay_ms`, `held_frame_age`, `frame_lost_flag`, `packet_drop_flag`, `drop_burst_length`, `camera_crash_flag`, `valid_camera_count`, `fov_keep_ratio`, `masked_side`, `masked_pixel_ratio`, `route_corridor_masked_ratio`, `pose_error_m`, `yaw_error_deg`, `calib_translation_error_m`.

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

Last checked: 2026-07-07 12:18 KST. Static FARM full launchers were stopped and replaced by the shared FARM queue. Shared FARM full root is `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm_shared_20260707_121317`; status file is `shared_queue_status.csv`. Active shared queue workers: FARM2 PID `82647` on GPUs `0,1`, FARM6 PID `80615` on GPUs `0,1,2`, FARM7 PID `80720` on GPUs `0,1,2`, FARM8 PID `82126` on GPUs `0,1,2,3`, FARM9 PID `44229` on GPUs `1,2`; FARM1 shared waiter PID `88385` waits for GPUs `1,2,3` after pilot completion. Shared queue status remains `running=14,pending=268`; jobs have reached at least `progress 100/3560`. FARM1 phase1 pilot root `phase1_pilot_farm1_20260706_183438` remains at `done=6,running=3`, so FARM1 has not joined the shared full queue yet. CPS duplicate pilot process is no longer active; CPS full waiter PID `2740454` was stopped and its stale pidfile removed because CPS full launch before pilot/smoke clearance is not authorized by the monitor policy. No CPS full root exists. Recent V2XVerse matching warning lines are non-fatal delayed-source replacement warnings.
