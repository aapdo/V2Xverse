#!/usr/bin/env python3
"""Build an empirical clean_best_single_source baseline from completed runs."""

import argparse
import csv
import json
import math
import statistics
import time
from pathlib import Path


def read_csv(path):
    with Path(path).open(newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows, fieldnames):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def key(row):
    sample_id = row.get("sample_id") or row.get("sample_idx") or ""
    if sample_id != "":
        return ("sample", sample_id)
    return ("route_frame", row.get("route_id") or row.get("scenario_id") or "", row.get("frame_id") or "")


def as_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def percentile(values, q):
    if not values:
        return None
    sorted_values = sorted(values)
    idx = max(0, min(len(sorted_values) - 1, math.ceil((q / 100.0) * len(sorted_values)) - 1))
    return sorted_values[idx]


def choose_best(rsu_row, cav_row):
    rsu_ade = as_float(rsu_row.get("ADE")) if rsu_row else None
    cav_ade = as_float(cav_row.get("ADE")) if cav_row else None
    if rsu_ade is None:
        return cav_row, "cav"
    if cav_ade is None:
        return rsu_row, "rsu"
    return (rsu_row, "rsu") if rsu_ade <= cav_ade else (cav_row, "cav")


def summarize(rows):
    ade = [as_float(row.get("ADE")) for row in rows]
    fde = [as_float(row.get("FDE")) for row in rows]
    ade = [x for x in ade if x is not None]
    fde = [x for x in fde if x is not None]
    return {
        "run_id": "phase0_clean_best_single_source_empirical_seed0",
        "setting": "clean_best_single_source",
        "shift_family": "none",
        "severity": "none",
        "application_mode": "none",
        "shift_seed": 0,
        "num_samples": len(rows),
        "mean_ADE": statistics.fmean(ade) if ade else None,
        "median_ADE": statistics.median(ade) if ade else None,
        "p90_ADE": percentile(ade, 90),
        "p95_ADE": percentile(ade, 95),
        "mean_FDE": statistics.fmean(fde) if fde else None,
        "p90_FDE": percentile(fde, 90),
        "p95_FDE": percentile(fde, 95),
        "elapsed_sec": 0.0,
        "source": "posthoc_min_ADE(clean_rsu_only, clean_vehicle_only)",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rsu-planning", required=True)
    parser.add_argument("--cav-planning", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    rsu_rows = read_csv(args.rsu_planning)
    cav_rows = read_csv(args.cav_planning)
    rsu_by_key = {key(row): row for row in rsu_rows}
    cav_by_key = {key(row): row for row in cav_rows}
    all_keys = sorted(set(rsu_by_key) | set(cav_by_key), key=str)

    out_rows = []
    counts = {"rsu": 0, "cav": 0, "missing": 0}
    for item_key in all_keys:
        best, source = choose_best(rsu_by_key.get(item_key), cav_by_key.get(item_key))
        if best is None:
            counts["missing"] += 1
            continue
        row = dict(best)
        row["run_id"] = "phase0_clean_best_single_source_empirical_seed0"
        row["setting"] = "clean_best_single_source"
        row["shift_family"] = "none"
        row["severity"] = "none"
        row["application_mode"] = "none"
        row["best_single_source"] = source
        row["best_single_source_basis"] = "min_ADE"
        out_rows.append(row)
        counts[source] += 1

    if not out_rows:
        raise SystemExit("no rows available for empirical best single-source baseline")

    fieldnames = list(out_rows[0].keys())
    for field in ["best_single_source", "best_single_source_basis"]:
        if field not in fieldnames:
            fieldnames.append(field)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "per_sample_planning.csv", out_rows, fieldnames)
    summary = summarize(out_rows)
    summary["best_single_source_counts"] = counts
    summary["created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    write_csv(out_dir / "manifest.csv", [{
        "run_id": summary["run_id"],
        "date": summary["created_at"],
        "dataset": "V2Xverse",
        "task": "posthoc_best_single_source",
        "model": "CoDriving",
        "setting": "clean_best_single_source",
        "source": summary["source"],
        "rsu_planning": args.rsu_planning,
        "cav_planning": args.cav_planning,
    }], ["run_id", "date", "dataset", "task", "model", "setting", "source", "rsu_planning", "cav_planning"])
    print(out_dir)
    print(f"rows={len(out_rows)} counts={counts}")


if __name__ == "__main__":
    main()
