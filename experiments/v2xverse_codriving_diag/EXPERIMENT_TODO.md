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
  - default free-GPU threshold for offload monitor: memory free `>=20000MiB`, utilization `<=20%`

## 2. Config Files

- Planner/perception harness: `experiments/v2xverse_codriving_diag/run_planner_diag.py`
- Queue launcher: `experiments/v2xverse_codriving_diag/launch_local_queue.py`
- Shared-storage queue launcher: `experiments/v2xverse_codriving_diag/launch_shared_queue.py`
- Cross-storage offload helper: `experiments/v2xverse_codriving_diag/offload_shared_jobs.py`
- Planning delta/coop-state enricher: `experiments/v2xverse_codriving_diag/enrich_planning_deltas.py`
- Empirical best-source baseline builder: `experiments/v2xverse_codriving_diag/make_best_single_source.py`
- Completed-run postprocessor: `experiments/v2xverse_codriving_diag/postprocess_done_runs.py`
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
- Objective Stage 0-6 jobs:
  - `experiments/v2xverse_codriving_diag/jobs_objective_stage0.tsv` (`9` jobs)
  - `experiments/v2xverse_codriving_diag/jobs_objective_stage1.tsv` (`42` jobs)
  - `experiments/v2xverse_codriving_diag/jobs_objective_stage2.tsv` (`128` jobs)
  - `experiments/v2xverse_codriving_diag/jobs_objective_stage3.tsv` (`60` jobs)
  - `experiments/v2xverse_codriving_diag/jobs_objective_stage4.tsv` (`48` jobs)
  - `experiments/v2xverse_codriving_diag/jobs_objective_stage5.tsv` (`132` jobs)
  - `experiments/v2xverse_codriving_diag/jobs_objective_stage6.tsv` (`9` jobs)
  - `experiments/v2xverse_codriving_diag/jobs_objective_full.tsv` (`428` jobs)
- Full phase 1 queue and fallback files:
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
  - CPS cross-storage offload monitor: `experiments/v2xverse_codriving_diag/bin/monitor_cps_offload.sh`
  - Objective queue chain monitor: `experiments/v2xverse_codriving_diag/bin/monitor_objective_chain.sh`
  - Completed-run postprocess monitor: `experiments/v2xverse_codriving_diag/bin/monitor_done_postprocess.sh`
  - CPS offload recovery watcher: `experiments/v2xverse_codriving_diag/bin/watch_cps_offload_batch.sh`
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
- [x] `clean_best_single_source`: empirical post-hoc oracle baseline built from sample-wise lower ADE of `clean_rsu_only` and `clean_vehicle_only`.
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

Delta/coop-state enrichment artifact:

- Combined phase0 enriched planning CSV: `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase0_baseline_planning_enriched.csv`
- Per-run enriched planning CSVs: `per_sample_planning_enriched.csv` in each phase0 run directory.
- Empirical best single-source run dir: `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase0_empirical_baselines/phase0_clean_best_single_source_empirical_seed0`
- Empirical best-source counts: RSU `1741`, CAV `1819`, missing `0`.

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

Execution policy:

- FARM shared queue is the default execution mode for FARM hosts. FARM2/6/7/8/9 and later FARM1 all consume the same `300` pending-job queue, so a faster or earlier-freed host automatically takes more work.
- Active FARM GPU plan: FARM8 GPUs `0,1,2,3`; FARM6 GPUs `0,1,2`; FARM7 GPUs `0,1,2`; FARM2 GPUs `0,1`; FARM9 GPUs `1,2`; FARM1 GPUs `1,2,3` only after the remaining pilot jobs finish.
- FARM1 GPU `0` and FARM9 GPU `0` remain reserved.
- Static per-host TSVs are fallback/recovery files only. They are not the preferred execution plan because they can leave a server idle after its assigned slice finishes.
- CPS is dynamic offload only. Do not run a static CPS split concurrently while the FARM shared queue contains all `300` jobs, unless those jobs are explicitly removed or marked from the FARM queue first.
- CPS has separate storage, so it cannot directly join the FARM lock directory. To use CPS safely, first run `offload_shared_jobs.py claim` on FARM to mark pending rows as `offloaded` and write a CPS TSV, copy that TSV to CPS, run `launch_phase1_full_cps.sh` with `JOB_FILE=<offload TSV>`, then merge CPS `launcher_status.csv` back with `offload_shared_jobs.py merge`. If CPS launch is aborted before running, use `offload_shared_jobs.py release --host-id cps`.
- `bin/monitor_cps_offload.sh` automates the CPS procedure from a controller host that can SSH to both `FARM9` and `cps_workstation`. It excludes GPUs already running CPS offload batches, waits until remaining CPS GPUs satisfy the free-GPU threshold, and by default launches one independent CPS offload batch per free GPU. Each GPU batch now claims `1` pending job from the FARM shared queue and runs asynchronously, so if one CPS GPU finishes earlier than another it can immediately claim more work. This avoids a static CPS slice and minimizes tail idle time when FARM finishes the local shared queue first. Every loop also scans already offloaded CPS batches and partially merges any `running`/`done`/`failed` rows from CPS `launcher_status.csv` back into the FARM shared queue; completed CPS run directories are copied back before `done` rows are merged. If an inactive CPS batch is missing claimed rows in `launcher_status.csv`, those rows are released back to `pending`. Increase `V2X_CPS_OFFLOAD_JOBS_PER_GPU` only when launch overhead is more important than tail utilization; `V2X_CPS_OFFLOAD_ONE_BATCH_PER_GPU=0` restores one combined multi-GPU batch.
- `bin/monitor_objective_chain.sh` waits for the current `300`-job FARM shared queue to drain, launches `jobs_objective_full.tsv` (`428` jobs) as the next FARM shared queue on FARM2/6/7/8/9 plus per-GPU FARM1 waiters, starts a completed-run postprocess monitor for the objective root, updates controller-local CPS monitor state files, and restarts the CPS LaunchAgent so CPS offload claims from the objective job file.
- If a controller is interrupted after CPS launch, run `bin/watch_cps_offload_batch.sh` with the batch stamp. It waits for the CPS launcher PID, merges `launcher_status.csv` into the FARM shared queue, or releases the claimed rows if the CPS status file is missing.

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

Objective Stage 0-6 job files now cover `428` jobs:

- Stage 0 baseline/logging sanity: `9` jobs.
- Stage 1 high-yield screening: `42` jobs.
- Stage 2 top-family full severity: `128` jobs.
- Stage 3 bandwidth/request proxy sweep: `60` jobs.
- Stage 4 pose/calibration protocol sweep: `48` jobs.
- Stage 5 photometric full sweep: `132` jobs.
- Stage 6 compound selected sweep: `9` jobs.

Original objective coverage notes:

- Naming aliases currently used by the harness:
  - `clean_cav_only` -> `clean_vehicle_only`
  - `null_rsu_only_cav_clean` -> `null_rsu_only`
  - `null_cav_only_rsu_clean` -> `null_vehicle_only`
  - `cav_shifted_only_rsu_clean` -> `vehicle_shifted_only`
  - `packet_drop_input` -> `packet_drop`
- Already executable: `latency_det`, `latency_jitter`, `frame_lost_hold`, `packet_drop`, `bandwidth_cap`, `topk_feature_cap` proxy, `request_region_cap` proxy, FOV loss families, `camera_crash`, `missing_camera`, `pose_noise`, `pose_bias`, `pose_drift`, `calibration`, photometric/weather corruptions, and current compound families.
- Hook/job backlog for the exact original objective:
  - true CoDriving request-map internals for `source_selected_by_request`, attention/fusion weights, request-map entropy, and route/actor overlap.
  - true feature-token gating for `topk_feature_cap` and `request_region_cap`; current implementation is a deterministic LiDAR/FOV proxy with bandwidth/request-region audit fields.
  - exact source-combination semantics for `shifted_source_full_clean_source_limited` and `clean_source_full_shifted_source_limited`; current implementation maps these to deterministic RSU/CAV-side limited-source proxies.

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

Every open-loop run should ultimately log the fields below. Current files cover the core planning fields, normalized aliases, ADE/FDE horizon aliases, approximate communication payload fields, and a broader set of per-agent transform audit fields. `enrich_planning_deltas.py` post-fills delta-vs-baseline, worse-than, and coop-state fields when baseline roots are available. The remaining request-map internals and route-corridor overlap fields are backlog items.

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

Last checked: 2026-07-07 13:44 KST. The earlier shared root `phase1_full_farm_shared_20260707_121317` was stopped because it was generated before CPS-offload removal and covered only the FARM slice. It was replaced by the full `300`-job shared FARM queue at `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm_shared_20260707_122043`; status file is `shared_queue_status.csv`. Active shared queue workers: FARM2 PID `83489` on GPUs `0,1`, FARM6 PID `81591` on GPUs `0,1,2`, FARM7 PID `81698` on GPUs `0,1,2`, FARM8 PID `83242` on GPUs `0,1,2,3`, FARM9 PID `44934` on GPUs `1,2`; FARM1 shared waiter PID `89159` waits for GPUs `1,2,3` after pilot completion. Current shared queue status is `running=14,pending=282,offloaded=4`, with no completed full jobs yet and no fatal traceback/RuntimeError observed in FARM shared logs. CPS dynamic offload is active on both CPS GPUs: batch `/data/adas/e2e/experiments/v2xverse_codriving_diag/results/phase1_full_cps_offload_20260707_130301` runs on GPU `0` with `phase1full_clean_all_latency_jitter_s1_vehicle_shifted_only_seed0` past `progress 1275/3560`, and batch `/data/adas/e2e/experiments/v2xverse_codriving_diag/results/phase1_full_cps_offload_20260707_130943` runs on GPU `1` with `phase1full_clean_all_latency_jitter_s2_rsu_shifted_only_seed0` past `progress 1100/3560`; this job currently emits delayed-source fallback warnings but no fatal error. The queued second jobs in those CPS batches are `phase1full_clean_all_latency_jitter_s2_all_shifted_seed0` and `phase1full_clean_all_latency_jitter_s2_vehicle_shifted_only_seed0`. The controller Mac LaunchAgent `com.jy.v2x.cps-offload` is running with log `/tmp/v2x_cps_offload_monitor_launchd.log`; it reads controller-local queue/job/prefix state files, excludes CPS GPUs already running offload batches, scans all offloaded CPS batches each loop without stdin loss, merges finished `launcher_status.csv` files back into the FARM shared queue, and releases stale offloaded rows if a CPS batch has no usable status file and no active CPS process. The monitor now defaults to one independent offload batch per free CPS GPU, so a GPU that finishes earlier can claim additional FARM pending jobs without waiting for a different CPS GPU batch. Objective chain LaunchAgent `com.jy.v2x.objective-chain` is running with log `/tmp/v2x_objective_chain_launchd.log`; it waits for the current `300`-job queue to drain, then launches `jobs_objective_full.tsv` (`428` jobs) as `objective_full_farm_shared_20260707_133600`, updates CPS monitor state files to `jobs_objective_full.tsv` and `objective_full_cps_offload`, and restarts CPS offload. FARM1 phase1 pilot root `phase1_pilot_farm1_20260706_183438` remains `done=8,running=3`: `bandwidth_cap/s3/all_shifted` is past `progress 3275/3560`, `fov_left_loss/s3/rsu_shifted_only` past `progress 825/3560`, and `fov_right_loss/s3/vehicle_shifted_only` past `progress 1100/3560`. FARM1 has not joined the shared full queue yet. CPS pilot root remains `done=4,running=1`; CPS duplicate static full processes are not active. New harness support added for aliases, `clean_best_single_source` proxy, `missing_camera`, `pose_bias`, `pose_drift`, `calibration`, `topk_feature_cap` proxy, `request_region_cap` proxy, expanded per-agent communication/audit fields, objective Stage 0-6 TSVs (`428` total jobs), empirical best single-source baseline, and post-hoc planning baseline delta enrichment. Phase0 baseline enrichment regenerated `32040` rows with `3560` baseline keys and no missing `clean_best_single_source` baseline values.

Last checked: 2026-07-07 14:08 KST. FARM1 phase1 pilot advanced to `done=9,running=2`: `bandwidth_cap/s3/all_shifted` produced `summary.json`, while `fov_left_loss/s3/rsu_shifted_only` is past `progress 1650/3560` and `fov_right_loss/s3/vehicle_shifted_only` is past `progress 1600/3560`; no fatal error observed, only known delayed-source fallback warnings. FARM shared full queue remains active at `running=14,pending=282,offloaded=4`, with no completed full jobs yet and progress sample past `2975/3560`. CPS offload batches remain active on both GPUs: `phase1_full_cps_offload_20260707_130301` is past `progress 1950/3560`, and `phase1_full_cps_offload_20260707_130943` is past `progress 1775/3560`; no fatal error observed. Objective chain LaunchAgent saw a transient SSH `Network is unreachable` at 14:01 KST, briefly logged an empty count as drained, but no objective root or objective process was created and the current shared queue was rechecked as `offloaded=4,pending=282,running=14`; `monitor_objective_chain.sh` was patched so failed or empty queue-count checks retry instead of being treated as drained.

Last checked: 2026-07-07 14:13 KST. FARM1 free-GPU watcher comparison was fixed to force numeric awk comparisons on mawk hosts; the same fix was applied to CPS/full/pilot waiters and committed/pushed. The stale FARM1 all-GPU waiter was replaced with per-GPU waiters for GPUs `1,2,3`. GPU `2` immediately joined the shared full queue and is running `phase1full_clean_all_latency_jitter_s3_all_shifted_seed0`, while GPUs `1` and `3` continue waiting for their remaining pilot jobs to finish. Current FARM shared queue status is `running=15,pending=281,offloaded=4`, with `farm1=1,farm2=2,farm6=3,farm7=3,farm8=4,farm9=2` active workers. CPS offload monitor was restarted after the numeric selector fix and remains active; existing CPS batches continue running.

Last checked: 2026-07-07 14:16 KST. FARM shared full queue advanced to `done=3,running=15,pending=278,offloaded=4` with no failed rows and no fatal tracebacks found in shared logs. Completed runs are `phase1full_clean_all_latency_det_s1_rsu_shifted_only_seed0`, `phase1full_clean_all_latency_det_s2_rsu_shifted_only_seed0`, and `phase1full_clean_all_latency_det_s3_rsu_shifted_only_seed0`; each has `summary.json`. Partial aggregate was refreshed at `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm_shared_20260707_122043/combined/summary.csv` and `combined/RESULTS.md` with `3` completed runs. Baseline delta enrichment was run only on those `done` directories, producing per-run `per_sample_planning_enriched.csv` files and `combined/planning_enriched_done.csv` with `10680` rows and `0` missing baseline keys. FARM1 GPU `2` shared run reached `progress 25/3560`; FARM1 GPUs `1` and `3` remain per-GPU waiters behind the two remaining pilot jobs. CPS offload batches remain running, with batch `20260707_130301` past `progress 2150/3560` and batch `20260707_130943` past `progress 2000/3560`; no CPS fatal errors observed. Objective root `objective_full_farm_shared_20260707_133600` does not exist yet, and the patched objective chain monitor is still waiting for current queue drain.

Last checked: 2026-07-07 14:19 KST. FARM shared full queue remains healthy at `done=3,running=15,pending=278,offloaded=4`; no failed rows or fatal shared logs were found. New FARM progress includes `latency_jitter/s3` and `latency_jitter/stress` jobs starting on FARM1/FARM6, while FARM8 `latency_jitter/s1/rsu_shifted_only` is past `progress 3250/3560`. CPS offload batches remain active, with batch `20260707_130301` past `progress 2225/3560` and batch `20260707_130943` past `progress 2075/3560`. The CPS offload monitor was hardened so that if an inactive multi-job CPS batch has a partial `launcher_status.csv`, any claimed FARM rows missing from that status file are released back to `pending` instead of remaining permanently `offloaded`.

Last checked: 2026-07-07 14:22 KST. FARM shared full queue is still `done=3,running=15,pending=278,offloaded=4`, with no failed rows. CPS offload batches remain active (`20260707_130301` past `progress 2325/3560`, `20260707_130943` past `progress 2175/3560`) and no fatal CPS errors were observed. The CPS offload monitor was further hardened to copy completed CPS run directories from `/data/adas/e2e/experiments/.../<batch>/<run_id>` back into the FARM shared result root before merging `launcher_status.csv`; this keeps FARM-side aggregate/enrichment from missing CPS-completed runs.

Last checked: 2026-07-07 14:25 KST. Added `postprocess_done_runs.py` and `bin/monitor_done_postprocess.sh` so FARM shared roots continuously refresh `combined/summary.csv`, `combined/RESULTS.md`, `combined/planning_enriched_done.csv`, and `combined/postprocess_status.json` from queue rows whose status is `done`. Objective chain was updated to start FARM1 as per-GPU waiters for objective runs and to launch a postprocess monitor for the objective root. The current FARM shared root still reports `done=3,running=15,pending=278,offloaded=4`.

Last checked: 2026-07-07 14:28 KST. One-shot postprocess on current FARM shared root succeeded after the queue advanced to `done=6,running=15,pending=275,offloaded=4`: `combined/postprocess_status.json` reports `done_result_dirs=6`, `summary_rows=6`, `enriched_rows=21360`, `missing_baseline_rows=0`, and no missing completed result dirs. A background postprocess monitor is now running on FARM9 with log `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/postprocess_phase1_full_farm_shared_20260707_122043.log` and pid file `/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/postprocess_phase1_full_farm_shared_20260707_122043.pid`.

Last checked: 2026-07-07 14:30 KST. Objective-chain LaunchAgent was restarted onto the version that launches per-GPU FARM1 objective waiters and objective postprocess monitoring; it is running as PID `39793` and reads current queue status as `done=7,offloaded=4,pending=274,running=15`. One-shot postprocess was rerun on the current FARM shared root and `combined/postprocess_status.json` now reports `done_result_dirs=7`, `summary_rows=7`, `enriched_rows=24920`, `missing_baseline_rows=0`, and no missing completed result dirs.

Last checked: 2026-07-07 14:35 KST. FARM shared full queue advanced to `done=8,running=15,pending=273,offloaded=4` with failed rows `0`. The completed set now includes `latency_det/s1,s2,s3` RSU-shifted, `latency_det/s1,s2` vehicle-shifted, `latency_det/stress` all/RSU-shifted, and `latency_jitter/s1` RSU-shifted. A one-shot completed-run postprocess was run after the status change; `combined/postprocess_status.json` reports `done_result_dirs=8`, `summary_rows=8`, `enriched_rows=28480`, `missing_baseline_rows=0`, and no missing completed result dirs. FARM1 pilot remains `done=9,running=2`, H200 `sub_vehicle_stg2` remains healthy at epoch 18/30, and CPS offload batches remain active with no fatal errors.

Last checked: 2026-07-07 14:36 KST. Current FARM shared queue is `done=8,offloaded=4,pending=273,running=15`, with no failed rows and no completed rows missing `summary.json`. A duplicate postprocess monitor from an earlier malformed launch was checked; the current postprocess monitor remains active, and a one-shot refresh updated `combined/postprocess_status.json` to `summary_rows=8`, `enriched_rows=28480`, and `missing_baseline_rows=0`. Objective/CPS launch helpers were patched so future background pid files record the actual launcher/monitor process instead of a wrapper shell.

Last checked: 2026-07-07 14:41 KST. CPS offload was tightened from static/deep batching to one-job leases: `monitor_cps_offload.sh` now defaults `V2X_CPS_OFFLOAD_JOBS_PER_GPU=1`, and the controller LaunchAgent wrapper was updated to pass the same value. Existing multi-job CPS batches are still allowed to finish, but the monitor now partial-merges CPS `running`/`done`/`failed` rows every loop instead of waiting for the whole batch to end. Current FARM shared queue is `done=10,running=17,pending=271,offloaded=2`; the only remaining `offloaded` rows are the two not-yet-started jobs already claimed by old CPS two-job batches. One-shot completed-run postprocess reports `summary_rows=10`, `enriched_rows=35600`, `missing_baseline_rows=0`, and no missing completed result directories.

Last checked: 2026-07-07 14:44 KST. Current FARM shared queue remains healthy at `done=10,running=17,pending=271,offloaded=2`, with no failed rows and no fatal `Traceback`/`RuntimeError`/OOM markers in FARM or CPS logs. Active running workers are `farm1=1`, `farm2=2`, `farm6=3`, `farm7=3`, `farm8=4`, `farm9=2`, and `cps=2`; FARM1 GPU `0` and FARM9 GPU `0` remain unused. FARM running logs all showed recent progress within roughly two minutes; CPS batch `20260707_130301` reached about `3000/3560`, and batch `20260707_130943` is still advancing with delayed-source fallback warnings only. Objective chain is still waiting on the current queue and last read counts as `done=10 offloaded=2 pending=271 running=17`.

Last checked: 2026-07-07 14:50 KST. `monitor_cps_offload.sh` was hardened for CPS recovery/release edge cases: active-batch detection now uses `ps` with self-match-safe grep patterns, and FARM queue comparisons normalize CPS paths by stripping `/_launcher_logs/...` before matching the CPS batch root. This prevents partial-merged CPS `running` rows from being treated as fake batches named after individual log files. Validation on the live queue returns only the two real CPS batch roots, and a bogus log-file batch name returns inactive. Current shared queue counts are unchanged at `done=10,running=17,pending=271,offloaded=2`; postprocess remains `summary_rows=10,enriched_rows=35600,missing_baseline_rows=0`; CPS batches are still progressing (`20260707_130301` past `3200/3560`, `20260707_130943` past `3050/3560`) without fatal error patterns.

Last checked: 2026-07-07 14:51 KST. FARM shared queue advanced to `done=11,running=17,pending=270,offloaded=2` with no failed rows. A one-shot completed-run postprocess was run immediately after the status change; `combined/postprocess_status.json` now reports `done_result_dirs=11`, `summary_rows=11`, `enriched_rows=39160`, `missing_baseline_rows=0`, and no missing completed result directories.

Last checked: 2026-07-07 14:57 KST. FARM shared queue advanced to `done=12,running=17,pending=269,offloaded=2` with no failed rows and no fatal FARM/CPS log patterns. The new completed run is `phase1full_clean_all_latency_jitter_s1_all_shifted_seed0` on FARM8. One-shot completed-run postprocess refreshed `combined/postprocess_status.json` to `done_result_dirs=12`, `summary_rows=12`, `enriched_rows=42720`, `missing_baseline_rows=0`, and no missing completed result directories. The CPS monitor's latest loop after the recovery matching patch processed only the real CPS batch roots; no new fake log-file batch entries appeared after the 14:51 restart. CPS batches are still progressing toward their first-job completions (`20260707_130301` past `3400/3560`, `20260707_130943` past `3275/3560`).

Last checked: 2026-07-07 15:08 KST. Both initial CPS offload jobs finished successfully and were merged into the FARM shared queue after copying their result directories back to the FARM result root: `phase1full_clean_all_latency_jitter_s1_vehicle_shifted_only_seed0` from batch `20260707_130301`, and `phase1full_clean_all_latency_jitter_s2_rsu_shifted_only_seed0` from batch `20260707_130943`. The two queued second jobs in those old CPS batches immediately started on CPS GPUs `0` and `1`, so the current shared queue is `done=14,running=17,pending=269` with `offloaded=0` and no failed rows. One-shot completed-run postprocess now reports `done_result_dirs=14`, `summary_rows=14`, `enriched_rows=49840`, `missing_baseline_rows=0`, and no missing completed result directories. CPS fatal-log scan is empty; running second CPS jobs are `phase1full_clean_all_latency_jitter_s2_all_shifted_seed0` and `phase1full_clean_all_latency_jitter_s2_vehicle_shifted_only_seed0`.

Last checked: 2026-07-07 15:10 KST. Current shared queue remains `done=14,running=17,pending=269` with no failed rows and no fatal FARM log patterns. Running worker distribution is still `farm1=1`, `farm2=2`, `farm6=3`, `farm7=3`, `farm8=4`, `farm9=2`, `cps=2`; all FARM running logs had recent progress within roughly two minutes. FARM1 GPU `0` and FARM9 GPU `0` remain unused. FARM1 pilot remains `done=9,running=2`; GPU `2` is already in the shared full queue, while GPU `1` and GPU `3` wait behind the remaining pilot jobs. CPS second jobs are advancing (`phase1full_clean_all_latency_jitter_s2_all_shifted_seed0` past `150/3560`, `phase1full_clean_all_latency_jitter_s2_vehicle_shifted_only_seed0` past `50/3560`) with no CPS fatal log patterns.
