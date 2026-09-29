from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from evaluation.metrics import (
    aggregate,
    citation_metrics,
    grade_keypoints,
    retrieval_metrics,
    wilson,
)
from evaluation.reporting import generate_cost_report, generate_evaluation_report
from evaluation.run_eval import validate_gold, warmup_local_encoder
from scripts.report_docs import publish, replace_block


def test_url_metrics_preserve_first_occurrence_and_require_all_pages() -> None:
    metrics = retrieval_metrics(["wrong", "a", "a", "b"], ["a", "b"], k=3)
    assert metrics["hit_at_k"] == 1
    assert metrics["reciprocal_rank"] == 0.5
    assert metrics["page_coverage"] == 1.0
    assert retrieval_metrics(["a#fragment"], ["a"])["hit_at_k"] == 0
    assert retrieval_metrics(["a"], [])["hit_at_k"] is None


def test_keypoint_requires_every_component_and_supports_alternatives() -> None:
    points = [{"label": "behavior", "patterns": ["immutable|cannot change", "tuple"]}]
    assert grade_keypoints("A tuple cannot change", points)["all_keypoints"]
    assert not grade_keypoints("A tuple can change", points)["all_keypoints"]
    assert grade_keypoints("anything", [])["keypoint_coverage"] is None


def test_exact_citation_cannot_claim_fabricated_url_chunk_or_quote() -> None:
    chunk = {"a": {"source_url": "https://test/a", "text": "An exact quote. More text."}}
    source = {"chunk_id": "a", "url": "https://test/a", "evidence": "An  exact\nquote."}
    assert citation_metrics([source], chunk, ["https://test/a"])["valid_citations"] == 1
    assert (
        citation_metrics([{**source, "evidence": "Invented quote"}], chunk, ["https://test/a"])[
            "valid_citations"
        ]
        == 0
    )
    assert citation_metrics([source], chunk, [])["valid_citations"] == 0
    assert (
        citation_metrics([{**source, "url": "https://evil/a"}], chunk, ["https://evil/a"])[
            "valid_citations"
        ]
        == 0
    )


def test_wilson_small_sample_does_not_claim_certainty() -> None:
    value = wilson(6, 6)
    assert value["rate"] == 1
    assert 0.60 < value["low"] < 0.62
    assert value["high"] == 1
    assert wilson(0, 0)["rate"] is None


def test_gold_validation_rejects_unsupported_benchmark() -> None:
    question = {
        "id": "s1",
        "expected_urls": ["page"],
        "keypoints": [{"label": "answer", "patterns": ["ground truth"]}],
    }
    assert validate_gold([question], [{"url": "page", "text": "ground truth"}])[0]["valid"]
    with pytest.raises(ValueError, match="unsupported"):
        validate_gold([question], [{"url": "page", "text": "different text"}])


def test_errors_never_count_as_correct_refusals_in_accuracy() -> None:
    row = {
        "expected_answerable": False,
        "actual_answerable": False,
        "answerability_correct": False,
        "wall_ms": 1,
        "timings_ms": {},
        "error": "failed",
        "all_keypoints": None,
    }
    result = aggregate([row])
    assert result["answerability_accuracy"]["successes"] == 0
    assert result["unanswerable_refusal"]["successes"] == 0
    assert result["errors"] == 1


def test_benchmark_categories_and_paired_split_do_not_leak_twins() -> None:
    items = json.loads(Path("evaluation/questions.json").read_text(encoding="utf-8"))["questions"]
    assert Counter(q["category"] for q in items) == {
        "straightforward": 5,
        "paraphrased": 5,
        "multi-page": 5,
        "misleading": 5,
        "unanswerable": 6,
    }
    lookup = {q["id"]: q for q in items}
    assert len(lookup) == len(items)
    for item in items:
        if item["category"] == "multi-page":
            assert len(item["expected_urls"]) >= 2
        if item.get("paired_with"):
            assert item["split"] == lookup[item["paired_with"]]["split"]


def test_citation_preserves_case_and_unicode_literal_characters() -> None:
    chunks = {"c": {"source_url": "page", "text": "True  K"}}
    exact = {"chunk_id": "c", "url": "page", "evidence": "True\nK"}
    assert citation_metrics([exact], chunks, ["page"])["valid_citations"] == 1
    for changed in ["true K", "True K"]:
        assert (
            citation_metrics([{**exact, "evidence": changed}], chunks, ["page"])["valid_citations"]
            == 0
        )
    assert grade_keypoints("TRUE", [{"label": "proxy", "patterns": ["true"]}])["all_keypoints"]


def test_local_warmup_forces_loader_and_paid_warmup_makes_no_call() -> None:
    class Embeddings:
        calls = 0

        def _load(self) -> None:
            self.calls += 1

    local = Embeddings()
    assert warmup_local_encoder("local", local) >= 0
    assert local.calls == 1
    paid = Embeddings()
    assert warmup_local_encoder("openai", paid) == 0
    assert paid.calls == 0


def report_fixture(provider: str) -> dict[str, Any]:
    """Synthetic ledger values exercise reporting arithmetic without any API calls."""
    rows: list[dict[str, Any]] = []
    for index, answerable in enumerate([True, False]):
        usage = {
            "input_tokens": 100 if provider == "openai" else 0,
            "output_tokens": 20 if provider == "openai" else 0,
            "embedding_tokens": 5,
            "estimated_usd": (0.02 if answerable else 0.01) if provider == "openai" else 0,
            "token_source": "api_reported" if provider == "openai" else "estimated_tiktoken",
        }
        row: dict[str, Any] = {
            "id": f"new_{index}",
            "question": "Fixture question",
            "category": "straightforward" if answerable else "unanswerable",
            "split": "independent_holdout",
            "expected_answerable": answerable,
            "actual_answerable": answerable,
            "answerability_correct": True,
            "expected_urls": ["page"] if answerable else [],
            "wall_ms": 100,
            "timings_ms": {"total": 100},
            "error": None,
            "usage": usage,
            "counterfactual_tokens": {
                "input": 10000,
                "output": 500,
                "query_embedding": 10,
                "context_chunks": 1,
            },
            "raw_answer": {"answer": "Fixture answer", "answerable": answerable, "sources": []},
        }
        row.update(
            grade_keypoints(
                "Fixture answer",
                [{"label": "fixture", "patterns": ["fixture"]}] if answerable else [],
            )
        )
        row.update(retrieval_metrics(["page"], row["expected_urls"]))
        row.update(citation_metrics([], {}, ["page"]))
        rows.append(row)
    result = aggregate(rows)
    return {
        "run_id": "unit-test-only",
        "timestamp_utc": "unit-test-only",
        "provider": provider,
        "answer_mode": "synthesis" if provider == "openai" else "extractive",
        "top_k": 5,
        "initialization_ms": 10,
        "model_warmup_ms": 0,
        "settings": {"verify_with_llm": True},
        "corpus": {"pages": 1, "chunks": 1, "chunk_tokens": 200, "chunks_sha256": "fixture"},
        "questions": rows,
        "overall": result,
        "by_split": {"independent_holdout": result},
        "by_category": {
            category: aggregate([r for r in rows if r["category"] == category])
            for category in ["straightforward", "unanswerable"]
        },
        "auxiliary_usage": {
            "retrieval_ablations": {"estimated_usd": 0.004 if provider == "openai" else 0}
        },
    }


def test_paid_cost_uses_returned_usage_and_does_not_discount_paid_refusals(tmp_path: Path) -> None:
    text = generate_cost_report(report_fixture("openai"), tmp_path)
    assert "| Query API cost estimate from usage records | $0.030000 |" in text
    assert "| Query plus auxiliary API cost estimate, excludes ingestion | $0.034000 |" in text
    assert "| 1,000 | $15.0000 | $10.5000 |" in text
    assert "no additional zero-cost refusal discount" in text
    assert "not a second usage ledger" in text
    assert "Hypothetical OpenAI comparison — not measured" not in text
    assert "made no paid model API calls" not in text


def test_local_cost_keeps_hypothetical_comparison_separate(tmp_path: Path) -> None:
    text = generate_cost_report(report_fixture("local"), tmp_path / "cost.md")
    assert "| Query API cost estimate from usage records | $0.000000 |" in text
    assert "Hypothetical OpenAI comparison — not measured" in text
    assert "Observed provider usage extrapolation" not in text
    assert (tmp_path / "cost.md").exists()


def test_paid_evaluation_does_not_reuse_old_local_benchmark_or_timing_claims(
    tmp_path: Path,
) -> None:
    text = generate_evaluation_report(report_fixture("openai"), tmp_path)
    assert "**2-question**" in text
    assert "125-second" not in text
    assert "49-second" not in text
    assert "No paid provider credentials" not in text
    assert "paid warmup requests: **0**" in text
    assert "whitespace-normalized" in text
    assert "preserving case and Unicode" in text
    assert "No independent evaluation LLM judge" in text


def test_publisher_handles_new_ids_and_preserves_local_documents_once(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "evaluation/results").mkdir(parents=True)
    (tmp_path / "evaluation/results/results.json").write_text(
        '{"provider":"local"}', encoding="utf-8"
    )
    (tmp_path / "EVALUATION.md").write_text("old local evaluation", encoding="utf-8")
    (tmp_path / "COST_ANALYSIS.md").write_text("old local cost", encoding="utf-8")
    markers = "\n".join(
        f"<!-- {name}_START -->\nold\n<!-- {name}_END -->"
        for name in ["CORPUS_SUMMARY", "EVAL_SUMMARY", "EXAMPLES"]
    )
    (tmp_path / "README.md").write_text(markers, encoding="utf-8")
    for name, marker in [("EMAIL_REPLY.md", "EMAIL_METRICS"), ("VIDEO_SCRIPT.md", "VIDEO_METRICS")]:
        (tmp_path / "docs" / name).write_text(
            f"<!-- {marker}_START -->\nold\n<!-- {marker}_END -->", encoding="utf-8"
        )
    publish(report_fixture("openai"), tmp_path)
    publish(report_fixture("openai"), tmp_path)
    assert (tmp_path / "evaluation/results/local_baseline/EVALUATION.md").read_text(
        encoding="utf-8"
    ) == "old local evaluation"
    assert "Independent holdout" in (tmp_path / "README.md").read_text(encoding="utf-8")
    email = (tmp_path / "docs/EMAIL_REPLY.md").read_text(encoding="utf-8")
    assert "$0.030000" in email
    assert "Default local API spend" not in email


def test_independent_holdout_has_frozen_source_evidence_and_all_categories() -> None:
    benchmark = json.loads(
        Path("evaluation/independent_holdout_questions.json").read_text(encoding="utf-8")
    )
    rows = benchmark["questions"]
    assert len(rows) == 12
    assert Counter(r["category"] for r in rows) == {
        "straightforward": 2,
        "paraphrased": 2,
        "multi-page": 2,
        "misleading": 2,
        "unanswerable": 4,
    }
    assert {r["split"] for r in rows} == {"independent_holdout"}
    old = json.loads(Path("evaluation/questions.json").read_text(encoding="utf-8"))["questions"]
    assert not {r["question"] for r in rows}.intersection(r["question"] for r in old)
    for row in rows:
        if row["category"] == "multi-page":
            assert len(row["expected_urls"]) >= 2
        for point in row["keypoints"]:
            assert point["heading"] and point["source_evidence"]
            assert grade_keypoints(point["source_evidence"], [point])["all_keypoints"]


def test_publisher_can_add_metrics_to_rewritten_documents_without_losing_prose(
    tmp_path: Path,
) -> None:
    doc = tmp_path / "email.md"
    doc.write_text("Reviewed publication links and owner-written prose.\n", encoding="utf-8")
    replace_block(doc, "METRICS", "Measured provider result")
    replace_block(doc, "METRICS", "New measured provider result")
    text = doc.read_text(encoding="utf-8")
    assert text.startswith("Reviewed publication links and owner-written prose.")
    assert text.count("<!-- METRICS_START -->") == 1
    assert "New measured provider result" in text
