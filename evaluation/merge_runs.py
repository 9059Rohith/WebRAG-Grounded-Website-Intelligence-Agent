"""Combine independently executed dev and holdout runs without querying again."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.metrics import aggregate
from evaluation.reporting import generate_cost_report, generate_evaluation_report


def merge_runs(dev_path: Path, holdout_path: Path, out: Path) -> dict[str, Any]:
    """Refuse to combine mismatched snapshots/settings/code or duplicate question IDs."""
    dev = json.loads(dev_path.read_text(encoding="utf-8"))
    holdout = json.loads(holdout_path.read_text(encoding="utf-8"))
    for key in ["provider", "top_k", "settings", "corpus", "source_sha256", "benchmark_version"]:
        if dev.get(key) != holdout.get(key):
            raise ValueError(f"Cannot combine runs with different {key}")
    if any(row["split"] != "dev" for row in dev["questions"]) or any(
        row["split"] != "holdout" for row in holdout["questions"]
    ):
        raise ValueError("Each input must contain its own split only")
    rows = dev["questions"] + holdout["questions"]
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate question IDs across runs")
    report: dict[str, Any] = {
        **holdout,
        "run_id": holdout["run_id"] + "-combined",
        "questions": rows,
        "source_runs": {"dev": dev["run_id"], "holdout": holdout["run_id"]},
        "dev_initialization_ms": dev["initialization_ms"],
        "gold_validation": dev["gold_validation"] + holdout["gold_validation"],
        "overall": aggregate(rows),
        "by_split": {
            "dev": aggregate(dev["questions"]),
            "holdout": aggregate(holdout["questions"]),
        },
        "by_category": {
            c: aggregate([r for r in rows if r["category"] == c])
            for c in sorted({r["category"] for r in rows})
        },
        "threshold_diagnostics": dev["threshold_diagnostics"],
    }
    dev_n = sum(bool(r["expected_urls"]) for r in dev["questions"])
    holdout_n = sum(bool(r["expected_urls"]) for r in holdout["questions"])
    if dev["retrieval_ablations"].keys() != holdout["retrieval_ablations"].keys():
        raise ValueError("Cannot combine different retrieval ablations")
    report["retrieval_ablations"] = {
        mode: {
            key: (
                dev["retrieval_ablations"][mode][key] * dev_n
                + holdout["retrieval_ablations"][mode][key] * holdout_n
            )
            / (dev_n + holdout_n)
            for key in ["hit_at_k", "mrr", "page_coverage", "mean_wall_ms"]
        }
        for mode in dev["retrieval_ablations"]
    }
    baseline_path = out / "baseline.json"
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        report["improvement_history"] = [
            {
                "round": "baseline (same revised scorer)",
                "dev_keypoint_coverage": baseline["by_split"]["dev"]["keypoint_coverage"],
                "holdout_keypoint_coverage": baseline["by_split"]["holdout"]["keypoint_coverage"],
                "change": "Original extractive implementation; development-only scorer synonyms applied to stored original answers.",
            },
        ]
        for path in sorted(out.glob("dev-round*/results.json")):
            saved = json.loads(path.read_text(encoding="utf-8"))
            is_final = path.resolve() == dev_path.resolve()
            report["improvement_history"].append(
                {
                    "round": path.parent.name,
                    "dev_keypoint_coverage": saved["by_split"]["dev"]["keypoint_coverage"],
                    "holdout_keypoint_coverage": report["by_split"]["holdout"]["keypoint_coverage"]
                    if is_final
                    else None,
                    "change": saved.get(
                        "change_description",
                        "Saved development round; implementation changes described in DECISIONS.md. Holdout measured after final development choice only.",
                    ),
                }
            )
        if not any(
            path.resolve() == dev_path.resolve() for path in out.glob("dev-round*/results.json")
        ):
            report["improvement_history"].append(
                {
                    "round": "dev-final (round 3)",
                    "dev_keypoint_coverage": dev["by_split"]["dev"]["keypoint_coverage"],
                    "holdout_keypoint_coverage": report["by_split"]["holdout"]["keypoint_coverage"],
                    "change": "Numeric qualifiers retained; explicit conjunction facets retrieve/select complementary evidence. Final code frozen before one holdout run.",
                }
            )
    earlier_benchmark = out.parent.parent / "artifacts" / "benchmark.json"
    if earlier_benchmark.exists():
        report["earlier_cli_benchmark"] = json.loads(earlier_benchmark.read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    generate_evaluation_report(report, out)
    generate_cost_report(report, out)
    return report


def main() -> None:
    """Publish independent split observations while preserving their provenance."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("evaluation/results"))
    args = parser.parse_args()
    report = merge_runs(args.dev, args.holdout, args.out)
    print(json.dumps(report["by_split"], indent=2))


if __name__ == "__main__":
    main()
