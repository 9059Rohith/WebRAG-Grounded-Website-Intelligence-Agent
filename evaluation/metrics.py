"""Deterministic diagnostics. These checks do not establish semantic faithfulness."""

from __future__ import annotations

import math
import re
from statistics import mean
from typing import Any


def normalize(text: str) -> str:
    """Ignore whitespace variation while preserving evidence characters."""
    return " ".join(text.split())


def wilson(successes: int, trials: int) -> dict[str, float | int | None]:
    """Two-sided 95% Wilson score interval for a Bernoulli proportion."""
    if trials == 0:
        return {"successes": 0, "trials": 0, "rate": None, "low": None, "high": None}
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    radius = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return {
        "successes": successes,
        "trials": trials,
        "rate": p,
        "low": max(0.0, center - radius),
        "high": min(1.0, center + radius),
    }


def retrieval_metrics(
    ranked_urls: list[str], expected_urls: list[str], k: int = 5
) -> dict[str, float | int | None]:
    """Rank by first URL occurrence; aliases and partial URL matches never receive credit."""
    ranked = list(dict.fromkeys(ranked_urls))[:k]
    expected = set(expected_urls)
    if not expected:
        return {
            "hit_at_k": None,
            "reciprocal_rank": None,
            "page_coverage": None,
            "covered_pages": 0,
            "expected_pages": 0,
        }
    intersection = expected.intersection(ranked)
    rank = next((i for i, url in enumerate(ranked, 1) if url in expected), None)
    return {
        "hit_at_k": int(bool(intersection)),
        "reciprocal_rank": 1 / rank if rank else 0.0,
        "page_coverage": len(intersection) / len(expected),
        "covered_pages": len(intersection),
        "expected_pages": len(expected),
    }


def grade_keypoints(answer: str, keypoints: list[dict[str, Any]]) -> dict[str, Any]:
    """Require every listed regex component for each keypoint, ignoring case."""
    normalized = normalize(answer)
    points = []
    for point in keypoints:
        passed = all(
            re.search(pattern, normalized, flags=re.IGNORECASE) is not None
            for pattern in point["patterns"]
        )
        points.append({"label": point["label"], "matched": passed})
    return {
        "keypoints": points,
        "keypoint_coverage": mean(p["matched"] for p in points) if points else None,
        "all_keypoints": all(p["matched"] for p in points) if points else None,
    }


def citation_metrics(
    sources: list[dict[str, Any]], chunks: dict[str, dict[str, Any]], retrieved_urls: list[str]
) -> dict[str, Any]:
    """Check stored exact evidence, correct URL, and URL-level retrieval provenance."""
    checks = []
    for source in sources:
        chunk = chunks.get(source.get("chunk_id", ""))
        evidence = normalize(source.get("evidence", ""))
        valid = bool(
            chunk
            and evidence
            and source.get("url") == chunk["source_url"]
            and source.get("url") in retrieved_urls
            and evidence in normalize(chunk["text"])
        )
        checks.append(
            {
                "chunk_id": source.get("chunk_id", ""),
                "url": source.get("url", ""),
                "valid_exact_quote": valid,
            }
        )
    return {
        "citations": checks,
        "valid_citations": sum(c["valid_exact_quote"] for c in checks),
        "citation_count": len(checks),
        "citation_precision": mean(c["valid_exact_quote"] for c in checks) if checks else None,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Preserve undefined metrics rather than silently replacing them with success."""

    def average(key: str) -> float | None:
        values = [row[key] for row in rows if row.get(key) is not None]
        return mean(values) if values else None

    applicable = [row for row in rows if row.get("all_keypoints") is not None]
    retrieval = [row for row in rows if row.get("hit_at_k") is not None]
    unknown = [row for row in rows if not row["expected_answerable"]]
    answerable = [row for row in rows if row["expected_answerable"]]
    citation_count = sum(row.get("citation_count", 0) for row in rows)
    valid = sum(row.get("valid_citations", 0) for row in rows)
    cited_answers = [r for r in rows if r["actual_answerable"]]
    latencies = sorted(row["wall_ms"] for row in rows)
    p95 = latencies[max(0, math.ceil(0.95 * len(latencies)) - 1)] if latencies else None
    return {
        "count": len(rows),
        "keypoint_coverage": average("keypoint_coverage"),
        "all_keypoints": wilson(sum(bool(r["all_keypoints"]) for r in applicable), len(applicable)),
        "hit_at_k": wilson(sum(r["hit_at_k"] for r in retrieval), len(retrieval)),
        "mrr": average("reciprocal_rank"),
        "page_coverage": average("page_coverage"),
        "citation_exact_quote": wilson(valid, citation_count),
        "all_citations_supported": wilson(
            sum(
                bool(r.get("citation_count"))
                and r.get("valid_citations") == r.get("citation_count")
                for r in cited_answers
            ),
            len(cited_answers),
        ),
        "answerability_accuracy": wilson(sum(r["answerability_correct"] for r in rows), len(rows)),
        "unanswerable_refusal": wilson(
            sum(not r["actual_answerable"] and not r.get("error") for r in unknown), len(unknown)
        ),
        "false_answer": wilson(sum(r["actual_answerable"] for r in unknown), len(unknown)),
        "false_refusal": wilson(
            sum(not r["actual_answerable"] and not r.get("error") for r in answerable),
            len(answerable),
        ),
        "answerable_response": wilson(
            sum(r["actual_answerable"] for r in answerable), len(answerable)
        ),
        "errors": sum(bool(r.get("error")) for r in rows),
        "mean_wall_ms": average("wall_ms"),
        "p50_wall_ms": latencies[max(0, math.ceil(0.50 * len(latencies)) - 1)]
        if latencies
        else None,
        "p95_wall_ms": p95,
        "mean_stage_ms": {
            stage: mean(r["timings_ms"][stage] for r in rows if stage in r.get("timings_ms", {}))
            for stage in sorted({s for r in rows for s in r.get("timings_ms", {})})
        },
        "stage_percentiles_ms": {
            stage: {
                "p50": values[max(0, math.ceil(0.50 * len(values)) - 1)],
                "p95": values[max(0, math.ceil(0.95 * len(values)) - 1)],
            }
            for stage in sorted({s for r in rows for s in r.get("timings_ms", {})})
            if (
                values := sorted(
                    r["timings_ms"][stage] for r in rows if stage in r.get("timings_ms", {})
                )
            )
        },
    }
