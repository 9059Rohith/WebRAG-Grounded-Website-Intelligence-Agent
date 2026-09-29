# End-to-end verification — 29 September 2026

The source, real website ingestion, persistent retrieval, CLI/API, evaluation, cost analysis, architecture diagrams and deployment configuration are implemented. The final measured path uses real OpenAI embeddings and source-only synthesis; a local excerpt fallback needs no paid credentials. **Independent regex coverage and latency targets remain unmet. Semantic production correctness has not been established.**

| Requirement / check | Observed result |
|---|---|
| Public website ingestion | 40 Python documentation pages, zero crawl errors, 1,597 chunks |
| Real embeddings and vector storage | OpenAI text-embedding-3-small 1,536-dimensional vectors; embedded persistent Chroma/BM25; separate real 384-dimensional local fallback |
| Core workflow | Executable LangGraph validation, retrieval, generation, verification, bounded retry and refusal |
| Source grounding | Returned URLs and restored exact website evidence; formal paid evaluation 59/59 supported quotes, independent holdout 11/11; provenance is not entailment |
| Natural-language CLI and API | CLI smoke passes 5/5; live host and Docker APIs pass five query checks, cache and invalid-input checks |
| Evaluation | One formal paid run over 38 source-checked questions: 13 dev, 13 previously inspected holdout, 12 new independent holdout; all five categories, raw outputs/hashes retained |
| Independent held-out diagnostics | 75% regex coverage; Hit@8 8/8; MRR 0.823; unknown refusals 4/4; false refusals 2/8; p50/p95 4.575/10.960 seconds |
| Cost reporting | Formal queries $0.052342 standard-rate estimate; ingestion $0.005539 separately; auxiliary ablations $0; projections and historical local report kept separate |
| Full test suite | Latest full run: 181 passed in 44.64 seconds, 93.83% application coverage; 85% configured gate passes |
| Static checks | Ruff lint/format for 72 files, strict mypy for 26 files, and full Bandit pass |
| Dependency audit | No known vulnerabilities outside five ignored advisory records for four explicitly documented embedded-Chroma scope exceptions; upstream CPU PyTorch release audited |
| Docker | Final paid image built; UID 10001; paid five-query HTTP smoke/cache/422 checks pass; empty-index health=200/readiness=503 |
| Architecture | Rendered SVG and Mermaid; actual compiled LangGraph export |
| Recorded walkthrough | Final paid-run MP4 734.15 seconds, H264/AAC, 12,211,292 bytes; synthetic narration disclosed; decode checks at 0/360/720 seconds pass |
| Paid OpenAI provider | Live embeddings/synthesis/semantic checking measured with gpt-4o-mini/text-embedding-3-small; actual returned usage recorded; invoice reconciliation is unmeasured |
| External delivery | Email draft prepared; no email sent. Hosted Space/Render deployment and remote CI execution are unverified |

<!-- PROVIDER_EVALUATION_START -->
## Final provider and evaluation

Run **20260929T142544Z** selected OpenAI with **top-k 8**, **minimum cosine relevance 0.25**, **900 output tokens**, and **semantic verification enabled**. No provider warmup call was made; agent/index initialization was 1.393 seconds and query wall time includes provider generation, verification and retries. All **38 query attempts completed without errors**.

Overall regex keypoint coverage was **66.1%**, all-keypoint questions **17/28**, retrieval Hit@8 **28/28**, page coverage **98.2%**, exact citation support **59/59**, and unanswerable refusal **10/10**. Four of 28 answerable requests were refused. The new independent set is the headline: **75% coverage**, **6/8 all-keypoint**, **2/8 false refusals**, and **4/4 unknown refusals**. Its small-sample refusal interval spans **51.0%–100%**, so the observed perfect numerator does not establish reliable universal refusal.

The original 26 questions were already inspected during local development. Only the new 12 were unseen before freeze, and their different questions cannot establish a like-for-like provider improvement percentage. Several original misses are regex wording/formula misses; no gold expressions or scores were changed after seeing this run. Production self-checks are part of the answering path, not independent semantic evaluation. Human correctness, faithfulness and inter-rater agreement remain unmeasured.

Returned usage totals: **325,827 input**, **5,760 output** and **583 estimated embedding text tokens**. Query cost estimate **$0.05234171**, auxiliary cost **$0**, initial ingestion estimate **$0.00553854**. These are standard-rate usage estimates, excluding earlier development/smoke calls and hosting, not an account invoice. The paid report retains source/schema/benchmark hashes and documents a nonbehavioral constant/formatting repair; raw answers, scores and original observed bytes remain intact. [Historical local baseline](../evaluation/results/local_baseline/EVALUATION.md) preserves its original timing outliers and $0 API comparison.
<!-- PROVIDER_EVALUATION_END -->

[Evaluation](../EVALUATION.md) records per-question outputs and confidence intervals. Quote provenance does not establish semantic correctness, and the small benchmark cannot establish production readiness. Historical local Docker model download took 144 seconds and a cold local query took 42.67 seconds; those observations are separate from the final paid evaluation.

Evidence is retained in [verification records](verification/), [raw evaluation](../evaluation/results/results.json), and [the recorded walkthrough](video/README.md). The local data folder contains the actual crawl, snapshots and Chroma index; it is excluded from Git and recreated with `rag ingest`.

To repeat the checks after ingestion:

```powershell
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m mypy src/rag_agent evaluation
.venv\Scripts\python.exe -m bandit -q -r src/rag_agent
.venv\Scripts\python.exe scripts/audit_dependencies.py
.venv\Scripts\python.exe -m pytest --cov=rag_agent --cov-report=term-missing --cov-fail-under=85
.venv\Scripts\rag.exe smoke
# Start the API in a separate terminal, then exercise the actual service:
.venv\Scripts\python.exe scripts/verify_live.py
```

The live script is deliberately specific to the default Python documentation corpus. Offline tests use fixtures at network/provider boundaries; the saved real crawl, embeddings and HTTP checks are separate evidence of execution.
