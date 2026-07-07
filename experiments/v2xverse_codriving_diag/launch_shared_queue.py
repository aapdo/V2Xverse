#!/usr/bin/env python3
"""Run diagnostic jobs from a shared multi-host queue.

All FARM containers share the same V2Xverse checkout/results directory. This
launcher uses a small lock directory next to the status CSV so multiple hosts
can claim jobs without duplicate execution.
"""

import argparse
import csv
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from launch_local_queue import build_cmd, read_jobs


STATUS_FIELDS = [
    "run_id", "status", "host", "gpu", "started_at", "finished_at",
    "returncode", "log_path", "setting", "shift_family", "severity",
    "application_mode", "shift_seed",
]


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


class DirLock:
    def __init__(self, path, stale_seconds=600):
        self.path = Path(path)
        self.stale_seconds = stale_seconds

    def __enter__(self):
        while True:
            try:
                self.path.mkdir(parents=True)
                (self.path / "owner.txt").write_text(f"{os.uname().nodename} {os.getpid()} {time.time()}\n")
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                    if age > self.stale_seconds:
                        shutil.rmtree(self.path, ignore_errors=True)
                        continue
                except FileNotFoundError:
                    continue
                time.sleep(1)

    def __exit__(self, exc_type, exc, tb):
        shutil.rmtree(self.path, ignore_errors=True)


def write_status(path, rows):
    tmp = Path(str(path) + ".tmp")
    with tmp.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=STATUS_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in STATUS_FIELDS})
    tmp.replace(path)


def read_status(path):
    if not Path(path).exists():
        return []
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def initial_rows(jobs):
    rows = []
    for job in jobs:
        rows.append({
            "run_id": job["run_id"],
            "status": "pending",
            "setting": job.get("setting", ""),
            "shift_family": job.get("shift_family", ""),
            "severity": job.get("severity", ""),
            "application_mode": job.get("application_mode", ""),
            "shift_seed": job.get("shift_seed", ""),
        })
    return rows


def load_or_init_status(args, jobs):
    status_path = Path(args.out_root) / "shared_queue_status.csv"
    lock_path = Path(args.out_root) / "shared_queue.lock"
    with DirLock(lock_path, args.lock_stale_seconds):
        rows = read_status(status_path)
        if not rows:
            rows = initial_rows(jobs)
            write_status(status_path, rows)
        return rows


def claim_job(args, gpu, jobs_by_id):
    status_path = Path(args.out_root) / "shared_queue_status.csv"
    lock_path = Path(args.out_root) / "shared_queue.lock"
    with DirLock(lock_path, args.lock_stale_seconds):
        rows = read_status(status_path)
        for row in rows:
            if row.get("status") == "pending":
                row.update({
                    "status": "running",
                    "host": args.host_id,
                    "gpu": gpu,
                    "started_at": now(),
                    "finished_at": "",
                    "returncode": "",
                })
                log_dir = Path(args.out_root) / "_launcher_logs"
                log_dir.mkdir(parents=True, exist_ok=True)
                row["log_path"] = str(log_dir / f"{row['run_id']}.{args.host_id}.gpu{gpu}.log")
                write_status(status_path, rows)
                return jobs_by_id[row["run_id"]], row["log_path"]
    return None, None


def finish_job(args, run_id, rc):
    status_path = Path(args.out_root) / "shared_queue_status.csv"
    lock_path = Path(args.out_root) / "shared_queue.lock"
    with DirLock(lock_path, args.lock_stale_seconds):
        rows = read_status(status_path)
        for row in rows:
            if row.get("run_id") == run_id and row.get("host") == args.host_id:
                row["status"] = "done" if rc == 0 else "failed"
                row["finished_at"] = now()
                row["returncode"] = rc
                break
        write_status(status_path, rows)


def worker(gpu, args, jobs_by_id):
    while True:
        job, log_path = claim_job(args, gpu, jobs_by_id)
        if job is None:
            return
        run_id = job["run_id"]
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(gpu)
        env["PYTHONPATH"] = f"{args.repo_root}:{env.get('PYTHONPATH', '')}"
        env["OMP_NUM_THREADS"] = str(args.omp_threads)
        if args.wandb_project:
            env["WANDB_PROJECT"] = args.wandb_project

        cmd = build_cmd(args, job, args.out_root)
        with open(log_path, "w") as fh:
            fh.write(" ".join(cmd) + "\n")
            fh.flush()
            proc = subprocess.Popen(cmd, cwd=args.repo_root, env=env, stdout=fh, stderr=subprocess.STDOUT)
            rc = proc.wait()
        finish_job(args, run_id, rc)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--gpus", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--host-id", default=os.uname().nodename)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--max-samples", default="")
    parser.add_argument("--shift-seed", type=int, default=0)
    parser.add_argument("--wandb-mode", choices=["auto", "online", "offline", "disabled"], default=os.environ.get("WANDB_MODE", "auto"))
    parser.add_argument("--wandb-project", default=os.environ.get("WANDB_PROJECT", "v2xverse-codriving-zero-shot"))
    parser.add_argument("--model-dir", dest="model_dir", default="checkpoints/codriving/perception")
    parser.add_argument("--planner-resume", dest="planner_resume", default="checkpoints/codriving/planner/codriving_planner.ckpt")
    parser.add_argument("--config-file", default="codriving/hypes_yaml/codriving/end2end_codriving.yaml")
    parser.add_argument("--log-interval", type=int, default=25)
    parser.add_argument("--wandb-log-interval", type=int, default=10)
    parser.add_argument("--omp-threads", type=int, default=8)
    parser.add_argument("--save-waypoints", action="store_true")
    parser.add_argument("--lock-stale-seconds", type=int, default=600)
    return parser.parse_args()


def main():
    args = parse_args()
    args.out_root = Path(args.out_root)
    args.out_root.mkdir(parents=True, exist_ok=True)
    jobs = read_jobs(args.jobs)
    load_or_init_status(args, jobs)
    jobs_by_id = {job["run_id"]: job for job in jobs}

    threads = []
    for gpu in [x.strip() for x in args.gpus.split(",") if x.strip()]:
        thread = threading.Thread(target=worker, args=(gpu, args, jobs_by_id), daemon=False)
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    main()
