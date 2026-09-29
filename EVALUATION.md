# Evaluation status of the deployed revision

The original independent evaluation is preserved below. The follow-up deliberately repairs previously observed failures, so the 38-question rerun is a **regression run**: gold facts, source URLs and scoring expressions are unchanged, and split labels explicitly identify reused data.

| Diagnostic | Original independent 12 | Same 12 after repairs (regression) |
|---|---:|---:|
| All-keypoint answerable questions | 6/8 | 8/8 |
| False refusals | 2/8 | 0/8 |
| Unknown refusals | 4/4 | 4/4 |
| Exact quote provenance | 11/11 | 15/15 |

The entire regression run has 37/38 correct answerability decisions, 78.6% regex keypoint coverage, 61/61 exact source quotations, 10/10 unknown refusals, one false refusal among 28 answerable questions, and no request errors. Wall p50/p95: 5.425/8.817 seconds. Regex coverage and quotation provenance do not measure independent semantic correctness. Model outputs can vary; three successful uncached repetitions per repaired question do not establish a universal guarantee.

[Full follow-up report](evaluation/results/followup_regression/EVALUATION.md) · [Raw results](evaluation/results/followup_regression/results.json) · [Unmodified original benchmark](evaluation/submission_questions.json) · [Explicitly relabeled regression benchmark](evaluation/refusal_regression_questions.json)

---

# Evaluation

Run `20260929T142544Z`, 2026-09-29T14:25:44.466874+00:00. Corpus: 40 pages / 1597 chunks from [Python documentation](https://docs.python.org/3/tutorial/index.html). Corpus SHA-256: `b2605c51c659bfd6e32e6e71b8544180412ed7870557ffed45f624424a2c2b2d`. Provider: **openai**; mode: **synthesis**; top-k: **8**. Answer cache disabled. Agent/index initialization: **1393 ms**, separate from query wall time. Recorded local encoder warmup: **0 ms**; paid warmup requests: **0**.

**Semantic production quality is not established.** Inspect keypoint misses, false answers/refusals, confidence intervals and query latency; exact source quotes can still support an irrelevant or incomplete answer.

Provider and timing notes: Paid synthesis was selected; inspect returned token metadata, errors and verification settings for actual execution. Agent/index initialization makes no provider warmup call. Query wall times include provider request/framing, synthesis, semantic verification and retries. Embedding-cache hits can skip paid encoding. Regex keypoint coverage and exact quotation provenance do not establish semantic faithfulness or human correctness. Independent semantic evaluation and human rating remain unmeasured; production quality is not established.

## What was measured

The **38-question** file uses explicit split labels and source-checked gold points. Benchmark: **Formal38: original benchmark plus independent holdout**. Development data supports implementation/threshold selection; holdout outputs must not be used for tuning. This small hand-written set is not a generalization guarantee. Corpus validation checks required pages and each gold regex component in the actual stored page. No independent evaluation LLM judge was used. Production provider self-checks are part of the answering path, not an independent faithfulness score. The answer cache is disabled; the content-addressed embedding cache remains enabled and can avoid repeated query encoding. New local evaluations explicitly load the encoder during initialization; paid mode makes no initialization embedding or synthesis call. The archived local timing setup is preserved separately.

Benchmark provenance: **684c698acbef80256a301128640029e48ce992d87365d26a0b74525dba0e2e15**. Original dev and holdout were previously inspected during local development. Only independent_holdout is new unseen final testing. No tuning after this run. Regex keypoints and quote provenance are diagnostic proxies.

Source provenance notes: An early-run source snapshot differed from end-of-run saved files only in graph.py. During evaluation, a Bandit-only repair replaced two identical mixed_api_and_estimated string literals with the equivalent MIXED_PROVENANCE constant. The parent confirmed unchanged behavior/settings; no answer rerun or score/gold change was made. Both hash maps and original observed result bytes are retained. After the run, isort removed one extra import-area blank line in graph.py; that nonbehavioral formatting hash is recorded separately as source_sha256_postrun. Observed end-of-run hashes and raw answers remain unchanged.

Keypoint coverage is a deterministic case-insensitive regex proxy over the returned answer. It can miss valid paraphrases and can reward a matching quote without a useful explanation. **It is not semantic faithfulness, answer correctness, hallucination rate, or a human rating.** Exact citation support checks nonempty evidence as a whitespace-normalized substring of its stored chunk, preserving case and Unicode characters, matching the source URL and that URL appearing in the retrieval trace. The response trace stores URLs rather than every retrieved chunk ID; this metric checks URL-level provenance, while the graph verifies IDs against its actual retrieval hits. It proves quotation provenance, not logical claim entailment. No independent semantic audit of each claim was performed. Production self-check setting: **True**.

Retrieval Hit@k asks whether any expected URL occurs in the first k distinct retrieved URLs, MRR uses the first such URL, and page coverage counts all expected URLs. Unanswerable questions have no expected URLs and are excluded from retrieval/keypoint averages. The corpus snapshot is the authority: outside-corpus facts must refuse even when a pretrained model might know them. Misleading questions are answerable and need the corrective gold evidence.

## Overall observations

- Mean keypoint coverage: **66.1%**; all-keypoint questions: 17/28 (60.7%; 95% CI 42.4%–76.4%).
- Hit@8: 28/28 (100.0%; 95% CI 87.9%–100.0%); MRR: **0.836**; mean page coverage: **98.2%**.
- Exact supported citations: 59/59 (100.0%; 95% CI 93.9%–100.0%). This denominator is citations; multiple citations per answer are correlated, so its interval is descriptive.
- Answerability decisions: 34/38 (89.5%; 95% CI 75.9%–95.8%); refusal on unanswerable: 10/10 (100.0%; 95% CI 72.2%–100.0%); responses on answerable: 24/28 (85.7%; 95% CI 68.5%–94.3%).
- False-answer rate on unanswerable: 0/10 (0.0%; 95% CI 0.0%–27.8%); false-refusal rate on answerable: 4/28 (14.3%; 95% CI 5.7%–31.5%); answerable responses with every citation supported: 24/24 (100.0%; 95% CI 86.2%–100.0%).
- Query wall latency: mean **4694.9 ms**, empirical nearest-rank p50 **4551.7 ms**, p95 **10116.5 ms**. Errors: **0**. Small-sample Wilson intervals are 95%; they do not account for question selection bias.

| Category | N | Keypoint coverage | Hit@k | MRR | Page coverage | Answerability |
|---|---:|---:|---:|---:|---:|---:|
| misleading | 7 | 28.6% | 100.0% | 0.786 | 100.0% | 57.1% |
| multi-page | 7 | 50.0% | 100.0% | 0.893 | 92.9% | 85.7% |
| paraphrased | 7 | 85.7% | 100.0% | 0.905 | 100.0% | 100.0% |
| straightforward | 7 | 100.0% | 100.0% | 0.762 | 100.0% | 100.0% |
| unanswerable | 10 | n/a | n/a | n/a | n/a | 100.0% |

| Split | N | Keypoint coverage | Hit@k | MRR | Unanswerable refusal (95% CI) |
|---|---:|---:|---:|---:|---|
| dev | 13 | 65.0% | 100.0% | 0.758 | 3/3 (100.0%; 95% CI 43.9%–100.0%) |
| holdout | 13 | 60.0% | 100.0% | 0.925 | 3/3 (100.0%; 95% CI 43.9%–100.0%) |
| independent_holdout | 12 | 75.0% | 100.0% | 0.823 | 4/4 (100.0%; 95% CI 51.0%–100.0%) |

## Retrieval ablations

The same frozen questions and index are used; only retrieval mode/diversification changes. These are retrieval-only runs, so they do not measure generation quality. Initial model loading is excluded.

| Retrieval configuration | Hit@k | MRR | Page coverage | Mean wall ms |
|---|---:|---:|---:|---:|
| hybrid, diversity on, k=5 | 92.9% | 0.818 | 91.1% | 63.5 |
| hybrid, diversity off, k=5 | 92.9% | 0.818 | 89.3% | 44.1 |
| dense, diversity off, k=5 | 89.3% | 0.815 | 87.5% | 33.5 |
| bm25, diversity off, k=5 | 96.4% | 0.777 | 85.7% | 32.4 |
| hybrid, diversity on, k=3 | 89.3% | 0.810 | 85.7% | 21.5 |
| hybrid, diversity on, k=8 | 96.4% | 0.827 | 96.4% | 19.6 |

The LLM-self-check on/off and 400/600/900-token reindexing ablations are **NOT YET MEASURED** in this report. Selecting a self-check setting is not an on/off comparison. Larger chunks require their own quality/reindexing measurement; the local MiniLM encoder segments oversized text into 220-wordpiece windows. Reported diversification is a greedy source-count penalty, not full vector-pair MMR. Retrieval ablations can incur paid embedding misses; auxiliary usage is recorded separately from answer-query usage in the cost report.

## Dev-only gate diagnostic

This table simulates the relevance gate on the stored best dense scores from development questions that actually reached retrieval. Preblocked injections and errors without retrieval are excluded, rather than treated as zero-score gate successes. It does not rerun extraction/verification, and later refusals are not attributed to the gate. Holdout questions were excluded. The configured threshold was not selected from holdout results.

| Candidate minimum score | Answerable rejected at gate | Unanswerable rejected at gate |
|---|---:|---:|
| 0.25 | 0.0% | 100.0% |
| 0.30 | 10.0% | 100.0% |
| 0.35 | 10.0% | 100.0% |
| 0.40 | 20.0% | 100.0% |
| 0.45 | 30.0% | 100.0% |
| 0.50 | 40.0% | 100.0% |
| 0.55 | 60.0% | 100.0% |
| 0.60 | 80.0% | 100.0% |

## Stage latency

One measurement per attempted question; index loaded at startup, with embedding cache reuse and the lazy encoder caveat above. Stage times may overlap or be aggregate times, so do not sum every row.

| Stage | p50 ms | p95 ms |
|---|---:|---:|
| bm25 | 22.0 | 45.9 |
| dense | 6.5 | 26.2 |
| embedding | 332.9 | 1586.4 |
| fusion | 0.4 | 1.1 |
| generation | 3327.8 | 6818.6 |
| retrieval | 359.9 | 1647.9 |
| total | 4550.9 | 10114.8 |
| verification | 1344.1 | 3123.8 |

## Per-question diagnostics

Full question text, raw answer, citations, keypoints, token estimates and per-stage timing are in `results.json`. Gold evidence and scoring expressions are in `evaluation/questions.json`. Corpus validation is recorded in `gold_validation`.

| ID | Split | Category | Keypoint coverage | Hit@k | Page coverage | Answerability correct | Wall ms | Status |
|---|---|---|---:|---:|---:|---|---:|---|
| s1 | dev | straightforward | 100.0% | 1.000 | 100.0% | yes | 10117 | PASS |
| s2 | dev | straightforward | 100.0% | 1.000 | 100.0% | yes | 3520 | PASS |
| s3 | holdout | straightforward | 100.0% | 1.000 | 100.0% | yes | 7384 | PASS |
| s4 | dev | straightforward | 100.0% | 1.000 | 100.0% | yes | 3001 | PASS |
| s5 | holdout | straightforward | 100.0% | 1.000 | 100.0% | yes | 6372 | PASS |
| p1 | dev | paraphrased | 100.0% | 1.000 | 100.0% | yes | 4764 | PASS |
| p2 | dev | paraphrased | 100.0% | 1.000 | 100.0% | yes | 3886 | PASS |
| p3 | holdout | paraphrased | 100.0% | 1.000 | 100.0% | yes | 5009 | PASS |
| p4 | dev | paraphrased | 0.0% | 1.000 | 100.0% | yes | 4317 | PARTIAL |
| p5 | holdout | paraphrased | 100.0% | 1.000 | 100.0% | yes | 7179 | PASS |
| m1 | dev | multi-page | 100.0% | 1.000 | 100.0% | yes | 4435 | PASS |
| m2 | holdout | multi-page | 50.0% | 1.000 | 100.0% | yes | 4552 | PARTIAL |
| m3 | holdout | multi-page | 0.0% | 1.000 | 100.0% | yes | 5368 | PARTIAL |
| m4 | dev | multi-page | 50.0% | 1.000 | 100.0% | yes | 7298 | PARTIAL |
| m5 | holdout | multi-page | 50.0% | 1.000 | 100.0% | yes | 6525 | PARTIAL |
| f1 | dev | misleading | 0.0% | 1.000 | 100.0% | yes | 3665 | PARTIAL |
| f2 | holdout | misleading | 100.0% | 1.000 | 100.0% | yes | 4378 | PASS |
| f3 | dev | misleading | 0.0% | 1.000 | 100.0% | no | 9567 | FAIL |
| f4 | holdout | misleading | 0.0% | 1.000 | 100.0% | yes | 3984 | PARTIAL |
| f5 | holdout | misleading | 0.0% | 1.000 | 100.0% | no | 9863 | FAIL |
| u1 | dev | unanswerable | n/a | n/a | n/a | yes | 23 | PASS |
| u2 | holdout | unanswerable | n/a | n/a | n/a | yes | 3696 | PASS |
| u3 | dev | unanswerable | n/a | n/a | n/a | yes | 32 | PASS |
| u4 | holdout | unanswerable | n/a | n/a | n/a | yes | 4882 | PASS |
| u5 | holdout | unanswerable | n/a | n/a | n/a | yes | 1989 | PASS |
| u6 | dev | unanswerable | n/a | n/a | n/a | yes | 4 | PASS |
| ih_s1 | independent_holdout | straightforward | 100.0% | 1.000 | 100.0% | yes | 6915 | PASS |
| ih_s2 | independent_holdout | straightforward | 100.0% | 1.000 | 100.0% | yes | 4575 | PASS |
| ih_p1 | independent_holdout | paraphrased | 100.0% | 1.000 | 100.0% | yes | 5284 | PASS |
| ih_p2 | independent_holdout | paraphrased | 100.0% | 1.000 | 100.0% | yes | 4916 | PASS |
| ih_m1 | independent_holdout | multi-page | 100.0% | 1.000 | 100.0% | yes | 6343 | PASS |
| ih_m2 | independent_holdout | multi-page | 0.0% | 1.000 | 50.0% | no | 10960 | FAIL |
| ih_f1 | independent_holdout | misleading | 100.0% | 1.000 | 100.0% | yes | 4180 | PASS |
| ih_f2 | independent_holdout | misleading | 0.0% | 1.000 | 100.0% | no | 3986 | FAIL |
| ih_u1 | independent_holdout | unanswerable | n/a | n/a | n/a | yes | 279 | PASS |
| ih_u2 | independent_holdout | unanswerable | n/a | n/a | n/a | yes | 268 | PASS |
| ih_u3 | independent_holdout | unanswerable | n/a | n/a | n/a | yes | 282 | PASS |
| ih_u4 | independent_holdout | unanswerable | n/a | n/a | n/a | yes | 4607 | PASS |

## Failures to inspect

- **p4**: missing keypoints: venv creates and manages virtual environments. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m2**: missing keypoints: a mutable default is evaluated only once. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m3**: missing keypoints: finally runs whether or not an exception occurs, with closes a file even if an exception is raised. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m4**: missing keypoints: range excludes its endpoint. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m5**: missing keypoints: module search checks directories in sys.path. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **f1**: missing keypoints: range excludes its endpoint. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **f3**: answerability mismatch; inspect gate score and evidence selection. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **f4**: missing keypoints: in-place mutable list methods return None. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **f5**: answerability mismatch; inspect gate score and evidence selection. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **ih_m2**: answerability mismatch; inspect gate score and evidence selection. Expected-page retrieval miss or incomplete multi-page coverage. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **ih_f2**: answerability mismatch; inspect gate score and evidence selection. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.

## Reproduce and improve

Run `python -m evaluation.run_eval --questions evaluation/submission_questions.json --out results`, using this report's provider and data directory settings. Hardware, network/provider latency, embedding-cache state and source revisions affect results. Initialization and query wall times are separate. Page/source hashes and dependency locks identify drift. Tune on development data only, then freeze code before a fresh independent holdout. Human claim-entailment review and a larger independently authored benchmark remain necessary. Do not interpret this small set as production readiness.

| Round | Dev regex coverage | Holdout regex coverage | Change |
|---|---:|---:|---|
| Baseline only | see split table | see split table | No implementation improvement measured yet |

This run does not establish a before/after improvement on the archived local benchmark. The independent holdout has different questions and cannot support a like-for-like provider improvement percentage. Its gold expressions must remain frozen; investigate failures on development data and use a fresh independent test for later revisions.

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
