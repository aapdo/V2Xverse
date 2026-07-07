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
- CPS는 dataset mirror가 준비되어 있지만, 현재 GPU가 다른 작업으로 점유되어 있으면 launcher 대상에서 제외한다.
- `launch_phase0_farm*.sh`는 phase 0가 모두 성공하면 자동으로 phase 1 pilot을 이어서 실행한다. 실패가 있으면 `set -e`로 중단되어 phase 1은 시작하지 않는다.

## 파일

- `run_planner_diag.py`: 단일 setting zero-shot 실행기.
- `launch_local_queue.py`: 한 머신의 여러 GPU에 job TSV를 분배하는 큐 런처.
- `make_jobs.py`: baseline/pilot/full job TSV 생성기.
- `jobs_phase0.tsv`: baseline source utility 평가.
- `jobs_phase0_farm1.tsv`, `jobs_phase0_farm9.tsv`: 중복 실행 방지용 host split.
- `jobs_phase1_pilot.tsv`: 대표 shift pilot sweep.
- `jobs_phase1_pilot_farm1.tsv`, `jobs_phase1_pilot_farm9.tsv`: pilot host split.
- `jobs_phase1_full.tsv`: full open-loop shift sweep 전체 job.
- `jobs_phase1_full_farm9.tsv`, `jobs_phase1_full_farm1.tsv`, `jobs_phase1_full_cps.tsv`: full sweep host split.
- `aggregate_results.py`: completed run의 `summary.json`을 모아 `combined/RESULTS.md` 생성.
- `bin/launch_*`: FARM1/FARM9용 기본 실행 스크립트.
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

기본 free GPU 기준은 memory used `<=2048MiB`, utilization `<=20%`입니다. 필요하면 `V2X_FREE_MEM_LIMIT_MIB`, `V2X_FREE_UTIL_LIMIT_PCT`, `V2X_MAX_GPUS`로 조정합니다.

Full sweep을 돌릴 때:

```bash
cd /home/jy/adas/external/V2Xverse
nohup bash experiments/v2xverse_codriving_diag/bin/launch_phase1_full_farm9.sh \
  > experiments/v2xverse_codriving_diag/results/phase1_full_farm9_launcher.log 2>&1 &
nohup bash experiments/v2xverse_codriving_diag/bin/wait_launch_phase1_full_farm1.sh \
  > experiments/v2xverse_codriving_diag/results/phase1_full_farm1_waiter.log 2>&1 &
```

CPS에서 full sweep split을 GPU가 비는 즉시 시작하려면:

```bash
cd /data/adas/e2e/external/V2Xverse
nohup bash experiments/v2xverse_codriving_diag/bin/wait_launch_phase1_full_cps.sh \
  > /data/adas/e2e/experiments/v2xverse_codriving_diag/results/phase1_full_cps_waiter.log 2>&1 &
```

기본 launch script는 host별 split TSV를 사용합니다. 전체 TSV를 한 머신에서 돌리고 싶으면 `JOB_FILE`을 override합니다.

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
