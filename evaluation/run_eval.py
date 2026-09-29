"""Evaluate a snapshot with deterministic diagnostics and recorded provider usage."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

import rag_agent
from evaluation.metrics import (
    aggregate,
    citation_metrics,
    grade_keypoints,
    normalize,
    retrieval_metrics,
)
from evaluation.reporting import generate_cost_report, generate_evaluation_report
from rag_agent.config import Settings
from rag_agent.cost import token_count
from rag_agent.prompts import build_prompt
from rag_agent.retriever import question_facets
from rag_agent.schemas import Hit


def warmup_local_encoder(provider: str, embeddings: Any) -> float:
    """Force local model loading; never send a paid-provider warmup request."""
    if provider != "local":
        return 0.0
    started = time.perf_counter()
    embeddings._load()
    return (time.perf_counter() - started) * 1000


def add_usage(total: dict[str, Any], usage: dict[str, Any]) -> None:
    """Accumulate auxiliary usage separately from the answering-path ledger."""
    for key in ["embedding_tokens", "input_tokens", "output_tokens", "estimated_usd"]:
        total[key] = total.get(key, 0) + usage.get(key, 0)


def validate_gold(
    questions: list[dict[str, Any]], pages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Fail before evaluation when the benchmark is unsupported by the ingested snapshot."""
    by_url = {p["url"]: p for p in pages}
    checks = []
    for question in questions:
        missing = [url for url in question["expected_urls"] if url not in by_url]
        texts = " ".join(
            normalize(by_url[url]["text"]) for url in question["expected_urls"] if url in by_url
        )
        unsupported = [
            p["label"]
            for p in question["keypoints"]
            if not all(
                re.search(
                    pattern,
                    normalize(by_url.get(p.get("source_url", ""), {}).get("text", texts)),
                    flags=re.IGNORECASE,
                )
                for pattern in p["patterns"]
            )
        ]
        checks.append(
            {
                "id": question["id"],
                "missing_urls": missing,
                "unsupported_keypoints": unsupported,
                "valid": not missing and not unsupported,
            }
        )
    invalid = [check for check in checks if not check["valid"]]
    if invalid:
        raise ValueError("Gold benchmark unsupported by corpus: " + json.dumps(invalid))
    return checks


def run_evaluation(settings: Settings, questions: Path, out: Path) -> dict[str, Any]:
    """Validate snapshot-backed gold, score real queries and persist raw observations."""
    from rag_agent.graph import Agent

    benchmark = json.loads(questions.read_text(encoding="utf-8"))
    items = benchmark["questions"] if isinstance(benchmark, dict) else benchmark
    if not items:
        raise ValueError("Benchmark must contain at least one question")
    ids = [item["id"] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate benchmark IDs")
    page_path = settings.data_dir / "pages.json"
    index_info = json.loads((settings.data_dir / "stats.json").read_text(encoding="utf-8"))
    chunk_path = settings.data_dir / index_info.get("chunk_snapshot", "chunks.json")
    pages = json.loads(page_path.read_text(encoding="utf-8"))
    chunk_bytes = chunk_path.read_bytes()
    chunk_items = json.loads(chunk_bytes)
    chunk_lookup = {c["chunk_id"]: c for c in chunk_items}
    gold_validation = validate_gold(items, pages)
    init_started = time.perf_counter()
    agent = Agent(settings)
    agent_initialization_ms = (time.perf_counter() - init_started) * 1000
    model_warmup_ms = warmup_local_encoder(settings.provider, agent.embeddings)
    initialization_ms = (time.perf_counter() - init_started) * 1000
    auxiliary_usage: dict[str, dict[str, Any]] = {
        "reconstructed_prompt_retrieval": {},
        "retrieval_ablations": {},
    }
    rows = []
    for item in items:
        started = time.perf_counter()
        error = None
        try:
            answer = agent.ask(item["question"], use_cache=False).model_dump(mode="json")
        except Exception as exc:  # An error is a scored failure, never silently omitted.
            error = f"{type(exc).__name__}: query failed; provider detail omitted from evaluation artifacts"
            answer = {
                "answer": "",
                "answerable": False,
                "sources": [],
                "retrieved_urls": [],
                "usage": {},
                "timings_ms": {},
                "mode": "error",
            }
        row = {
            "id": item["id"],
            "question": item["question"],
            "category": item["category"],
            "split": item["split"],
            "expected_answerable": item["answerable"],
            "actual_answerable": answer["answerable"],
            "expected_urls": item["expected_urls"],
            "answerability_correct": error is None and answer["answerable"] == item["answerable"],
            "wall_ms": (time.perf_counter() - started) * 1000,
            "error": error,
            "raw_answer": answer,
            "usage": answer["usage"],
            "timings_ms": answer["timings_ms"],
            "retrieval_score": answer.get("retrieval_score", 0.0),
        }
        # Construct the optional synthesis prompt using only returned evidence chunks.
        # This is a reproducible counterfactual token count, not a paid-provider observation.
        selected_ids = list(dict.fromkeys(source["chunk_id"] for source in answer["sources"]))
        hits = [
            Hit(chunk=chunk_lookup[chunk_id], score=0)
            for chunk_id in selected_ids
            if chunk_id in chunk_lookup
        ]
        if settings.provider == "local" and error is None:
            reconstructed, reconstruction_usage = agent.retriever.retrieve_with_usage(
                item["question"]
            )
            hits = reconstructed.hits
            add_usage(
                auxiliary_usage["reconstructed_prompt_retrieval"],
                reconstruction_usage.model_dump(mode="json"),
            )
        system, user = build_prompt(item["question"], hits)
        row["counterfactual_tokens"] = {
            "input": token_count(system + "\n" + user),
            "output": token_count(answer["answer"]),
            "query_embedding": sum(
                token_count(text) for text in [item["question"]] + question_facets(item["question"])
            ),
            "context_chunks": len(hits),
        }
        row.update(grade_keypoints(answer["answer"], item["keypoints"]))
        row.update(
            retrieval_metrics(answer["retrieved_urls"], item["expected_urls"], settings.final_top_k)
        )
        row.update(citation_metrics(answer["sources"], chunk_lookup, answer["retrieved_urls"]))
        row["status"] = (
            "FAIL"
            if error or not row["answerability_correct"]
            else "PASS"
            if not item["answerable"]
            or (
                row["all_keypoints"]
                and row["page_coverage"] == 1
                and row["citation_precision"] == 1
            )
            else "PARTIAL"
            if answer["answerable"]
            else "FAIL"
        )
        rows.append(row)
        print(
            f"{item['id']}: coverage={row['keypoint_coverage']} answerability={row['answerability_correct']}",
            flush=True,
        )
    ablations = {}
    for mode, diversify, top_k in [
        ("hybrid", True, 5),
        ("hybrid", False, 5),
        ("dense", False, 5),
        ("bm25", False, 5),
        ("hybrid", True, 3),
        ("hybrid", True, 8),
    ]:
        alternate = Agent(
            settings.model_copy(
                update={"retrieval_mode": mode, "diversify": diversify, "final_top_k": top_k}
            )
        )
        scores = []
        latency = []
        for item in items:
            if not item["expected_urls"]:
                continue
            started = time.perf_counter()
            result, ablation_usage = alternate.retriever.retrieve_with_usage(item["question"])
            add_usage(
                auxiliary_usage["retrieval_ablations"], ablation_usage.model_dump(mode="json")
            )
            latency.append((time.perf_counter() - started) * 1000)
            scores.append(
                retrieval_metrics(
                    [hit.chunk.source_url for hit in result.hits], item["expected_urls"], top_k
                )
            )
        ablations[f"{mode}, diversity {'on' if diversify else 'off'}, k={top_k}"] = {
            "hit_at_k": mean(float(s["hit_at_k"] or 0) for s in scores),
            "mrr": mean(float(s["reciprocal_rank"] or 0) for s in scores),
            "page_coverage": mean(float(s["page_coverage"] or 0) for s in scores),
            "mean_wall_ms": mean(latency),
        }
    now = datetime.now(UTC)
    if not rag_agent.__file__:
        raise ValueError("Cannot fingerprint the installed source package")
    package_dir = Path(rag_agent.__file__).parent
    report: dict[str, Any] = {
        "run_id": now.strftime("%Y%m%dT%H%M%SZ"),
        "timestamp_utc": now.isoformat(),
        "provider": settings.provider,
        "benchmark_version": benchmark.get("version", 1) if isinstance(benchmark, dict) else 1,
        "benchmark_name": benchmark.get("name", questions.stem)
        if isinstance(benchmark, dict)
        else questions.stem,
        "benchmark_path": questions.as_posix(),
        "benchmark_sha256": hashlib.sha256(questions.read_bytes()).hexdigest(),
        "benchmark_provenance": benchmark.get("source_provenance", {})
        if isinstance(benchmark, dict)
        else {},
        "benchmark_notes": benchmark.get("notes", "") if isinstance(benchmark, dict) else "",
        "answer_mode": "extractive" if settings.provider == "local" else "synthesis",
        "top_k": settings.final_top_k,
        "initialization_ms": initialization_ms,
        "agent_initialization_ms": agent_initialization_ms,
        "model_warmup_ms": model_warmup_ms,
        "initialization_usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "embedding_tokens": 0,
            "estimated_usd": 0.0,
        },
        "timing_caveat": (
            "Local encoder loading was explicitly forced during initialization; no cacheable embedding warmup was used. Query timings include inference and any remaining first-use work."
            if settings.provider == "local"
            else "Agent/index initialization makes no provider warmup call. Query wall times include provider request/framing, synthesis, semantic verification and retries. Embedding-cache hits can skip paid encoding."
        ),
        "settings": {
            "retrieval_mode": settings.retrieval_mode,
            "diversify": settings.diversify,
            "min_relevance": settings.min_relevance,
            "local_embedding_model": settings.local_embedding_model,
            "llm_model": settings.llm_model,
            "embedding_model": settings.embedding_model,
            "verify_with_llm": settings.verify_with_llm,
            "llm_max_retries": settings.llm_max_retries,
            "llm_max_output_tokens": settings.llm_max_output_tokens,
        },
        "corpus": {
            "pages": len(pages),
            "chunks": len(chunk_items),
            "chunk_tokens": sum(c["token_count"] for c in chunk_items),
            "chunks_sha256": hashlib.sha256(chunk_bytes).hexdigest(),
        },
        "gold_validation": gold_validation,
        "source_sha256": {
            name: hashlib.sha256((package_dir / name).read_bytes()).hexdigest()
            for name in [
                "graph.py",
                "retriever.py",
                "grounding.py",
                "prompts.py",
                "config.py",
                "embeddings.py",
                "vectorstore.py",
                "cost.py",
                "schemas.py",
            ]
        },
        "overall": aggregate(rows),
        "by_category": {
            category: aggregate([r for r in rows if r["category"] == category])
            for category in sorted({r["category"] for r in rows})
        },
        "by_split": {
            split: aggregate([r for r in rows if r["split"] == split])
            for split in sorted({r["split"] for r in rows})
        },
        "retrieval_ablations": ablations,
        "questions": rows,
        "agent_stats": agent.stats(),
        "auxiliary_usage": auxiliary_usage,
    }
    ingest_path = settings.data_dir / "ingest_report.json"
    if ingest_path.exists():
        report["ingestion"] = json.loads(ingest_path.read_text(encoding="utf-8"))
    first_ingest_path = (
        Path("artifacts/ingest-output.json")
        if settings.provider == "local"
        else Path("artifacts/openai-ingest-output.json")
    )
    if first_ingest_path.exists() and first_ingest_path.stat().st_size:
        first = json.loads(first_ingest_path.read_text(encoding="utf-8"))
        if (
            first.get("index_version") == index_info.get("index_version")
            and first.get("provider") == settings.provider
        ):
            report["first_ingestion"] = first
    development = [r for r in rows if r["split"] == "dev" and "retrieval" in r["timings_ms"]]
    report["threshold_diagnostics"] = []
    for threshold in [0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60] if development else []:
        positives = [r for r in development if r["expected_answerable"]]
        negatives = [r for r in development if not r["expected_answerable"]]
        report["threshold_diagnostics"].append(
            {
                "threshold": threshold,
                "answerable_gate_refusal_rate": mean(
                    r["retrieval_score"] < threshold for r in positives
                )
                if positives
                else None,
                "unanswerable_gate_refusal_rate": mean(
                    r["retrieval_score"] < threshold for r in negatives
                )
                if negatives
                else None,
            }
        )
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    generate_evaluation_report(report, out)
    generate_cost_report(report, out)
    return report


def main() -> None:
    """Expose configured-provider evaluation with explicit input/output paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("evaluation/questions.json"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args()
    report = run_evaluation(Settings(), args.questions, args.out)
    print(json.dumps(report["overall"], indent=2))


if __name__ == "__main__":
    main()
