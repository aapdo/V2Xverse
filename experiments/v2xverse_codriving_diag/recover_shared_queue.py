#!/usr/bin/env python3
"""Recover abandoned rows in a shared FARM queue.

This is an operator tool for cases where a worker process has already been
checked dead but `shared_queue_status.csv` still contains stale `running` rows.
It preserves old run logs before allowing launchers to claim the jobs again.
"""

import argparse
import time
from pathlib import Path

from launch_shared_queue import DirLock, read_status, write_status


def parse_started_at(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S",):
        try:
            return time.mktime(time.strptime(value, fmt))
        except ValueError:
            pass
    return None


def log_age_seconds(row, now):
    log_path = row.get("log_path", "")
    if log_path:
        path = Path(log_path)
        if path.exists():
            return int(now - path.stat().st_mtime)
    started = parse_started_at(row.get("started_at", ""))
    if started is None:
        return None
    return int(now - started)


def archive_log(row, stamp):
    log_path = row.get("log_path", "")
    if not log_path:
        return ""
    path = Path(log_path)
    if not path.exists():
        return ""
    target = path.with_name(f"{path.name}.abandoned_{stamp}")
    idx = 1
    while target.exists():
        target = path.with_name(f"{path.name}.abandoned_{stamp}.{idx}")
        idx += 1
    path.rename(target)
    return str(target)


def eligible(row, args, now):
    if row.get("status") != "running":
        return False, "not-running", None
    if args.host and row.get("host") != args.host:
        return False, "host-filter", None
    if args.run_id and row.get("run_id") != args.run_id:
        return False, "run-filter", None
    age = log_age_seconds(row, now)
    if age is None:
        return False, "unknown-age", None
    if age < args.stale_seconds:
        return False, "not-stale", age
    return True, "stale", age


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue-root", required=True)
    parser.add_argument("--stale-seconds", type=int, default=900)
    parser.add_argument("--lock-stale-seconds", type=int, default=600)
    parser.add_argument("--host", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--mark", choices=("pending", "failed"), default="pending")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--no-archive-log", action="store_true")
    args = parser.parse_args()

    queue_root = Path(args.queue_root)
    status_path = queue_root / "shared_queue_status.csv"
    lock_path = queue_root / "shared_queue.lock"
    now = time.time()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    recovered = []
    skipped = []

    with DirLock(lock_path, args.lock_stale_seconds):
        rows = read_status(status_path)
        for row in rows:
            ok, reason, age = eligible(row, args, now)
            if not ok:
                if row.get("status") == "running":
                    skipped.append((row.get("run_id", ""), reason, age))
                continue
            archived = ""
            if args.apply and not args.no_archive_log:
                archived = archive_log(row, stamp)
            recovered.append((row.get("run_id", ""), row.get("host", ""), row.get("gpu", ""), age, archived))
            if args.apply:
                if args.mark == "pending":
                    row["status"] = "pending"
                    row["host"] = ""
                    row["gpu"] = ""
                    row["started_at"] = ""
                    row["finished_at"] = ""
                    row["returncode"] = ""
                    row["log_path"] = ""
                else:
                    row["status"] = "failed"
                    row["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    row["returncode"] = "abandoned"
        if args.apply:
            write_status(status_path, rows)

    action = "recovered" if args.apply else "would_recover"
    print(f"{action}={len(recovered)} mark={args.mark} stale_seconds={args.stale_seconds}")
    for run_id, host, gpu, age, archived in recovered:
        suffix = f" archived={archived}" if archived else ""
        print(f"{run_id} host={host} gpu={gpu} stale_s={age}{suffix}")
    if skipped:
        print(f"skipped_running={len(skipped)}")
        for run_id, reason, age in skipped[:20]:
            print(f"{run_id} reason={reason} stale_s={age}")


if __name__ == "__main__":
    main()
