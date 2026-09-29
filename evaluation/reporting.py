"""Reports explicitly separate observations, token estimates, and hypothetical costs."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from rag_agent.config import PRICING, PRICING_AS_OF


def fmt(value: float | int | None, percent: bool = False) -> str:
    """Keep undefined diagnostics visibly separate from measured zero."""
    if value is None:
        return "n/a"
    return f"{value:.1%}" if percent else f"{value:.3f}"


def interval(item: dict[str, Any]) -> str:
    """Show the actual numerator/denominator with its descriptive interval."""
    if not item["trials"]:
        return "n/a"
    return (
        f"{item['successes']}/{item['trials']} ({item['rate']:.1%}; "
        f"95% CI {item['low']:.1%}–{item['high']:.1%})"
    )


def measurement_notes(report: dict[str, Any]) -> str:
    """Describe the selected provider and recorded setup without claiming semantic quality."""
    timing = report.get("timing_caveat")
    if timing is None:
        timing = (
            "Archived local setup used a cacheable warmup that did not guarantee encoder loading; any lazy model work remains in query timing."
            if report["provider"] == "local"
            else "Agent/index initialization is separate; no paid warmup request is made. Query timings include provider request, generation, verification and retry work."
        )
    provider = (
        "Local excerpt mode was measured; paid synthesis was not exercised in this run."
        if report["provider"] == "local"
        else "Paid synthesis was selected; inspect returned token metadata, errors and verification settings for actual execution."
    )
    return (
        f"{provider} {timing} Regex keypoint coverage and exact quotation provenance do not establish semantic faithfulness or human correctness. "
        "Independent semantic evaluation and human rating remain unmeasured; production quality is not established."
    )


def generate_cost_report(report: dict[str, Any], out: Path) -> str:
    """Write a standalone cost analysis beside results; return its markdown."""
    rows = report["questions"]
    usage = [r.get("usage", {}) for r in rows]
    input_tokens = sum(u.get("input_tokens", 0) for u in usage)
    output_tokens = sum(u.get("output_tokens", 0) for u in usage)
    embedding_tokens = sum(u.get("embedding_tokens", 0) for u in usage)
    estimated = sum(u.get("estimated_usd", 0) for u in usage)
    n = len(rows)
    if not rows:
        raise ValueError("Cannot report costs for an empty evaluation")
    paid = report["provider"] != "local"
    auxiliary = report.get("auxiliary_usage", {})
    auxiliary_cost = sum(u.get("estimated_usd", 0) for u in auxiliary.values())
    token_sources = ", ".join(sorted({u.get("token_source", "unknown") for u in usage}))
    chunks = report.get("corpus", {}).get("chunk_tokens", 0)
    constructed = [r["counterfactual_tokens"] for r in rows]
    averages = {
        key: sum(t[key] for t in constructed) / n for key in ["input", "output", "query_embedding"]
    }
    p95 = {
        key: sorted(t[key] for t in constructed)[max(0, math.ceil(0.95 * n) - 1)]
        for key in averages
    }
    per_query = (
        averages["input"] * PRICING["input"]
        + averages["output"] * PRICING["output"]
        + averages["query_embedding"] * PRICING["embedding"]
    ) / 1_000_000
    answered = [r for r in rows if r["actual_answerable"]]
    gate_cost = (
        sum(
            (
                r["counterfactual_tokens"]["input"] * PRICING["input"]
                + r["counterfactual_tokens"]["output"] * PRICING["output"]
            )
            / 1_000_000
            for r in answered
        )
        / n
        + averages["query_embedding"] * PRICING["embedding"] / 1_000_000
    )
    projected_rate = estimated / n if paid else per_query
    projections = "\n".join(
        (
            f"| {volume:,} | ${volume * projected_rate:.4f} | ${volume * projected_rate * 0.7:.4f} |"
            if paid
            else f"| {volume:,} | ${volume * per_query:.4f} | ${volume * per_query * 0.7:.4f} | ${volume * gate_cost:.4f} | $0.00 |"
        )
        for volume in [100, 1000, 10000]
    )
    example = next((r for r in rows if r["actual_answerable"]), rows[0])
    example_tokens = example["counterfactual_tokens"]
    example_cost = (
        example_tokens["input"] * PRICING["input"]
        + example_tokens["output"] * PRICING["output"]
        + example_tokens["query_embedding"] * PRICING["embedding"]
    ) / 1_000_000
    ingestions = []
    for label, key in [
        ("Initial real ingestion", "first_ingestion"),
        ("Latest saved rebuild", "ingestion"),
    ]:
        observed = report.get(key)
        if observed:
            ingestion_usage = observed.get("usage", {})
            ingestions.append(
                f"| {label} | {observed.get('created_at', 'n/a')} | {observed.get('elapsed_seconds', 0):.3f} | {observed.get('embedding_cache_hits', 0)} | {ingestion_usage.get('embedding_tokens', 0):,} | ${ingestion_usage.get('estimated_usd', 0):.6f} |"
            )
    if paid:
        comparison = f"""## Observed provider usage extrapolation — scenario, not invoice

Mean observed answer-query API cost estimate: **${projected_rate:.6f}/query**, including the synthesis and verification/retry usage returned by the agent. Chat token-source labels in this run: **{token_sources}**. API-reported chat token counts include provider framing where metadata is returned; fallback counts and all embedding counts remain local text estimates. Failed calls or automatic client retries without returned usage can undercount spend. Auxiliary retrieval ablations are charged separately and excluded from this per-answer rate.

| Query volume | Observed per-query rate extrapolated | Assumed 30% cache hits |
|---|---:|---:|
{projections}

The no-cache column extrapolates this small benchmark's actual mix of responses, refusals and retries. The cache column assumes 30% of requests incur no new provider work. Neither column is a measured load test or a billing guarantee. Refusals can already include paid generation/verification before refusal, so no additional zero-cost refusal discount is applied.

Example question: **{example["question"]}**. Observed returned usage: **{example["usage"].get("input_tokens", 0)}/{example["usage"].get("output_tokens", 0)}/{example["usage"].get("embedding_tokens", 0)}** input/output/estimated embedding tokens; observed API cost estimate **${example["usage"].get("estimated_usd", 0):.6f}**.

Stored reconstructed prompt/answer text counts are diagnostics, not a second usage ledger: mean input/output **{averages["input"]:.1f}/{averages["output"]:.1f}** tokens. They omit chat framing, schemas, semantic-check prompts and retries and can differ from the actual provider request. They are not used to replace or discount the usage above. The archived local report retains its separate hypothetical OpenAI comparison.
"""
    else:
        comparison = f"""## Hypothetical OpenAI comparison — not measured

For each local question, the runner constructed a synthesis prompt from a fresh retrieval of the original question and counted its system/user text and the returned extractive answer with tiktoken. The original-query bundle can differ from a retried graph's final trace. Observed local candidate-sentence embedding text is separate from the hypothetical question/facet retrieval embeddings. Mean (p95) counterfactual input: **{averages["input"]:.1f} ({p95["input"]})**, output: **{averages["output"]:.1f} ({p95["output"]})**, query/facet embedding: **{averages["query_embedding"]:.1f} ({p95["query_embedding"]})** tokens. These are measured text lengths, not measured OpenAI usage. Chat framing, structured-output schemas, verification/retry prompts and a different generated answer would change billing. Illustrative cost: **${per_query:.6f}/query** before those overheads.

Example question: **{example["question"]}**. Retrieved context chunks: **{example_tokens["context_chunks"]}**. Constructed input/output/query embedding text: **{example_tokens["input"]}/{example_tokens["output"]}/{example_tokens["query_embedding"]}** tokens; hypothetical cost **${example_cost:.6f}**; observed query API cost **${example["usage"].get("estimated_usd", 0):.6f}**.

| Query volume | Hypothetical no cache | Hypothetical 30% cache hits | Hypothetical observed refusal gating | Observed local API rate projected |
|---|---:|---:|---:|---:|
{projections}

Gating assumes synthesis is omitted on the observed refused local questions ({(n - len(answered)) / n:.1%}), retaining estimated query embedding cost. The 30% cache scenario assumes no provider work on a hit. These are scenarios, not measured load or billing. A hypothetical single embedding of {chunks:,} chunk text tokens costs **${chunks * PRICING["embedding"] / 1_000_000:.6f}**; provider tokenization can differ.
"""
    text = f"""# Cost analysis

Generated from `{report["run_id"]}` on {report["timestamp_utc"]}. Provider: **{report["provider"]}**.

## Observed run

| Quantity | Value |
|---|---:|
| Questions attempted, cache disabled | {n} |
| Query input tokens reported by the agent | {input_tokens:,} |
| Query output tokens reported by the agent | {output_tokens:,} |
| Query embedding tokens reported by the agent | {embedding_tokens:,} |
| Query API cost estimate from usage records | ${estimated:.6f} |
| Auxiliary retrieval/reporting API cost estimate | ${auxiliary_cost:.6f} |
| Query plus auxiliary API cost estimate, excludes ingestion | ${estimated + auxiliary_cost:.6f} |
| Total embedded chunk text tokens (includes headers) | {chunks:,} |

{"The run used local sentence-transformer embeddings and deterministic extractive answers. It made no paid model API calls, so API spend was $0. Token counts are local tiktoken estimates, not provider billable usage. CPU, RAM, disk, bandwidth, electricity and host costs were not measured; $0 API spend does not mean zero operating cost." if report["provider"] == "local" else "Provider usage records feed the cost estimate. The estimate is not an invoice and does not verify account-level billing. Failed calls, retries and usage not returned by the provider can cause uncertainty; inspect the per-question records."}

## Saved ingestion observations

| Ingestion | Created UTC | Wall seconds | Embedding cache hits | Miss text tokens estimated | API cost estimate |
|---|---|---:|---:|---:|---:|
{chr(10).join(ingestions) or "| Not captured in this query report | n/a | n/a | n/a | n/a | n/a |"}

The ingestion rows are separate observations and must not be summed when they identify the same run. A cached rebuild can report zero new embedding tokens while retaining the same corpus. Chunk token counts include title/heading headers. Embedding tokens are tiktoken estimates of text sent or locally encoded on cache misses, not API-returned embedding billing metadata. {"Paid embedding estimates use the configured standard rate." if paid else "Local candidate-sentence encoding is also counted as text volume, with zero API charge."}

## Standard pricing used for estimates

Pricing checked {PRICING_AS_OF}: GPT-4o mini input **${PRICING["input"]:.2f}/1M** and output **${PRICING["output"]:.2f}/1M**, text-embedding-3-small **${PRICING["embedding"]:.2f}/1M**. Sources: [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small). These are standard token rates; no batch/cache discount is assumed.

{comparison}

## Five cost levers

1. Cache: a 30% hit rate reduces the illustrative query API cost by 30%, assuming cache hits skip embedding and synthesis.
2. Refusal gate: refusing before synthesis can reduce generation work, balanced against false refusals. A refusal after paid generation/verification still incurs that cost.
3. Smaller top-k: removing 200 context tokens would save about **${200 * PRICING["input"] / 1_000_000:.6f}** per synthesized query; retrieval coverage can fall, so use the measured ablation.
4. Prompt trimming: eliminating 100 input tokens saves **${100 * PRICING["input"] / 1_000_000:.6f}** per synthesized query; remove boilerplate before evidence.
5. Model tiering/local excerpts: the archived local run had $0 API cost. Compare paid synthesis quality on the actual saved benchmark; no semantic-quality improvement is inferred from model selection alone.

The default local embedding index cannot be reused as an OpenAI index: reingestion is required when the embedding identity changes. Context limits, output caps, batching, bounded retries and the answer cache constrain cost. A cache hit should report zero new query API usage; evaluation disables the cache so every result measures fresh query work. Monthly extrapolation is a scenario, not an observed load test or budget guarantee.
"""
    target = out if out.suffix.lower() == ".md" else out / "COST_ANALYSIS.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return text


def generate_evaluation_report(report: dict[str, Any], out: Path) -> str:
    """Render saved diagnostics and their limitations without running a judge."""
    overall = report["overall"]
    table = []
    for name, group in report["by_category"].items():
        table.append(
            f"| {name} | {group['count']} | {fmt(group['keypoint_coverage'], True)} | "
            f"{fmt(group['hit_at_k']['rate'], True)} | {fmt(group['mrr'])} | "
            f"{fmt(group['page_coverage'], True)} | {fmt(group['answerability_accuracy']['rate'], True)} |"
        )
    split = []
    for name, group in report["by_split"].items():
        split.append(
            f"| {name} | {group['count']} | {fmt(group['keypoint_coverage'], True)} | "
            f"{fmt(group['hit_at_k']['rate'], True)} | {fmt(group['mrr'])} | "
            f"{interval(group['unanswerable_refusal'])} |"
        )
    question_rows = []
    for row in report["questions"]:
        question_rows.append(
            f"| {row['id']} | {row['split']} | {row['category']} | "
            f"{fmt(row['keypoint_coverage'], True)} | {fmt(row['hit_at_k'])} | "
            f"{fmt(row['page_coverage'], True)} | {'yes' if row['answerability_correct'] else 'no'} | "
            f"{row['wall_ms']:.0f} | {row.get('status', 'FAIL' if row.get('error') or not row['answerability_correct'] else 'PASS' if row.get('all_keypoints') is not False else 'PARTIAL')} |"
        )
    ablations = []
    for name, result in report.get("retrieval_ablations", {}).items():
        ablations.append(
            f"| {name} | {fmt(result['hit_at_k'], True)} | {fmt(result['mrr'])} | "
            f"{fmt(result['page_coverage'], True)} | {result['mean_wall_ms']:.1f} |"
        )
    failures = [
        r
        for r in report["questions"]
        if r.get("error")
        or not r["answerability_correct"]
        or r.get("all_keypoints") is False
        or r.get("page_coverage") not in {1, None}
    ]
    failure_text = (
        "\n".join(
            f"- **{r['id']}**: {r.get('error') or ('answerability mismatch; inspect gate score and evidence selection' if not r['answerability_correct'] else 'missing keypoints: ' + ', '.join(p['label'] for p in r['keypoints'] if not p['matched']))}. "
            + (
                "Expected-page retrieval miss or incomplete multi-page coverage. "
                if r.get("page_coverage") not in {1, None}
                else ""
            )
            + (
                "Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. "
                if r.get("all_keypoints") is False
                else ""
            )
            + "Next step: inspect development evidence and improve selection/composition against development questions only."
            for r in failures
        )
        or "No deterministic benchmark failures in this run."
    )
    thresholds = "\n".join(
        f"| {r['threshold']:.2f} | {fmt(r['answerable_gate_refusal_rate'], True)} | {fmt(r['unanswerable_gate_refusal_rate'], True)} |"
        for r in report.get("threshold_diagnostics", [])
    )
    stages = "\n".join(
        f"| {stage} | {values['p50']:.1f} | {values['p95']:.1f} |"
        for stage, values in overall["stage_percentiles_ms"].items()
    )
    history = "\n".join(
        f"| {r['round']} | {fmt(r['dev_keypoint_coverage'], True)} | {fmt(r['holdout_keypoint_coverage'], True)} | {r['change']} |"
        for r in report.get("improvement_history", [])
    )
    benchmark = report.get("earlier_cli_benchmark")
    benchmark_text = ""
    if benchmark:
        total = benchmark["total"]
        benchmark_text = f"""## Separate earlier CLI benchmark

`artifacts/benchmark.json` records an earlier implementation: {benchmark["runs"]} uncached runs over {benchmark["unique_questions"]} unique questions, with cold/lazy model work included. Wall mean/p50/p95 were **{total["mean_ms"]:.1f}/{total["p50_ms"]:.1f}/{total["p95_ms"]:.1f} ms** and API cost was **${benchmark["estimated_usd"]:.6f}**. This artifact has no matching frozen source fingerprint and is not the final dev/holdout evaluation. Its repeated questions, cache state and timing setup differ, so it is not a like-for-like latency improvement measurement.

"""
    timing_note = measurement_notes(report)
    independent = "independent_holdout" in report["by_split"]
    scoring_history = (
        "Original baseline outputs are retained in `baseline_original.json`. Two development-only synonym corrections were applied to the scorer (item/element and explicit denial of tuple item assignment), then original raw answers were rescored as `baseline.json`. Before/after comparison uses the same revised expressions. Gold facts/URLs and holdout patterns did not change; this scoring revision is not an agent improvement. Split source/settings/corpus hashes must match before a merge."
        if report.get("improvement_history")
        else "This run does not establish a before/after improvement on the archived local benchmark. The independent holdout has different questions and cannot support a like-for-like provider improvement percentage. Its gold expressions must remain frozen; investigate failures on development data and use a fresh independent test for later revisions."
        if independent
        else "No comparable improvement history was attached. Keep question/gold/code/settings/corpus versions explicit before comparing runs; tune on development data and use a fresh independent holdout for the final choice."
    )
    text = f"""# Evaluation

Run `{report["run_id"]}`, {report["timestamp_utc"]}. Corpus: {report["corpus"].get("pages", "unknown")} pages / {report["corpus"].get("chunks", "unknown")} chunks from [Python documentation](https://docs.python.org/3/tutorial/index.html). Corpus SHA-256: `{report["corpus"].get("chunks_sha256", "unknown")}`. Provider: **{report["provider"]}**; mode: **{report["answer_mode"]}**; top-k: **{report["top_k"]}**. Answer cache disabled. Agent/index initialization: **{report["initialization_ms"]:.0f} ms**, separate from query wall time. Recorded local encoder warmup: **{report.get("model_warmup_ms", 0):.0f} ms**; paid warmup requests: **0**.

**Semantic production quality is not established.** Inspect keypoint misses, false answers/refusals, confidence intervals and query latency; exact source quotes can still support an irrelevant or incomplete answer.

Provider and timing notes: {timing_note}

## What was measured

The **{len(report["questions"])}-question** file uses explicit split labels and source-checked gold points. Benchmark: **{report.get("benchmark_name", "stored source-check benchmark")}**. Development data supports implementation/threshold selection; holdout outputs must not be used for tuning. This small hand-written set is not a generalization guarantee. Corpus validation checks required pages and each gold regex component in the actual stored page. No independent evaluation LLM judge was used. Production provider self-checks are part of the answering path, not an independent faithfulness score. The answer cache is disabled; the content-addressed embedding cache remains enabled and can avoid repeated query encoding. New local evaluations explicitly load the encoder during initialization; paid mode makes no initialization embedding or synthesis call. The archived local timing setup is preserved separately.

Benchmark provenance: **{report.get("benchmark_sha256", "not recorded")}**. {report.get("benchmark_notes", "Split labels alone do not guarantee that a question was never previously inspected.")}

Source provenance notes: {report.get("source_provenance_notes", "Saved source hashes identify the package files captured for this run.")}

Keypoint coverage is a deterministic case-insensitive regex proxy over the returned answer. It can miss valid paraphrases and can reward a matching quote without a useful explanation. **It is not semantic faithfulness, answer correctness, hallucination rate, or a human rating.** Exact citation support checks nonempty evidence as a whitespace-normalized substring of its stored chunk, preserving case and Unicode characters, matching the source URL and that URL appearing in the retrieval trace. The response trace stores URLs rather than every retrieved chunk ID; this metric checks URL-level provenance, while the graph verifies IDs against its actual retrieval hits. It proves quotation provenance, not logical claim entailment. No independent semantic audit of each claim was performed. Production self-check setting: **{report.get("settings", {}).get("verify_with_llm", "not recorded")}**.

Retrieval Hit@k asks whether any expected URL occurs in the first k distinct retrieved URLs, MRR uses the first such URL, and page coverage counts all expected URLs. Unanswerable questions have no expected URLs and are excluded from retrieval/keypoint averages. The corpus snapshot is the authority: outside-corpus facts must refuse even when a pretrained model might know them. Misleading questions are answerable and need the corrective gold evidence.

## Overall observations

- Mean keypoint coverage: **{fmt(overall["keypoint_coverage"], True)}**; all-keypoint questions: {interval(overall["all_keypoints"])}.
- Hit@{report["top_k"]}: {interval(overall["hit_at_k"])}; MRR: **{fmt(overall["mrr"])}**; mean page coverage: **{fmt(overall["page_coverage"], True)}**.
- Exact supported citations: {interval(overall["citation_exact_quote"])}. This denominator is citations; multiple citations per answer are correlated, so its interval is descriptive.
- Answerability decisions: {interval(overall["answerability_accuracy"])}; refusal on unanswerable: {interval(overall["unanswerable_refusal"])}; responses on answerable: {interval(overall["answerable_response"])}.
- False-answer rate on unanswerable: {interval(overall["false_answer"])}; false-refusal rate on answerable: {interval(overall["false_refusal"])}; answerable responses with every citation supported: {interval(overall["all_citations_supported"])}.
- Query wall latency: mean **{overall["mean_wall_ms"]:.1f} ms**, empirical nearest-rank p50 **{overall["p50_wall_ms"]:.1f} ms**, p95 **{overall["p95_wall_ms"]:.1f} ms**. Errors: **{overall["errors"]}**. Small-sample Wilson intervals are 95%; they do not account for question selection bias.

| Category | N | Keypoint coverage | Hit@k | MRR | Page coverage | Answerability |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(table)}

| Split | N | Keypoint coverage | Hit@k | MRR | Unanswerable refusal (95% CI) |
|---|---:|---:|---:|---:|---|
{chr(10).join(split)}

## Retrieval ablations

The same frozen questions and index are used; only retrieval mode/diversification changes. These are retrieval-only runs, so they do not measure generation quality. Initial model loading is excluded.

| Retrieval configuration | Hit@k | MRR | Page coverage | Mean wall ms |
|---|---:|---:|---:|---:|
{chr(10).join(ablations) or "| Not run | n/a | n/a | n/a | n/a |"}

The LLM-self-check on/off and 400/600/900-token reindexing ablations are **NOT YET MEASURED** in this report. Selecting a self-check setting is not an on/off comparison. Larger chunks require their own quality/reindexing measurement; the local MiniLM encoder segments oversized text into 220-wordpiece windows. Reported diversification is a greedy source-count penalty, not full vector-pair MMR. Retrieval ablations can incur paid embedding misses; auxiliary usage is recorded separately from answer-query usage in the cost report.

## Dev-only gate diagnostic

This table simulates the relevance gate on the stored best dense scores from development questions that actually reached retrieval. Preblocked injections and errors without retrieval are excluded, rather than treated as zero-score gate successes. It does not rerun extraction/verification, and later refusals are not attributed to the gate. Holdout questions were excluded. The configured threshold was not selected from holdout results.

| Candidate minimum score | Answerable rejected at gate | Unanswerable rejected at gate |
|---|---:|---:|
{thresholds}

## Stage latency

One measurement per attempted question; index loaded at startup, with embedding cache reuse and the lazy encoder caveat above. Stage times may overlap or be aggregate times, so do not sum every row.

| Stage | p50 ms | p95 ms |
|---|---:|---:|
{stages}

{benchmark_text}## Per-question diagnostics

Full question text, raw answer, citations, keypoints, token estimates and per-stage timing are in `results.json`. Gold evidence and scoring expressions are in `evaluation/questions.json`. Corpus validation is recorded in `gold_validation`.

| ID | Split | Category | Keypoint coverage | Hit@k | Page coverage | Answerability correct | Wall ms | Status |
|---|---|---|---:|---:|---:|---|---:|---|
{chr(10).join(question_rows)}

## Failures to inspect

{failure_text}

## Reproduce and improve

Run `python -m evaluation.run_eval --questions {report.get("benchmark_path", "evaluation/questions.json")} --out results`, using this report's provider and data directory settings. Hardware, network/provider latency, embedding-cache state and source revisions affect results. Initialization and query wall times are separate. Page/source hashes and dependency locks identify drift. Tune on development data only, then freeze code before a fresh independent holdout. Human claim-entailment review and a larger independently authored benchmark remain necessary. Do not interpret this small set as production readiness.

| Round | Dev regex coverage | Holdout regex coverage | Change |
|---|---:|---:|---|
{history or "| Baseline only | see split table | see split table | No implementation improvement measured yet |"}

{scoring_history}

## How to interpret these numbers

1. The corpus is a bounded snapshot, not the entire Python documentation.
2. Scores depend on this snapshot's URLs and extracted text.
3. {len(report["questions"])} authored questions are a small sample; only the independent split was new final testing.
4. Hand-written questions create selection bias.
5. Paired paraphrases are correlated observations.
6. Multi-page questions count each required URL.
7. Hit@k only measures retrieval of a page.
8. MRR rewards an earlier relevant page.
9. Page coverage does not prove useful evidence was selected.
10. Regex keypoints are a transparent diagnostic proxy.
11. Equivalent paraphrases may be scored as misses.
12. Incidental keyword matches can receive credit.
13. Exact quotations establish source provenance.
14. Provenance does not establish logical entailment.
15. Independent LLM faithfulness evaluation is unmeasured here.
16. Errors count as answerability failures, never correct refusals.
17. Wilson intervals reflect small denominators, not selection bias.
18. Citation intervals ignore within-answer correlation.
19. Initialization, embedding cache reuse and query/provider work must be distinguished when comparing latency.
20. Improvements require development-only tuning and a frozen independent holdout.
"""
    out.mkdir(parents=True, exist_ok=True)
    (out / "EVALUATION.md").write_text(text, encoding="utf-8")
    return text
