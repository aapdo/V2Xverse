#!/usr/bin/env python3
"""Aggregate V2Xverse/CoDriving diagnostic result directories."""

import argparse
import csv
import json
from pathlib import Path


def load_summaries(root):
    rows = []
    for path in sorted(Path(root).glob("*/summary.json")):
        data = json.loads(path.read_text())
        data["run_dir"] = str(path.parent)
        rows.append(data)
    return rows


def write_csv(path, rows):
    if not rows:
        return
    fields = sorted({k for row in rows for k in row.keys() if not isinstance(row.get(k), dict)})
    with Path(path).open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{k: row.get(k, "") for k in fields} for row in rows])


def md_table(rows):
    cols = ["run_id", "setting", "shift_family", "severity", "application_mode", "num_samples", "mean_ADE", "p90_ADE", "mean_FDE", "p90_FDE"]
    out = []
    out.append("| " + " | ".join(cols) + " |")
    out.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for row in rows:
        values = []
        for col in cols:
            val = row.get(col, "")
            if isinstance(val, float):
                val = f"{val:.4f}"
            values.append(str(val))
        out.append("| " + " | ".join(values) + " |")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    root = Path(args.root)
    out_dir = Path(args.out_dir) if args.out_dir else root / "combined"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = load_summaries(root)
    write_csv(out_dir / "summary.csv", rows)

    title = root.name
    body = [
        f"# V2Xverse CoDriving Diagnostic Results: {title}",
        "",
        f"- result root: `{root}`",
        f"- runs found: `{len(rows)}`",
        "",
        "## Summary",
        "",
        md_table(rows) if rows else "No completed runs found.",
        "",
        "## Notes",
        "",
        "- `mean_ADE/FDE` are zero-shot checkpoint forward metrics; no training is performed.",
        "- Per-sample details are in each run directory: `per_sample_planning.csv`, `per_sample_perception.csv`, `per_sample_agent.csv`.",
    ]
    (out_dir / "RESULTS.md").write_text("\n".join(body))
    print(out_dir / "RESULTS.md")


if __name__ == "__main__":
    main()
