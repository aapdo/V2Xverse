#!/usr/bin/env python3
"""Add baseline-delta planning columns to diagnostic result CSVs.

This is intentionally post-hoc: baseline runs may live in separate roots
because FARM1/FARM9 split phase 0, and full sweeps can be aggregated after the
fact without rerunning expensive inference.
"""

import argparse
import csv
import json
from pathlib import Path


DELTA_FIELDS = [
    "delta_ADE_vs_clean_all",
    "delta_ADE_vs_ego",
    "delta_ADE_vs_null_all",
    "delta_ADE_vs_clean_best_single_source",
    "worse_than_clean_all",
    "worse_than_ego",
    "worse_than_null_all",
    "worse_than_clean_best_single_source",
    "delta_ADE_gt_0p2",
    "delta_ADE_gt_0p5",
    "delta_ADE_gt_1p0",
    "native_coop_state",
    "shift_coop_state",
    "rsu_native_state",
    "cav_native_state",
    "rsu_shift_state",
    "cav_shift_state",
    "baseline_clean_all_ADE",
    "baseline_ego_ADE",
    "baseline_null_all_ADE",
    "baseline_clean_best_single_source_ADE",
    "baseline_key_status",
]


def canonical_setting(value):
    value = value or ""
    aliases = {
        "ego_only": "ego",
        "clean_all": "clean_all",
        "clean_rsu_only": "clean_rsu_only",
        "clean_vehicle_only": "clean_vehicle_only",
        "clean_cav_only": "clean_vehicle_only",
        "clean_best_single_source": "clean_best_single_source",
        "null_all_missing_flag": "null_all",
        "null_all_image": "null_all",
    }
    return aliases.get(value, value)


def infer_setting_from_run_dir(path):
    name = Path(path).name
    for setting in [
        "clean_best_single_source",
        "null_all_missing_flag",
        "null_all_image",
        "clean_vehicle_only",
        "clean_cav_only",
        "clean_rsu_only",
        "clean_all",
        "ego_only",
    ]:
        if setting in name:
            return canonical_setting(setting)
    return ""


def row_key(row):
    sample_id = row.get("sample_id") or row.get("sample_idx") or ""
    if sample_id != "":
        return ("sample", sample_id)
    route_id = row.get("route_id") or row.get("scenario_id") or ""
    frame_id = row.get("frame_id") or ""
    if route_id and frame_id != "":
        return ("route_frame", route_id, frame_id)
    return ("empty", "")


def parse_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def bool_str(value):
    if value == "":
        return ""
    return "true" if bool(value) else "false"


def classify_delta(delta, threshold):
    if delta is None:
        return ""
    if delta < -threshold:
        return "benefit"
    if delta > threshold:
        return "harm"
    return "neutral"


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


def discover_run_dirs(root):
    root = Path(root)
    if (root / "per_sample_planning.csv").exists():
        return [root]
    return sorted(path.parent for path in root.glob("*/per_sample_planning.csv"))


def load_summary_setting(run_dir):
    summary_path = Path(run_dir) / "summary.json"
    if not summary_path.exists():
        return ""
    try:
        data = json.loads(summary_path.read_text())
    except json.JSONDecodeError:
        return ""
    return canonical_setting(data.get("setting", ""))


def build_baseline_index(roots):
    baselines = {}
    counts = {}
    for root in roots:
        for run_dir in discover_run_dirs(root):
            rows = read_csv(Path(run_dir) / "per_sample_planning.csv")
            if not rows:
                continue
            setting = canonical_setting(rows[0].get("setting", "")) or load_summary_setting(run_dir) or infer_setting_from_run_dir(run_dir)
            if setting not in {
                "ego",
                "clean_all",
                "clean_rsu_only",
                "clean_vehicle_only",
                "clean_best_single_source",
                "null_all",
            }:
                continue
            counts[setting] = counts.get(setting, 0) + len(rows)
            for row in rows:
                key = row_key(row)
                ade = parse_float(row.get("ADE"))
                if ade is None:
                    continue
                baselines.setdefault(key, {})
                # Keep the first value for deterministic phase0 split roots.
                baselines[key].setdefault(setting, ade)
    return baselines, counts


def add_delta_fields(row, baselines, threshold):
    key = row_key(row)
    base = baselines.get(key, {})
    ade = parse_float(row.get("ADE"))
    clean = base.get("clean_all")
    ego = base.get("ego")
    null_all = base.get("null_all")
    best = base.get("clean_best_single_source")
    rsu = base.get("clean_rsu_only")
    cav = base.get("clean_vehicle_only")

    refs = {
        "clean_all": clean,
        "ego": ego,
        "null_all": null_all,
        "clean_best_single_source": best,
    }
    for name, ref in refs.items():
        delta_key = f"delta_ADE_vs_{name}"
        worse_key = f"worse_than_{name}"
        if ade is None or ref is None:
            row[delta_key] = ""
            row[worse_key] = ""
        else:
            delta = ade - ref
            row[delta_key] = delta
            row[worse_key] = bool_str(delta > threshold)
        row[f"baseline_{name}_ADE"] = "" if ref is None else ref

    clean_delta = parse_float(row.get("delta_ADE_vs_clean_all"))
    row["delta_ADE_gt_0p2"] = bool_str(clean_delta is not None and clean_delta > 0.2)
    row["delta_ADE_gt_0p5"] = bool_str(clean_delta is not None and clean_delta > 0.5)
    row["delta_ADE_gt_1p0"] = bool_str(clean_delta is not None and clean_delta > 1.0)

    row["native_coop_state"] = classify_delta(None if clean is None or ego is None else clean - ego, threshold)
    row["shift_coop_state"] = classify_delta(None if ade is None or ego is None else ade - ego, threshold)
    row["rsu_native_state"] = classify_delta(None if rsu is None or ego is None else rsu - ego, threshold)
    row["cav_native_state"] = classify_delta(None if cav is None or ego is None else cav - ego, threshold)
    row["rsu_shift_state"] = classify_delta(clean_delta, threshold) if "rsu" in (row.get("application_mode") or "") else ""
    row["cav_shift_state"] = classify_delta(clean_delta, threshold) if "vehicle" in (row.get("application_mode") or "") or "cav" in (row.get("application_mode") or "") else ""

    missing = [name for name, ref in refs.items() if ref is None]
    row["baseline_key_status"] = "ok" if not missing else "missing:" + ",".join(missing)
    return row


def enrich_run(run_dir, baselines, threshold):
    run_dir = Path(run_dir)
    rows = read_csv(run_dir / "per_sample_planning.csv")
    enriched = [add_delta_fields(dict(row), baselines, threshold) for row in rows]
    fieldnames = list(rows[0].keys()) if rows else []
    for field in DELTA_FIELDS:
        if field not in fieldnames:
            fieldnames.append(field)
    out_path = run_dir / "per_sample_planning_enriched.csv"
    write_csv(out_path, enriched, fieldnames)
    return out_path, enriched, fieldnames


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-root", action="append", required=True, help="Result root or a single run dir to enrich.")
    parser.add_argument("--baseline-root", action="append", required=True, help="Phase0/baseline result root. Repeatable.")
    parser.add_argument("--threshold", type=float, default=0.05, help="ADE margin for benefit/neutral/harm and worse-than flags.")
    parser.add_argument("--combined-out", default="", help="Optional combined enriched CSV path.")
    args = parser.parse_args()

    baselines, counts = build_baseline_index(args.baseline_root)
    combined_rows = []
    combined_fields = []
    run_count = 0
    for target_root in args.target_root:
        for run_dir in discover_run_dirs(target_root):
            out_path, rows, fields = enrich_run(run_dir, baselines, args.threshold)
            run_count += 1
            combined_rows.extend(rows)
            for field in fields:
                if field not in combined_fields:
                    combined_fields.append(field)
            print(out_path)

    if args.combined_out:
        write_csv(args.combined_out, combined_rows, combined_fields)
        print(args.combined_out)

    print(f"baseline_keys={len(baselines)} baseline_rows={counts} enriched_runs={run_count} enriched_rows={len(combined_rows)}")


if __name__ == "__main__":
    main()
