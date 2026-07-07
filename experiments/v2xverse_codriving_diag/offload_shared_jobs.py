#!/usr/bin/env python3
"""Claim shared FARM queue jobs for execution on a separate storage host.

FARM hosts share the queue CSV directly, but CPS uses separate /data storage.
This helper atomically marks FARM pending rows as offloaded, writes a TSV that
can be copied to CPS, and later merges CPS launcher_status.csv back into the
FARM queue status.
"""

import argparse
import csv
import os
import shutil
import sys
import time
from pathlib import Path


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
                owner = f"{os.uname().nodename} {os.getpid()} {time.time()}\n"
                (self.path / "owner.txt").write_text(owner)
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


def read_csv(path):
    with Path(path).open(newline="") as fh:
        return list(csv.DictReader(fh))


def write_status(path, rows):
    tmp = Path(str(path) + ".tmp")
    with tmp.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=STATUS_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in STATUS_FIELDS})
    tmp.replace(path)


def read_jobs(path):
    with Path(path).open(newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        return reader.fieldnames or [], list(reader)


def write_jobs(path, fieldnames, jobs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, delimiter="\t", fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(jobs)


def queue_paths(queue_root):
    root = Path(queue_root)
    return root / "shared_queue_status.csv", root / "shared_queue.lock"


def cmd_claim(args):
    status_path, lock_path = queue_paths(args.queue_root)
    fieldnames, jobs = read_jobs(args.jobs)
    jobs_by_id = {job["run_id"]: job for job in jobs}
    claimed = []

    with DirLock(lock_path, args.lock_stale_seconds):
        rows = read_csv(status_path)
        for row in rows:
            if len(claimed) >= args.count:
                break
            if row.get("status") != "pending":
                continue
            job = jobs_by_id.get(row.get("run_id"))
            if job is None:
                raise SystemExit(f"run_id missing from jobs TSV: {row.get('run_id')}")
            row.update({
                "status": "offloaded",
                "host": args.host_id,
                "gpu": "",
                "started_at": now(),
                "finished_at": "",
                "returncode": "",
                "log_path": args.remote_out_root or "",
            })
            claimed.append(job)
        write_status(status_path, rows)

    write_jobs(args.out_jobs, fieldnames, claimed)
    print(f"claimed={len(claimed)} out_jobs={args.out_jobs}")
    if len(claimed) < args.count and args.require_count:
        raise SystemExit(f"only claimed {len(claimed)} of requested {args.count}")


def cmd_merge(args):
    status_path, lock_path = queue_paths(args.queue_root)
    launcher_rows = read_csv(args.launcher_status)
    launcher_by_id = {row["run_id"]: row for row in launcher_rows}
    updated = 0

    with DirLock(lock_path, args.lock_stale_seconds):
        rows = read_csv(status_path)
        for row in rows:
            launcher = launcher_by_id.get(row.get("run_id"))
            if launcher is None:
                continue
            if row.get("status") not in {"offloaded", "running", "pending"} and not args.force:
                continue
            status = launcher.get("status", "")
            if status not in {"running", "done", "failed"}:
                continue
            row.update({
                "status": status,
                "host": args.host_id or row.get("host") or "cps",
                "gpu": launcher.get("gpu", ""),
                "started_at": launcher.get("started_at", row.get("started_at", "")),
                "finished_at": launcher.get("finished_at", row.get("finished_at", "")),
                "returncode": launcher.get("returncode", row.get("returncode", "")),
                "log_path": launcher.get("log_path", row.get("log_path", "")),
            })
            updated += 1
        write_status(status_path, rows)

    print(f"merged={updated} launcher_status={args.launcher_status}")


def cmd_release(args):
    status_path, lock_path = queue_paths(args.queue_root)
    run_ids = set(args.run_id or [])
    if args.run_id_file:
        with Path(args.run_id_file).open() as fh:
            run_ids.update(line.strip() for line in fh if line.strip())
    statuses = set(args.status)
    released = 0

    with DirLock(lock_path, args.lock_stale_seconds):
        rows = read_csv(status_path)
        for row in rows:
            if row.get("status") not in statuses:
                continue
            if args.host_id and row.get("host") != args.host_id:
                continue
            if run_ids and row.get("run_id") not in run_ids:
                continue
            row.update({
                "status": "pending",
                "host": "",
                "gpu": "",
                "started_at": "",
                "finished_at": "",
                "returncode": "",
                "log_path": "",
            })
            released += 1
        write_status(status_path, rows)

    print(f"released={released}")


def build_parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    claim = sub.add_parser("claim", help="mark pending jobs offloaded and write a CPS TSV")
    claim.add_argument("--queue-root", required=True)
    claim.add_argument("--jobs", required=True)
    claim.add_argument("--count", type=int, required=True)
    claim.add_argument("--out-jobs", required=True)
    claim.add_argument("--host-id", default="cps")
    claim.add_argument("--remote-out-root", default="")
    claim.add_argument("--require-count", action="store_true")
    claim.add_argument("--lock-stale-seconds", type=int, default=600)
    claim.set_defaults(func=cmd_claim)

    merge = sub.add_parser("merge", help="merge CPS launcher_status.csv into shared queue")
    merge.add_argument("--queue-root", required=True)
    merge.add_argument("--launcher-status", required=True)
    merge.add_argument("--host-id", default="cps")
    merge.add_argument("--force", action="store_true")
    merge.add_argument("--lock-stale-seconds", type=int, default=600)
    merge.set_defaults(func=cmd_merge)

    release = sub.add_parser("release", help="return offloaded/failed jobs to pending")
    release.add_argument("--queue-root", required=True)
    release.add_argument("--host-id", default="")
    release.add_argument("--status", action="append", default=["offloaded"])
    release.add_argument("--run-id", action="append")
    release.add_argument("--run-id-file")
    release.add_argument("--lock-stale-seconds", type=int, default=600)
    release.set_defaults(func=cmd_release)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
