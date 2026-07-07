#!/usr/bin/env python3
"""Post-process completed shared-queue diagnostic runs only."""

import argparse
import csv
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import aggregate_results
import enrich_planning_deltas


def read_status(path):
    with Path(path).open(newline="") as fh:
        return list(csv.DictReader(fh))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def load_summary(run_dir):
    data = json.loads((Path(run_dir) / "summary.json").read_text())
    data["run_dir"] = str(run_dir)
    return data


def write_results_md(path, root, rows, missing_done):
    body = [
        f"# V2Xverse CoDriving Diagnostic Results: {Path(root).name}",
        "",
        f"- result root: `{root}`",
        f"- completed runs with summaries: `{len(rows)}`",
        f"- completed queue rows missing result dirs: `{len(missing_done)}`",
        "",
        "## Summary",
        "",
        aggregate_results.md_table(rows) if rows else "No completed runs found.",
        "",
        "## Notes",
        "",
        "- This file is generated from `shared_queue_status.csv` rows whose status is `done`.",
        "- Per-sample details are in each run directory: `per_sample_planning.csv`, `per_sample_perception.csv`, `per_sample_agent.csv`.",
    ]
    if missing_done:
        body.extend(["", "## Missing Completed Result Dirs", ""])
        body.extend(f"- `{run_id}`" for run_id in missing_done)
    Path(path).write_text("\n".join(body))


def collect_done_dirs(queue_root, status_rows):
    root = Path(queue_root)
    done_ids = [row["run_id"] for row in status_rows if row.get("status") == "done"]
    run_dirs = []
    missing = []
    for run_id in done_ids:
        run_dir = root / run_id
        if (run_dir / "summary.json").exists() and (run_dir / "per_sample_planning.csv").exists():
            run_dirs.append(run_dir)
        else:
            missing.append(run_id)
    return done_ids, run_dirs, missing


def status_counts(rows):
    counts = {}
    for row in rows:
        status = row.get("status", "")
        counts[status] = counts.get(status, 0) + 1
    return counts


def enrich_done_runs(run_dirs, baseline_roots, combined_out, threshold):
    if not run_dirs:
        return 0, 0, {}
    baselines, baseline_counts = enrich_planning_deltas.build_baseline_index(baseline_roots)
    combined_rows = []
    combined_fields = []
    for run_dir in run_dirs:
        _, rows, fields = enrich_planning_deltas.enrich_run(run_dir, baselines, threshold)
        combined_rows.extend(rows)
        for field in fields:
            if field not in combined_fields:
                combined_fields.append(field)
    if combined_rows:
        enrich_planning_deltas.write_csv(combined_out, combined_rows, combined_fields)
    missing_baseline = sum(1 for row in combined_rows if row.get("baseline_key_status") != "ok")
    return len(combined_rows), missing_baseline, baseline_counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue-root", required=True)
    parser.add_argument("--baseline-root", action="append", required=True)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--final-on-drain", action="store_true")
    args = parser.parse_args()

    queue_root = Path(args.queue_root)
    status_path = queue_root / "shared_queue_status.csv"
    rows = read_status(status_path)
    counts = status_counts(rows)
    done_ids, run_dirs, missing_done = collect_done_dirs(queue_root, rows)

    combined_dir = queue_root / "combined"
    combined_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = [load_summary(run_dir) for run_dir in run_dirs]
    aggregate_results.write_csv(combined_dir / "summary.csv", summary_rows)
    write_results_md(combined_dir / "RESULTS.md", queue_root, summary_rows, missing_done)

    enriched_rows, missing_baseline, baseline_counts = enrich_done_runs(
        run_dirs,
        [Path(root) for root in args.baseline_root],
        combined_dir / "planning_enriched_done.csv",
        args.threshold,
    )

    active = sum(counts.get(status, 0) for status in ("pending", "running", "offloaded"))
    if args.final_on_drain and active == 0 and (combined_dir / "planning_enriched_done.csv").exists():
        final_path = combined_dir / "planning_enriched.csv"
        final_path.write_bytes((combined_dir / "planning_enriched_done.csv").read_bytes())

    status = {
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "queue_root": str(queue_root),
        "status_counts": counts,
        "done_rows": len(done_ids),
        "done_result_dirs": len(run_dirs),
        "missing_done_result_dirs": missing_done,
        "summary_rows": len(summary_rows),
        "enriched_rows": enriched_rows,
        "missing_baseline_rows": missing_baseline,
        "baseline_rows": baseline_counts,
        "active_rows": active,
    }
    write_json(combined_dir / "postprocess_status.json", status)
    print(json.dumps(status, sort_keys=True))


if __name__ == "__main__":
    main()
