#!/usr/bin/env python3
"""Run V2Xverse diagnostic jobs on a local multi-GPU host."""

import argparse
import csv
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path


def read_jobs(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def write_status(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_id", "gpu", "status", "started_at", "finished_at", "returncode",
        "log_path", "setting", "shift_family", "severity", "application_mode",
        "shift_seed",
    ]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def build_cmd(args, job, out_root):
    script = Path(args.repo_root) / "experiments" / "v2xverse_codriving_diag" / "run_planner_diag.py"
    cmd = [
        args.python,
        str(script),
        "--run-id", job["run_id"],
        "--setting", job.get("setting") or "clean_all",
        "--shift-family", job.get("shift_family") or "none",
        "--severity", job.get("severity") or "none",
        "--application-mode", job.get("application_mode") or "none",
        "--shift-seed", str(job.get("shift_seed") or args.shift_seed),
        "--out-root", str(out_root),
        "--workers", str(args.workers),
        "--wandb-mode", args.wandb_mode,
        "--wandb-project", args.wandb_project,
        "--log-interval", str(args.log_interval),
        "--wandb-log-interval", str(args.wandb_log_interval),
        "--model_dir", args.model_dir,
        "--planner_resume", args.planner_resume,
        "--config-file", args.config_file,
    ]
    max_samples = job.get("max_samples") or args.max_samples
    if max_samples:
        cmd += ["--max-samples", str(max_samples)]
    if args.save_waypoints:
        cmd += ["--save-waypoints"]
    return cmd


def worker(gpu, args, jobs_q, status_rows, status_lock, out_root):
    while True:
        try:
            job = jobs_q.get_nowait()
        except queue.Empty:
            return

        run_id = job["run_id"]
        log_dir = out_root / "_launcher_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{run_id}.gpu{gpu}.log"
        row = {
            "run_id": run_id,
            "gpu": gpu,
            "status": "running",
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "log_path": str(log_path),
            "setting": job.get("setting", ""),
            "shift_family": job.get("shift_family", ""),
            "severity": job.get("severity", ""),
            "application_mode": job.get("application_mode", ""),
            "shift_seed": job.get("shift_seed", ""),
        }
        with status_lock:
            status_rows.append(row)
            write_status(out_root / "launcher_status.csv", status_rows)

        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(gpu)
        env["PYTHONPATH"] = f"{args.repo_root}:{env.get('PYTHONPATH', '')}"
        env["OMP_NUM_THREADS"] = str(args.omp_threads)
        if args.wandb_project:
            env["WANDB_PROJECT"] = args.wandb_project

        cmd = build_cmd(args, job, out_root)
        if args.dry_run:
            rc = 0
            with log_path.open("w") as fh:
                fh.write("DRY RUN\n")
                fh.write(" ".join(cmd) + "\n")
        else:
            with log_path.open("w") as fh:
                fh.write(" ".join(cmd) + "\n")
                fh.flush()
                proc = subprocess.Popen(cmd, cwd=args.repo_root, env=env, stdout=fh, stderr=subprocess.STDOUT)
                rc = proc.wait()

        row["status"] = "done" if rc == 0 else "failed"
        row["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        row["returncode"] = rc
        with status_lock:
            write_status(out_root / "launcher_status.csv", status_rows)
        jobs_q.task_done()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--gpus", required=True, help="Comma-separated physical GPU ids, e.g. 1,2,3")
    parser.add_argument("--out-root", required=True)
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
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    jobs = read_jobs(args.jobs)
    jobs_q = queue.Queue()
    for job in jobs:
        jobs_q.put(job)

    status_rows = []
    status_lock = threading.Lock()
    threads = []
    for gpu in [x.strip() for x in args.gpus.split(",") if x.strip()]:
        thread = threading.Thread(target=worker, args=(gpu, args, jobs_q, status_rows, status_lock, out_root), daemon=False)
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    write_status(out_root / "launcher_status.csv", status_rows)
    failed = [r for r in status_rows if r.get("status") == "failed"]
    if failed:
        raise SystemExit(f"{len(failed)} jobs failed")


if __name__ == "__main__":
    main()
