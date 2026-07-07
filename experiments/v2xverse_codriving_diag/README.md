# V2Xverse + CoDriving Multi-Agent Zero-Shot Diagnostics

이 디렉터리는 V2Xverse/CoDriving checkpoint를 재학습 없이 그대로 사용해서 multi-agent physical/corruption diagnostic을 실행하기 위한 harness입니다.

## 목적

- `ego_only`, `clean_all`, `clean_rsu_only`, `clean_vehicle_only`, `null_*` baseline을 먼저 고정한다.
- 이후 latency, frame lost, packet drop, bandwidth, FOV, pose noise, photometric corruption 등을 source별로 적용한다.
- `all_shifted`, `rsu_shifted_only`, `vehicle_shifted_only` 비교로 clean source가 bad source를 보완하는지 또는 all-fusion을 방해받는지 본다.
- 결과는 CSV와 wandb에 동시에 남긴다.

## 중요한 제약

- training은 수행하지 않는다.
- checkpoint:
  - perception: `checkpoints/codriving/perception`
  - planner: `checkpoints/codriving/planner/codriving_planner.ckpt`
- FARM1 GPU 0과 FARM9 GPU 0은 사용하지 않는다.
- CPS는 dataset mirror가 준비되어 있지만, 현재 GPU free memory/utilization 기준을 만족할 때만 FARM shared queue에서 job을 offload한다.
- Full/objective sweep은 정적 split ownership으로 운영하지 않는다. Host별 TSV는 fallback/recovery용이고, 실제 실행은 shared queue와 CPS one-job lease로 idle GPU가 계속 다음 pending job을 가져가는 방식이다.
- `launch_phase0_farm*.sh`는 phase 0가 모두 성공하면 자동으로 phase 1 pilot을 이어서 실행한다. 실패가 있으면 `set -e`로 중단되어 phase 1은 시작하지 않는다.

## 파일

- `run_planner_diag.py`: 단일 setting zero-shot 실행기.
- `launch_local_queue.py`: 한 머신의 여러 GPU에 job TSV를 분배하는 큐 런처.
- `launch_shared_queue.py`: FARM 공유 스토리지에서 여러 host가 하나의 pending queue를 같이 소비하는 런처. `--idle-poll-seconds`를 켜면 pending이 잠깐 없어도 running/offloaded row가 남아 있는 동안 worker가 살아 있다가 반납된 job을 다시 claim한다.
- `offload_shared_jobs.py`: FARM shared queue의 pending job을 CPS 같은 별도 스토리지 host로 중복 없이 offload/merge/release하는 유틸.
- `enrich_planning_deltas.py`: phase0 baseline을 기준으로 planning CSV에 delta/worse/coop-state columns를 후처리로 추가하는 유틸.
- `make_best_single_source.py`: 완료된 `clean_rsu_only`/`clean_vehicle_only` 결과에서 sample별 lower-ADE source를 골라 empirical `clean_best_single_source` baseline artifact를 만드는 유틸.
- `postprocess_done_runs.py`: shared queue의 `done` row만 aggregate/enrichment 대상으로 삼아 partial/final combined artifacts를 갱신하는 유틸.
- `make_jobs.py`: baseline/pilot/full job TSV 생성기.
- `jobs_phase0.tsv`: baseline source utility 평가.
- `jobs_phase0_farm1.tsv`, `jobs_phase0_farm9.tsv`: 중복 실행 방지용 host split.
- `jobs_phase1_pilot.tsv`: 대표 shift pilot sweep.
- `jobs_phase1_pilot_farm1.tsv`, `jobs_phase1_pilot_farm9.tsv`: pilot host split.
- `jobs_phase1_full.tsv`: full open-loop shift sweep 전체 job.
- `jobs_phase1_full_farm_shared.tsv`: FARM 공유 queue용 full sweep 전체 `300`개 job. FARM hosts가 같은 pending list에서 다음 job을 claim하므로 먼저 끝난 서버가 자동으로 더 가져간다.
- `jobs_objective_stage0.tsv` ... `jobs_objective_stage6.tsv`: 원 objective Stage 0-6을 그대로 펼친 job TSV.
- `jobs_objective_full.tsv`: Stage 0-6 objective job 전체 `428`개. 현재 running shared root와 분리된 다음 round용 job file이다.
- `jobs_phase1_full_cps.tsv`: CPS가 실제로 비어 있을 때 offload할 수 있는 optional split.
- `jobs_phase1_full_farm*.tsv`: static fallback/recovery split.
- `aggregate_results.py`: completed run의 `summary.json`을 모아 `combined/RESULTS.md` 생성.
- `bin/launch_*`: FARM1/FARM9용 기본 실행 스크립트.
- `bin/monitor_cps_offload.sh`: SSH로 FARM shared queue와 CPS를 연결해 free CPS GPU에 job을 자동 offload하는 controller용 monitor.
- `bin/monitor_objective_chain.sh`: 현재 FARM shared queue가 drain되면 `jobs_objective_full.tsv` objective queue를 FARM/CPS에 자동으로 이어서 띄우는 controller용 monitor.
- `bin/monitor_done_postprocess.sh`: FARM shared queue의 completed run만 주기적으로 aggregate/enrich하는 monitor.
- `bin/launch_farm_shared_backstop_waiters.sh`: 이미 떠 있는 old FARM launcher가 종료된 뒤에도 같은 shared queue로 다시 붙도록 FARM2/6/7/8/9 GPU별 waiters를 설치하는 controller용 helper.
- `bin/watch_cps_offload_batch.sh`: CPS offload batch가 launch된 뒤 monitor가 중단됐을 때 completion merge/release를 이어받는 recovery watcher.
- `EXPERIMENT_TODO.md`: machine layout, config, phase별 TODO, log/result 경로 정리.

## Phase Chaining

기본 phase 0 launcher는 다음 순서로 실행합니다.

```text
phase0 split jobs -> aggregate phase0 -> phase1 pilot split jobs -> aggregate phase1
```

자동 phase 1을 끄고 phase 0만 돌릴 때:

```bash
RUN_PHASE1_AFTER=0 bash experiments/v2xverse_codriving_diag/bin/launch_phase0_farm1.sh
```

## 실행 예시

FARM1 phase 0:

```bash
ssh FARM1
cd /home/jy/adas/external/V2Xverse
nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase0_farm1.sh \
  > experiments/v2xverse_codriving_diag/results/phase0_farm1_launcher.log 2>&1 &
```

FARM9 phase 0:

```bash
ssh FARM9
cd /home/jy/adas/external/V2Xverse
nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase0_farm9.sh \
  > experiments/v2xverse_codriving_diag/results/phase0_farm9_launcher.log 2>&1 &
```

Pilot을 작은 sample 수로 먼저 돌릴 때:

```bash
V2X_MAX_SAMPLES=128 nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase1_pilot_farm1.sh \
  > experiments/v2xverse_codriving_diag/results/phase1_pilot_farm1_launcher.log 2>&1 &
```

CPS에서 GPU가 비는 즉시 phase 1 pilot을 시작하려면:

```bash
cd /data/adas/e2e/external/V2Xverse
nohup bash experiments/v2xverse_codriving_diag/bin/wait_launch_phase1_pilot_cps.sh \
  > /data/adas/e2e/experiments/v2xverse_codriving_diag/results/phase1_pilot_cps_waiter.log 2>&1 &
```

기본 free GPU 기준은 memory free `>=20000MiB`, utilization `<=20%`입니다. 필요하면 `V2X_MIN_FREE_MEM_MIB`, `V2X_MAX_USED_MEM_MIB`, `V2X_FREE_UTIL_LIMIT_PCT`, `V2X_MAX_GPUS`로 조정합니다.

Full sweep을 돌릴 때 기본 방식은 FARM shared queue입니다. 정적으로 host별 job 수를 고정하지 않고, FARM2/6/7/8/9와 나중에 비는 FARM1이 같은 pending queue를 소비합니다. 먼저 끝난 host/GPU worker가 다음 pending row를 계속 claim하므로, 특정 서버에 미리 배정된 몫이 끝났다고 놀지 않습니다.

재분배 원칙은 다음과 같습니다. FARM 쪽은 같은 `shared_queue_status.csv`를 보므로 완료가 빠른 GPU가 바로 다음 pending row를 가져갑니다. CPS 쪽은 `/data`가 별도라 직접 lock을 공유하지 않고, monitor가 free GPU마다 FARM pending row를 `offloaded`로 lease한 뒤 CPS에서 실행하고 완료 결과를 FARM root로 복사/merge합니다. FARM worker는 기본 `V2X_SHARED_IDLE_POLL_SECONDS=300`으로 큐가 완전히 끝나기 전까지 종료하지 않으므로, CPS 실패/release 등으로 pending row가 다시 생겨도 idle FARM GPU가 다시 붙을 수 있습니다. 이미 패치 전 launcher가 떠 있는 queue에는 `launch_farm_shared_backstop_waiters.sh`를 별도로 걸어 두면 기존 launcher가 종료된 뒤 GPU별 waiter가 같은 queue로 재합류합니다.

```bash
cd /home/jy/adas/external/V2Xverse
export OUT_ROOT=/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm_shared_<stamp>
V2X_HOST_TAG=farm2 V2X_GPU_LIST=0,1 nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm_shared.sh \
  > experiments/v2xverse_codriving_diag/results/phase1_full_farm2_launcher.log 2>&1 &
V2X_HOST_TAG=farm6 V2X_GPU_LIST=0,1,2 nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm_shared.sh \
  > experiments/v2xverse_codriving_diag/results/phase1_full_farm6_launcher.log 2>&1 &
V2X_HOST_TAG=farm7 V2X_GPU_LIST=0,1,2 nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm_shared.sh \
  > experiments/v2xverse_codriving_diag/results/phase1_full_farm7_launcher.log 2>&1 &
V2X_HOST_TAG=farm8 V2X_GPU_LIST=0,1,2,3 nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm_shared.sh \
  > experiments/v2xverse_codriving_diag/results/phase1_full_farm8_launcher.log 2>&1 &
V2X_HOST_TAG=farm9 V2X_GPU_LIST=1,2 nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm_shared.sh \
  > experiments/v2xverse_codriving_diag/results/phase1_full_farm9_launcher.log 2>&1 &
V2X_HOST_TAG=farm1 V2X_ALLOWED_GPUS=1,2,3 V2X_MIN_GPUS=3 nohup bash experiments/v2xverse_codriving_diag/bin/wait_launch_phase1_full_farm_shared.sh \
  > experiments/v2xverse_codriving_diag/results/phase1_full_farm1_waiter.log 2>&1 &
```

이미 실행 중인 shared queue에 backstop waiters를 추가할 때:

```bash
OUT_ROOT=/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm_shared_<stamp> \
bash experiments/v2xverse_codriving_diag/bin/launch_farm_shared_backstop_waiters.sh
```

원 objective 전체 Stage 0-6을 새 root에서 돌릴 때는 `JOB_FILE`만 objective TSV로 바꿉니다.

```bash
export OUT_ROOT=/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/objective_full_farm_shared_<stamp>
export JOB_FILE=experiments/v2xverse_codriving_diag/jobs_objective_full.tsv
V2X_HOST_TAG=farm8 V2X_GPU_LIST=0,1,2,3 nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm_shared.sh \
  > experiments/v2xverse_codriving_diag/results/objective_full_farm8_launcher.log 2>&1 &
```

CPS에서 full sweep split을 GPU가 비는 즉시 시작하려면:

```bash
cd /data/adas/e2e/external/V2Xverse
nohup bash experiments/v2xverse_codriving_diag/bin/wait_launch_phase1_full_cps.sh \
  > /data/adas/e2e/experiments/v2xverse_codriving_diag/results/phase1_full_cps_waiter.log 2>&1 &
```

주의: FARM shared queue가 이미 전체 `300`개를 소비 중이면 CPS split을 동시에 돌리지 않습니다. CPS가 비었고 FARM에서 일부 pending job을 떼어낼 때만 CPS split을 사용합니다.

기본 full sweep 운영은 shared queue launcher를 사용합니다. Host별 split TSV launch script는 shared queue가 깨졌을 때의 recovery/offload용입니다. 운영 중에는 split 결과를 그대로 믿지 않고, idle GPU가 생기면 같은 shared queue에서 남은 pending job을 다시 가져가는 work-stealing 방식으로 돌립니다.

FARM shared queue에서 CPS로 job을 옮길 때는 먼저 FARM 큐에서 pending row를 `offloaded`로 잠급니다. 예시는 `8`개 job을 CPS로 넘기는 경우입니다.

```bash
cd /home/jy/adas/external/V2Xverse
QUEUE_ROOT=/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm_shared_<stamp>
BATCH=$(date +%Y%m%d_%H%M%S)
python experiments/v2xverse_codriving_diag/offload_shared_jobs.py claim \
  --queue-root "$QUEUE_ROOT" \
  --jobs experiments/v2xverse_codriving_diag/jobs_phase1_full_farm_shared.tsv \
  --count 8 \
  --out-jobs experiments/v2xverse_codriving_diag/results/jobs_phase1_full_cps_offload_$BATCH.tsv \
  --host-id cps \
  --remote-out-root /data/adas/e2e/experiments/v2xverse_codriving_diag/results/phase1_full_cps_offload_$BATCH
scp experiments/v2xverse_codriving_diag/results/jobs_phase1_full_cps_offload_$BATCH.tsv \
  cps_workstation:/data/adas/e2e/external/V2Xverse/experiments/v2xverse_codriving_diag/jobs_phase1_full_cps_offload_$BATCH.tsv
```

CPS에서는 복사된 TSV만 실행합니다.

```bash
cd /data/adas/e2e/external/V2Xverse
JOB_FILE=experiments/v2xverse_codriving_diag/jobs_phase1_full_cps_offload_$BATCH.tsv \
OUT_ROOT=/data/adas/e2e/experiments/v2xverse_codriving_diag/results/phase1_full_cps_offload_$BATCH \
V2X_GPU_LIST=0 \
nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase1_full_cps.sh \
  > /data/adas/e2e/experiments/v2xverse_codriving_diag/results/phase1_full_cps_offload_$BATCH.log 2>&1 &
```

CPS 실행이 끝나면 `launcher_status.csv`를 FARM 쪽으로 가져와 shared queue에 merge합니다.

```bash
scp cps_workstation:/data/adas/e2e/experiments/v2xverse_codriving_diag/results/phase1_full_cps_offload_$BATCH/launcher_status.csv \
  /home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/launcher_status_cps_offload_$BATCH.csv
python experiments/v2xverse_codriving_diag/offload_shared_jobs.py merge \
  --queue-root "$QUEUE_ROOT" \
  --launcher-status experiments/v2xverse_codriving_diag/results/launcher_status_cps_offload_$BATCH.csv \
  --host-id cps
```

CPS launch 전 문제가 생기면 `release`로 offloaded row를 다시 FARM pending queue에 돌려놓습니다.

```bash
python experiments/v2xverse_codriving_diag/offload_shared_jobs.py release \
  --queue-root "$QUEUE_ROOT" \
  --host-id cps
```

Controller host에서 백그라운드 monitor를 걸면 CPS GPU가 비는 순간 위 절차를 자동으로 수행합니다. Monitor는 이미 실행 중인 CPS offload GPU를 제외하고 새 free GPU만 고른 뒤, 기본값으로 GPU마다 독립 batch를 만들어 각 GPU당 `1`개 job만 claim합니다. Launch 후 batch 종료를 blocking wait하지 않고 다음 loop로 돌아가므로, CPS 한쪽 GPU가 먼저 끝나면 다른 GPU의 batch가 아직 running이어도 해당 GPU만 새 job을 다시 claim할 수 있습니다. 매 loop에서 이미 offload된 CPS batch의 `launcher_status.csv`도 확인해 `running`/`done`/`failed` row를 FARM shared queue로 partial merge합니다. 완료된 CPS run directory는 `done` merge 전에 FARM shared result root로 복사합니다. Inactive CPS batch에서 `launcher_status.csv`에 일부 claimed row가 빠진 경우 해당 missing row는 FARM pending queue로 release합니다. `V2X_CPS_OFFLOAD_JOBS_PER_GPU`, `V2X_CPS_OFFLOAD_MAX_JOBS_PER_BATCH`, `V2X_CPS_OFFLOAD_ONE_BATCH_PER_GPU`로 batch depth와 GPU별 batch 분리를 조정할 수 있지만, tail idle을 줄이려면 기본 `1`을 유지합니다.

```bash
QUEUE_ROOT=/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm_shared_<stamp> \
nohup bash experiments/v2xverse_codriving_diag/bin/monitor_cps_offload.sh \
  > experiments/v2xverse_codriving_diag/results/monitor_cps_offload_<stamp>.log 2>&1 &
```

현재 controller Mac에서는 LaunchAgent로 monitor를 올려 둡니다.

```bash
launchctl print gui/$(id -u)/com.jy.v2x.cps-offload
tail -f /tmp/v2x_cps_offload_monitor_launchd.log
```

LaunchAgent wrapper는 아래 controller-local state files를 읽어 active FARM queue와 job file을 정합니다. Objective chain monitor가 current full queue 완료 후 이 파일들을 objective queue로 갱신합니다.

```text
/Users/jy/.codex/v2x_cps_offload_queue_root
/Users/jy/.codex/v2x_cps_offload_jobs_file
/Users/jy/.codex/v2x_cps_offload_prefix
```

Monitor가 claim/launch 이후 끊긴 batch는 다음 monitor loop에서 자동 recovery 대상이 됩니다. 별도로 감시해야 하면 watcher로 merge/release를 이어받을 수 있습니다.

```bash
BATCH=20260707_130301 \
QUEUE_ROOT=/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm_shared_<stamp> \
nohup bash experiments/v2xverse_codriving_diag/bin/watch_cps_offload_batch.sh \
  > /tmp/v2x_cps_offload_20260707_130301_watcher.log 2>&1 &
```

Current `300`-job full queue가 끝나면 objective `428`-job full queue를 자동으로 이어서 띄우려면 controller에서 chain monitor를 실행합니다.

```bash
CURRENT_QUEUE_ROOT=/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm_shared_<stamp> \
nohup bash experiments/v2xverse_codriving_diag/bin/monitor_objective_chain.sh \
  > /tmp/v2x_objective_chain_<stamp>.log 2>&1 &
```

Completed run postprocess는 FARM shared result root에서 주기적으로 돌릴 수 있습니다. 이 monitor는 `shared_queue_status.csv`에서 `done`인 run만 읽어 `combined/summary.csv`, `combined/RESULTS.md`, `combined/planning_enriched_done.csv`, `combined/postprocess_status.json`을 갱신합니다.

```bash
QUEUE_ROOT=/home/jy/adas/external/V2Xverse/experiments/v2xverse_codriving_diag/results/phase1_full_farm_shared_<stamp> \
nohup bash experiments/v2xverse_codriving_diag/bin/monitor_done_postprocess.sh \
  > experiments/v2xverse_codriving_diag/results/postprocess_phase1_full_<stamp>.log 2>&1 &
```

## wandb

기본값은 `WANDB_MODE=auto`입니다.

- `WANDB_API_KEY` 또는 `~/.netrc`가 있으면 online mode로 기록한다.
- 없으면 offline mode로 기록한다.
- 강제로 offline으로 돌리려면 `WANDB_MODE=offline`을 지정한다.

프로젝트 기본값:

```bash
export WANDB_PROJECT=v2xverse-codriving-zero-shot
```

## 결과 구조

각 run directory:

```text
manifest.csv
per_sample_planning.csv
per_sample_perception.csv
per_sample_agent.csv
summary.json
run.log
```

결과 취합:

```bash
python experiments/v2xverse_codriving_diag/aggregate_results.py \
  --root experiments/v2xverse_codriving_diag/results/<run_root>
```

생성물:

```text
combined/summary.csv
combined/RESULTS.md
```

Baseline 대비 delta/coop-state 필드 후처리:

```bash
python experiments/v2xverse_codriving_diag/make_best_single_source.py \
  --rsu-planning experiments/v2xverse_codriving_diag/results/phase0_farm1_20260706_085007/phase0_clean_rsu_only_seed0/per_sample_planning.csv \
  --cav-planning experiments/v2xverse_codriving_diag/results/phase0_farm1_20260706_085007/phase0_clean_vehicle_only_seed0/per_sample_planning.csv \
  --out-dir experiments/v2xverse_codriving_diag/results/phase0_empirical_baselines/phase0_clean_best_single_source_empirical_seed0

python experiments/v2xverse_codriving_diag/enrich_planning_deltas.py \
  --target-root experiments/v2xverse_codriving_diag/results/<run_root> \
  --baseline-root experiments/v2xverse_codriving_diag/results/phase0_farm1_20260706_085007 \
  --baseline-root experiments/v2xverse_codriving_diag/results/phase0_farm9_20260706_085007 \
  --baseline-root experiments/v2xverse_codriving_diag/results/phase0_empirical_baselines/phase0_clean_best_single_source_empirical_seed0 \
  --combined-out experiments/v2xverse_codriving_diag/results/<run_root>/combined/planning_enriched.csv
```

이 도구는 각 run directory에 `per_sample_planning_enriched.csv`를 만들고, `delta_ADE_vs_clean_all`, `delta_ADE_vs_ego`, `delta_ADE_vs_null_all`, `delta_ADE_vs_clean_best_single_source`, `worse_than_*`, `native_coop_state`, `shift_coop_state`를 채웁니다. Empirical best-source baseline은 post-hoc oracle baseline이며 재추론 결과가 아닙니다.
