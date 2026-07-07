#!/usr/bin/env python3
"""Generate V2Xverse/CoDriving diagnostic job TSV files."""

import argparse
import csv
from pathlib import Path


FIELDS = [
    "run_id", "phase", "setting", "shift_family", "severity",
    "application_mode", "shift_seed", "max_samples",
]


PHASE0 = [
    ("ego_only", "none", "none", "none"),
    ("clean_all", "none", "none", "none"),
    ("clean_rsu_only", "none", "none", "none"),
    ("clean_vehicle_only", "none", "none", "none"),
    ("null_all_image", "none", "none", "none"),
    ("null_all_missing_flag", "none", "none", "none"),
    ("null_rsu_only", "none", "none", "none"),
    ("null_vehicle_only", "none", "none", "none"),
]


PILOT = [
    ("clean_all", "latency_det", "s1", "all_shifted"),
    ("clean_all", "latency_det", "s3", "all_shifted"),
    ("clean_all", "latency_jitter", "s3", "all_shifted"),
    ("clean_all", "latency_jitter", "stress", "rsu_shifted_only"),
    ("clean_all", "frame_lost_hold", "s2", "rsu_shifted_only"),
    ("clean_all", "frame_lost_hold", "s2", "vehicle_shifted_only"),
    ("clean_all", "frame_lost_zero", "s3", "all_shifted"),
    ("clean_all", "packet_drop", "s3", "all_shifted"),
    ("clean_all", "bandwidth_cap", "s3", "all_shifted"),
    ("clean_all", "fov_left_loss", "s3", "rsu_shifted_only"),
    ("clean_all", "fov_right_loss", "s3", "vehicle_shifted_only"),
    ("clean_all", "pose_noise", "s3", "all_shifted"),
    ("clean_all", "camera_crash", "s3", "rsu_shifted_only"),
    ("clean_all", "color_quant", "s3", "rsu_shifted_only"),
    ("clean_all", "jpeg", "s3", "rsu_shifted_only"),
    ("clean_all", "compound_avail", "mid", "all_shifted"),
    ("clean_all", "compound_lcf", "mid", "all_shifted"),
    ("clean_all", "compound_photo_comm", "mid", "all_shifted"),
]


FULL_FAMILIES = [
    "latency_det", "latency_jitter", "frame_lost_hold", "frame_lost_zero",
    "packet_drop", "bandwidth_cap", "fov_center", "fov_left_loss",
    "fov_right_loss", "fov_top_loss", "fov_bottom_loss", "camera_crash",
    "resolution", "pose_noise", "color_quant", "brightness", "darkness",
    "contrast", "motion_blur", "defocus_blur", "jpeg", "fog", "rain",
    "snow",
]


def row(phase, setting, family, severity, mode, seed, max_samples):
    run_id = f"{phase}_{setting}"
    if family != "none":
        run_id += f"_{family}_{severity}_{mode}"
    run_id += f"_seed{seed}"
    return {
        "run_id": run_id,
        "phase": phase,
        "setting": setting,
        "shift_family": family,
        "severity": severity,
        "application_mode": mode,
        "shift_seed": seed,
        "max_samples": max_samples,
    }


def write(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, delimiter="\t", fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def split_by_counts(rows, counts):
    buckets = {name: [] for name in counts}
    remaining = dict(counts)
    hosts = list(counts)
    cursor = 0
    for item in rows:
        while remaining[hosts[cursor % len(hosts)]] <= 0:
            cursor += 1
        host = hosts[cursor % len(hosts)]
        buckets[host].append(item)
        remaining[host] -= 1
        cursor += 1
    if any(remaining.values()):
        raise ValueError(f"unused split capacity: {remaining}")
    return buckets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--pilot-max-samples", default="")
    parser.add_argument("--full-max-samples", default="")
    args = parser.parse_args()

    out = Path(args.out_dir)
    write(out / "jobs_phase0.tsv", [
        row("phase0", setting, family, severity, mode, args.seed, "")
        for setting, family, severity, mode in PHASE0
    ])
    write(out / "jobs_phase1_pilot.tsv", [
        row("phase1pilot", setting, family, severity, mode, args.seed, args.pilot_max_samples)
        for setting, family, severity, mode in PILOT
    ])

    full_rows = []
    for family in FULL_FAMILIES:
        for severity in ["s1", "s2", "s3", "stress"]:
            for mode in ["all_shifted", "rsu_shifted_only", "vehicle_shifted_only"]:
                full_rows.append(row("phase1full", "clean_all", family, severity, mode, args.seed, args.full_max_samples))
    for family in ["compound_lcf", "compound_avail", "compound_photo_comm"]:
        for severity in ["mild", "mid", "severe", "stress"]:
            full_rows.append(row("phase1full", "clean_all", family, severity, "all_shifted", args.seed, args.full_max_samples))
    write(out / "jobs_phase1_full.tsv", full_rows)

    full_split = split_by_counts(
        full_rows,
        {
            "farm8": 66,
            "farm6": 50,
            "farm7": 50,
            "farm1": 50,
            "farm2": 33,
            "farm9": 33,
            "cps": 18,
        },
    )
    for host, host_rows in full_split.items():
        write(out / f"jobs_phase1_full_{host}.tsv", host_rows)

    farm_rows = []
    for host in ["farm8", "farm6", "farm7", "farm1", "farm2", "farm9"]:
        farm_rows.extend(full_split[host])
    write(out / "jobs_phase1_full_farm_shared.tsv", farm_rows)


if __name__ == "__main__":
    main()
