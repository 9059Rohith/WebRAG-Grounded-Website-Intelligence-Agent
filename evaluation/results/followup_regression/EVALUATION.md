# Evaluation

Run `20260929T155105Z`, 2026-09-29T15:51:05.529445+00:00. Corpus: 40 pages / 1597 chunks from [Python documentation](https://docs.python.org/3/tutorial/index.html). Corpus SHA-256: `b2605c51c659bfd6e32e6e71b8544180412ed7870557ffed45f624424a2c2b2d`. Provider: **openai**; mode: **synthesis**; top-k: **8**. Answer cache disabled. Agent/index initialization: **1518 ms**, separate from query wall time. Recorded local encoder warmup: **0 ms**; paid warmup requests: **0**.

**Semantic production quality is not established.** Inspect keypoint misses, false answers/refusals, confidence intervals and query latency; exact source quotes can still support an irrelevant or incomplete answer.

Provider and timing notes: Paid synthesis was selected; inspect returned token metadata, errors and verification settings for actual execution. Agent/index initialization makes no provider warmup call. Query wall times include provider request/framing, synthesis, semantic verification and retries. Embedding-cache hits can skip paid encoding. Regex keypoint coverage and exact quotation provenance do not establish semantic faithfulness or human correctness. Independent semantic evaluation and human rating remain unmeasured; production quality is not established.

## What was measured

The **38-question** file uses explicit split labels and source-checked gold points. Benchmark: **Follow-up regression38: inspected questions, frozen gold unchanged**. Development data supports implementation/threshold selection; holdout outputs must not be used for tuning. This small hand-written set is not a generalization guarantee. Corpus validation checks required pages and each gold regex component in the actual stored page. No independent evaluation LLM judge was used. Production provider self-checks are part of the answering path, not an independent faithfulness score. The answer cache is disabled; the content-addressed embedding cache remains enabled and can avoid repeated query encoding. New local evaluations explicitly load the encoder during initialization; paid mode makes no initialization embedding or synthesis call. The archived local timing setup is preserved separately.

Benchmark provenance: **50f59ddcdf8150ad8dc74d73ac7b7ac2a602660e9a960a75f71dc2cd2cbbb17a**. All 38 questions have previously been inspected. This follow-up repairs known false refusals and is a regression run, not independent held-out evaluation. Original answers, URLs, and gold expressions are unchanged. Original independent baseline remains evaluation/results/results.json.

Source provenance notes: Saved source hashes identify the package files captured for this run.

Keypoint coverage is a deterministic case-insensitive regex proxy over the returned answer. It can miss valid paraphrases and can reward a matching quote without a useful explanation. **It is not semantic faithfulness, answer correctness, hallucination rate, or a human rating.** Exact citation support checks nonempty evidence as a whitespace-normalized substring of its stored chunk, preserving case and Unicode characters, matching the source URL and that URL appearing in the retrieval trace. The response trace stores URLs rather than every retrieved chunk ID; this metric checks URL-level provenance, while the graph verifies IDs against its actual retrieval hits. It proves quotation provenance, not logical claim entailment. No independent semantic audit of each claim was performed. Production self-check setting: **True**.

Retrieval Hit@k asks whether any expected URL occurs in the first k distinct retrieved URLs, MRR uses the first such URL, and page coverage counts all expected URLs. Unanswerable questions have no expected URLs and are excluded from retrieval/keypoint averages. The corpus snapshot is the authority: outside-corpus facts must refuse even when a pretrained model might know them. Misleading questions are answerable and need the corrective gold evidence.

## Overall observations

- Mean keypoint coverage: **78.6%**; all-keypoint questions: 20/28 (71.4%; 95% CI 52.9%–84.7%).
- Hit@8: 28/28 (100.0%; 95% CI 87.9%–100.0%); MRR: **0.789**; mean page coverage: **96.4%**.
- Exact supported citations: 61/61 (100.0%; 95% CI 94.1%–100.0%). This denominator is citations; multiple citations per answer are correlated, so its interval is descriptive.
- Answerability decisions: 37/38 (97.4%; 95% CI 86.5%–99.5%); refusal on unanswerable: 10/10 (100.0%; 95% CI 72.2%–100.0%); responses on answerable: 27/28 (96.4%; 95% CI 82.3%–99.4%).
- False-answer rate on unanswerable: 0/10 (0.0%; 95% CI 0.0%–27.8%); false-refusal rate on answerable: 1/28 (3.6%; 95% CI 0.6%–17.7%); answerable responses with every citation supported: 27/27 (100.0%; 95% CI 87.5%–100.0%).
- Query wall latency: mean **4691.2 ms**, empirical nearest-rank p50 **5424.9 ms**, p95 **8817.5 ms**. Errors: **0**. Small-sample Wilson intervals are 95%; they do not account for question selection bias.

| Category | N | Keypoint coverage | Hit@k | MRR | Page coverage | Answerability |
|---|---:|---:|---:|---:|---:|---:|
| misleading | 7 | 71.4% | 100.0% | 0.786 | 100.0% | 100.0% |
| multi-page | 7 | 71.4% | 100.0% | 0.810 | 85.7% | 100.0% |
| paraphrased | 7 | 71.4% | 100.0% | 0.893 | 100.0% | 85.7% |
| straightforward | 7 | 100.0% | 100.0% | 0.667 | 100.0% | 100.0% |
| unanswerable | 10 | n/a | n/a | n/a | n/a | 100.0% |

| Split | N | Keypoint coverage | Hit@k | MRR | Unanswerable refusal (95% CI) |
|---|---:|---:|---:|---:|---|
| regression_dev | 13 | 60.0% | 100.0% | 0.692 | 3/3 (100.0%; 95% CI 43.9%–100.0%) |
| regression_holdout | 13 | 80.0% | 100.0% | 0.858 | 3/3 (100.0%; 95% CI 43.9%–100.0%) |
| regression_independent_holdout | 12 | 100.0% | 100.0% | 0.823 | 4/4 (100.0%; 95% CI 51.0%–100.0%) |

## Retrieval ablations

The same frozen questions and index are used; only retrieval mode/diversification changes. These are retrieval-only runs, so they do not measure generation quality. Initial model loading is excluded.

| Retrieval configuration | Hit@k | MRR | Page coverage | Mean wall ms |
|---|---:|---:|---:|---:|
| hybrid, diversity on, k=5 | 92.9% | 0.771 | 89.3% | 36.4 |
| hybrid, diversity off, k=5 | 92.9% | 0.771 | 87.5% | 43.8 |
| dense, diversity off, k=5 | 89.3% | 0.815 | 87.5% | 40.9 |
| bm25, diversity off, k=5 | 96.4% | 0.754 | 89.3% | 40.6 |
| hybrid, diversity on, k=3 | 89.3% | 0.762 | 82.1% | 56.2 |
| hybrid, diversity on, k=8 | 100.0% | 0.789 | 96.4% | 23.8 |

The LLM-self-check on/off and 400/600/900-token reindexing ablations are **NOT YET MEASURED** in this report. Selecting a self-check setting is not an on/off comparison. Larger chunks require their own quality/reindexing measurement; the local MiniLM encoder segments oversized text into 220-wordpiece windows. Reported diversification is a greedy source-count penalty, not full vector-pair MMR. Retrieval ablations can incur paid embedding misses; auxiliary usage is recorded separately from answer-query usage in the cost report.

## Dev-only gate diagnostic

This table simulates the relevance gate on the stored best dense scores from development questions that actually reached retrieval. Preblocked injections and errors without retrieval are excluded, rather than treated as zero-score gate successes. It does not rerun extraction/verification, and later refusals are not attributed to the gate. Holdout questions were excluded. The configured threshold was not selected from holdout results.

| Candidate minimum score | Answerable rejected at gate | Unanswerable rejected at gate |
|---|---:|---:|


## Stage latency

One measurement per attempted question; index loaded at startup, with embedding cache reuse and the lazy encoder caveat above. Stage times may overlap or be aggregate times, so do not sum every row.

| Stage | p50 ms | p95 ms |
|---|---:|---:|
| bm25 | 25.2 | 80.5 |
| dense | 6.6 | 33.4 |
| embedding | 21.3 | 108.4 |
| fusion | 0.4 | 1.0 |
| generation | 3465.2 | 5915.7 |
| retrieval | 60.0 | 206.6 |
| total | 5424.1 | 8816.4 |
| verification | 1926.6 | 3380.9 |

## Per-question diagnostics

Full question text, raw answer, citations, keypoints, token estimates and per-stage timing are in `results.json`. Gold evidence and scoring expressions are in `evaluation/questions.json`. Corpus validation is recorded in `gold_validation`.

| ID | Split | Category | Keypoint coverage | Hit@k | Page coverage | Answerability correct | Wall ms | Status |
|---|---|---|---:|---:|---:|---|---:|---|
| s1 | regression_dev | straightforward | 100.0% | 1.000 | 100.0% | yes | 8817 | PASS |
| s2 | regression_dev | straightforward | 100.0% | 1.000 | 100.0% | yes | 4287 | PASS |
| s3 | regression_holdout | straightforward | 100.0% | 1.000 | 100.0% | yes | 5537 | PASS |
| s4 | regression_dev | straightforward | 100.0% | 1.000 | 100.0% | yes | 4035 | PASS |
| s5 | regression_holdout | straightforward | 100.0% | 1.000 | 100.0% | yes | 5457 | PASS |
| p1 | regression_dev | paraphrased | 100.0% | 1.000 | 100.0% | yes | 4868 | PASS |
| p2 | regression_dev | paraphrased | 0.0% | 1.000 | 100.0% | no | 7842 | FAIL |
| p3 | regression_holdout | paraphrased | 100.0% | 1.000 | 100.0% | yes | 5536 | PASS |
| p4 | regression_dev | paraphrased | 0.0% | 1.000 | 100.0% | yes | 5032 | PARTIAL |
| p5 | regression_holdout | paraphrased | 100.0% | 1.000 | 100.0% | yes | 5915 | PASS |
| m1 | regression_dev | multi-page | 50.0% | 1.000 | 100.0% | yes | 5644 | PARTIAL |
| m2 | regression_holdout | multi-page | 50.0% | 1.000 | 100.0% | yes | 6996 | PARTIAL |
| m3 | regression_holdout | multi-page | 50.0% | 1.000 | 50.0% | yes | 5425 | PARTIAL |
| m4 | regression_dev | multi-page | 50.0% | 1.000 | 100.0% | yes | 6310 | PARTIAL |
| m5 | regression_holdout | multi-page | 100.0% | 1.000 | 100.0% | yes | 6070 | PASS |
| f1 | regression_dev | misleading | 0.0% | 1.000 | 100.0% | yes | 4716 | PARTIAL |
| f2 | regression_holdout | misleading | 100.0% | 1.000 | 100.0% | yes | 5564 | PASS |
| f3 | regression_dev | misleading | 100.0% | 1.000 | 100.0% | yes | 10485 | PASS |
| f4 | regression_holdout | misleading | 0.0% | 1.000 | 100.0% | yes | 5918 | PARTIAL |
| f5 | regression_holdout | misleading | 100.0% | 1.000 | 100.0% | yes | 6717 | PASS |
| u1 | regression_dev | unanswerable | n/a | n/a | n/a | yes | 17 | PASS |
| u2 | regression_holdout | unanswerable | n/a | n/a | n/a | yes | 2729 | PASS |
| u3 | regression_dev | unanswerable | n/a | n/a | n/a | yes | 19 | PASS |
| u4 | regression_holdout | unanswerable | n/a | n/a | n/a | yes | 3494 | PASS |
| u5 | regression_holdout | unanswerable | n/a | n/a | n/a | yes | 2146 | PASS |
| u6 | regression_dev | unanswerable | n/a | n/a | n/a | yes | 7 | PASS |
| ih_s1 | regression_independent_holdout | straightforward | 100.0% | 1.000 | 100.0% | yes | 6948 | PASS |
| ih_s2 | regression_independent_holdout | straightforward | 100.0% | 1.000 | 100.0% | yes | 4690 | PASS |
| ih_p1 | regression_independent_holdout | paraphrased | 100.0% | 1.000 | 100.0% | yes | 4728 | PASS |
| ih_p2 | regression_independent_holdout | paraphrased | 100.0% | 1.000 | 100.0% | yes | 5545 | PASS |
| ih_m1 | regression_independent_holdout | multi-page | 100.0% | 1.000 | 100.0% | yes | 5483 | PASS |
| ih_m2 | regression_independent_holdout | multi-page | 100.0% | 1.000 | 50.0% | yes | 6172 | PARTIAL |
| ih_f1 | regression_independent_holdout | misleading | 100.0% | 1.000 | 100.0% | yes | 4361 | PASS |
| ih_f2 | regression_independent_holdout | misleading | 100.0% | 1.000 | 100.0% | yes | 4084 | PASS |
| ih_u1 | regression_independent_holdout | unanswerable | n/a | n/a | n/a | yes | 61 | PASS |
| ih_u2 | regression_independent_holdout | unanswerable | n/a | n/a | n/a | yes | 47 | PASS |
| ih_u3 | regression_independent_holdout | unanswerable | n/a | n/a | n/a | yes | 46 | PASS |
| ih_u4 | regression_independent_holdout | unanswerable | n/a | n/a | n/a | yes | 6517 | PASS |

## Failures to inspect

- **p2**: answerability mismatch; inspect gate score and evidence selection. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **p4**: missing keypoints: venv creates and manages virtual environments. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m1**: missing keypoints: tuples are immutable. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m2**: missing keypoints: a class variable list is shared across instances. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m3**: missing keypoints: with closes a file even if an exception is raised. Expected-page retrieval miss or incomplete multi-page coverage. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m4**: missing keypoints: range excludes its endpoint. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **f1**: missing keypoints: range excludes its endpoint. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **f4**: missing keypoints: in-place mutable list methods return None. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **ih_m2**: missing keypoints: . Expected-page retrieval miss or incomplete multi-page coverage. Next step: inspect development evidence and improve selection/composition against development questions only.

## Reproduce and improve

Run `python -m evaluation.run_eval --questions evaluation/refusal_regression_questions.json --out results`, using this report's provider and data directory settings. Hardware, network/provider latency, embedding-cache state and source revisions affect results. Initialization and query wall times are separate. Page/source hashes and dependency locks identify drift. Tune on development data only, then freeze code before a fresh independent holdout. Human claim-entailment review and a larger independently authored benchmark remain necessary. Do not interpret this small set as production readiness.

| Round | Dev regex coverage | Holdout regex coverage | Change |
|---|---:|---:|---|
| Baseline only | see split table | see split table | No implementation improvement measured yet |

No comparable improvement history was attached. Keep question/gold/code/settings/corpus versions explicit before comparing runs; tune on development data and use a fresh independent holdout for the final choice.

## How to interpret these numbers

1. The corpus is a bounded snapshot, not the entire Python documentation.
2. Scores depend on this snapshot's URLs and extracted text.
3. 38 authored questions are a small sample; only the independent split was new final testing.
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
