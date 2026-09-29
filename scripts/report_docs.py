"""Publish saved observations into submission documents without rerunning queries."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from evaluation.reporting import (
    fmt,
    generate_cost_report,
    generate_evaluation_report,
    interval,
    measurement_notes,
)


def replace_block(path: Path, marker: str, text: str) -> None:
    """Replace a bounded generated section and retain the surrounding human notes."""
    content = path.read_text(encoding="utf-8")
    start = f"<!-- {marker}_START -->"
    end = f"<!-- {marker}_END -->"
    if start not in content and end not in content:
        path.write_text(
            content.rstrip() + "\n\n" + start + "\n" + text.strip() + "\n" + end + "\n",
            encoding="utf-8",
        )
        return
    before, tail = content.split(start, 1)
    _, after = tail.split(end, 1)
    path.write_text(before + start + "\n" + text.strip() + "\n" + end + after, encoding="utf-8")


def preserve_local_baseline(root: Path) -> None:
    """Archive existing local results/docs once before publishing a paid-provider run."""
    source = root / "evaluation/results/results.json"
    if not source.exists():
        return
    if json.loads(source.read_text(encoding="utf-8")).get("provider") != "local":
        return
    archive = root / "evaluation/results/local_baseline"
    archive.mkdir(parents=True, exist_ok=True)
    for old, name in [
        (source, "results.json"),
        (root / "EVALUATION.md", "EVALUATION.md"),
        (root / "COST_ANALYSIS.md", "COST_ANALYSIS.md"),
        (root / "README.md", "README.md"),
    ]:
        target = archive / name
        if old.exists() and not target.exists():
            shutil.copy2(old, target)


def publish(report: dict[str, Any], root: Path) -> None:
    """Make README/email/video observations agree with the same saved run."""
    if report["provider"] != "local":
        preserve_local_baseline(root)
    generate_evaluation_report(report, root)
    generate_cost_report(report, root / "COST_ANALYSIS.md")
    corpus = report["corpus"]
    splits = report["by_split"]
    split_name = next(
        (name for name in ["independent_holdout", "holdout"] if name in splits),
        next(iter(splits)),
    )
    holdout = splits[split_name]
    split_label = split_name.replace("_", " ").capitalize()
    whole = report["overall"]
    text = f"""Measured snapshot: **{corpus["pages"]} pages**, **{corpus["chunks"]:,} chunks**, **{corpus["chunk_tokens"]:,} embedded text token estimates**. Crawl/index files retain per-page hashes and metadata. Evaluation corpus hash: `{corpus["chunks_sha256"]}`. Corpus/index configuration and ingestion usage are recorded in the selected run's raw report. This is a bounded snapshot, not complete site coverage."""
    replace_block(root / "README.md", "CORPUS_SUMMARY", text)
    table = f"""Run `{report["run_id"]}`: {whole["count"]} questions, provider **{report["provider"]}**, cache disabled. {split_label} ({holdout["count"]} questions) is the headline below.

| Measured diagnostic | {split_label} | Overall |
|---|---|---|
| Regex keypoint coverage | {fmt(holdout["keypoint_coverage"], True)} | {fmt(whole["keypoint_coverage"], True)} |
| Retrieval Hit@{report["top_k"]} | {interval(holdout["hit_at_k"])} | {interval(whole["hit_at_k"])} |
| Retrieval MRR | {fmt(holdout["mrr"])} | {fmt(whole["mrr"])} |
| Unanswerable refusal | {interval(holdout["unanswerable_refusal"])} | {interval(whole["unanswerable_refusal"])} |
| Exact supported citation | {interval(holdout["citation_exact_quote"])} | {interval(whole["citation_exact_quote"])} |
| Query p50 / p95 | {holdout["p50_wall_ms"]:.1f} / {holdout["p95_wall_ms"]:.1f} ms | {whole["p50_wall_ms"]:.1f} / {whole["p95_wall_ms"]:.1f} ms |

Intervals are 95% Wilson. {measurement_notes(report)} All failures and raw responses remain in the detailed report. Different independent-holdout questions do not establish a like-for-like improvement over the archived local benchmark."""
    replace_block(root / "README.md", "EVAL_SUMMARY", table)
    examples = []
    selected: set[str] = set()
    for label, category in [
        ("Straightforward", "straightforward"),
        ("Multi-page", "multi-page"),
        ("Unanswerable", "unanswerable"),
        ("Additional unanswerable", "unanswerable"),
    ]:
        row = next(
            (
                r
                for r in report["questions"]
                if r["category"] == category and r["id"] not in selected
            ),
            None,
        )
        if row is None:
            continue
        selected.add(row["id"])
        answer = row["raw_answer"]
        sources = "\n".join(f"- [{s['title']}]({s['url']})" for s in answer["sources"])
        examples.append(f"""**{label}:** {row["question"]}

Actual answer (`answerable={str(answer["answerable"]).lower()}`):

```text
{answer["answer"]}
```

{sources or "No supporting source was returned."}

Regex keypoint coverage: {fmt(row["keypoint_coverage"], True)}; query wall time: {row["wall_ms"]:.1f} ms; reported API cost: ${row["usage"].get("estimated_usd", 0):.6f}.""")
    replace_block(root / "README.md", "EXAMPLES", "\n\n".join(examples))
    observed_cost = sum(row.get("usage", {}).get("estimated_usd", 0) for row in report["questions"])
    cost_label = (
        "Observed answer-query API cost estimate"
        if report["provider"] != "local"
        else "Observed local API spend"
    )
    headline = (
        f"{split_label} ({holdout['count']} questions): regex keypoint coverage **{fmt(holdout['keypoint_coverage'], True)}**, "
        f"retrieval Hit@{report['top_k']} **{interval(holdout['hit_at_k'])}**, "
        f"unanswerable refusal **{interval(holdout['unanswerable_refusal'])}**. "
        f"Query wall latency p50/p95 **{holdout['p50_wall_ms']:.1f}/{holdout['p95_wall_ms']:.1f} ms**. "
        f"{cost_label}: **${observed_cost:.6f}**; ingestion and auxiliary work are separate. "
        + measurement_notes(report)
    )
    replace_block(root / "docs/EMAIL_REPLY.md", "EMAIL_METRICS", headline)
    replace_block(root / "docs/VIDEO_SCRIPT.md", "VIDEO_METRICS", headline)
    graph_path = root / "docs/langgraph.mmd"
    if graph_path.exists():
        replace_block(
            root / "docs/architecture.md",
            "GENERATED_GRAPH",
            "```mermaid\n" + graph_path.read_text(encoding="utf-8").strip() + "\n```",
        )


def main() -> None:
    """Update generated document sections from an existing measured report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("evaluation/results/results.json"))
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    publish(json.loads(args.report.read_text(encoding="utf-8")), args.root.resolve())
    print("Published saved evaluation/cost observations to submission documents.")


if __name__ == "__main__":
    main()
