# Evaluation

Run `20260929T133418Z`, 2026-09-29T13:34:18.305889+00:00. Corpus: 40 pages / 1597 chunks from [Python documentation](https://docs.python.org/3/tutorial/index.html). Corpus SHA-256: `b2605c51c659bfd6e32e6e71b8544180412ed7870557ffed45f624424a2c2b2d`. Provider: **local**; mode: **extractive**; top-k: **5**. Cache disabled. Initial model/index load: **1380 ms**, separate from query latency.

## What was measured

The 26-question file is included with fixed dev/holdout labels and source-checked gold points. Development questions support implementation and threshold selection. Holdout scores are reported separately; this small hand-written set is not a generalization guarantee. Corpus validation checks that required pages and each gold regex component occur in the actual stored page. No external LLM judges were used. The answer cache is disabled; the content-addressed embedding cache remains enabled and can avoid repeated encoding. A separate local warmup before scoring is included in initialization timing.

Keypoint coverage is a deterministic case-insensitive regex proxy over the returned answer. It can miss valid paraphrases and can reward a matching quote without a useful explanation. **It is not semantic faithfulness, answer correctness, hallucination rate, or a human rating.** Exact citation support checks nonempty evidence as a normalized substring of its stored chunk, matching source URL and that URL appearing in the retrieval trace. The response trace stores URLs rather than every retrieved chunk ID; this metric checks URL-level provenance, while the graph itself verifies IDs against its actual retrieval hits. It proves quotation provenance, not that evidence logically entails a generated claim. No uncited claims are semantically audited. The optional OpenAI synthesis/semantic verification path was not exercised.

Retrieval Hit@k asks whether any expected URL occurs in the first k distinct retrieved URLs, MRR uses the first such URL, and page coverage counts all expected URLs. Unanswerable questions have no expected URLs and are excluded from retrieval/keypoint averages. The corpus snapshot is the authority: outside-corpus facts must refuse even when a pretrained model might know them. Misleading questions are answerable and need the corrective gold evidence.

## Overall observations

- Mean keypoint coverage: **15.0%**; all-keypoint questions: 1/10 (10.0%; 95% CI 1.8%–40.4%).
- Hit@5: 10/10 (100.0%; 95% CI 72.2%–100.0%); MRR: **0.870**; mean page coverage: **95.0%**.
- Exact supported citations: 25/25 (100.0%; 95% CI 86.7%–100.0%). This denominator is citations; multiple citations per answer are correlated, so its interval is descriptive.
- Answerability decisions: 9/13 (69.2%; 95% CI 42.4%–87.3%); refusal on unanswerable: 2/3 (66.7%; 95% CI 20.8%–93.9%); responses on answerable: 7/10 (70.0%; 95% CI 39.7%–89.2%).
- False-answer rate on unanswerable: 1/3 (33.3%; 95% CI 6.1%–79.2%); false-refusal rate on answerable: 3/10 (30.0%; 95% CI 10.8%–60.3%); answerable responses with every citation supported: 8/8 (100.0%; 95% CI 67.6%–100.0%).
- Query wall latency: mean **11252.2 ms**, empirical nearest-rank p50 **1547.2 ms**, p95 **125129.0 ms**. Errors: **0**. Small-sample Wilson intervals are 95%; they do not account for question selection bias.

| Category | N | Keypoint coverage | Hit@k | MRR | Page coverage | Answerability |
|---|---:|---:|---:|---:|---:|---:|
| misleading | 3 | 0.0% | 100.0% | 0.567 | 100.0% | 33.3% |
| multi-page | 3 | 16.7% | 100.0% | 1.000 | 83.3% | 100.0% |
| paraphrased | 2 | 0.0% | 100.0% | 1.000 | 100.0% | 50.0% |
| straightforward | 2 | 50.0% | 100.0% | 1.000 | 100.0% | 100.0% |
| unanswerable | 3 | n/a | n/a | n/a | n/a | 66.7% |

| Split | N | Keypoint coverage | Hit@k | MRR | Unanswerable refusal (95% CI) |
|---|---:|---:|---:|---:|---|
| holdout | 13 | 15.0% | 100.0% | 0.870 | 2/3 (66.7%; 95% CI 20.8%–93.9%) |

## Retrieval ablations

The same frozen questions and index are used; only retrieval mode/diversification changes. These are retrieval-only runs, so they do not measure generation quality. Initial model loading is excluded.

| Retrieval configuration | Hit@k | MRR | Page coverage | Mean wall ms |
|---|---:|---:|---:|---:|
| hybrid, diversity on, k=5 | 100.0% | 0.900 | 95.0% | 29.7 |
| hybrid, diversity off, k=5 | 100.0% | 0.900 | 90.0% | 24.0 |
| dense, diversity off, k=5 | 80.0% | 0.750 | 80.0% | 36.9 |
| bm25, diversity off, k=5 | 100.0% | 0.900 | 90.0% | 47.7 |
| hybrid, diversity on, k=3 | 100.0% | 0.900 | 90.0% | 31.8 |
| hybrid, diversity on, k=8 | 100.0% | 0.900 | 100.0% | 26.1 |

The LLM-self-check on/off and 400/600/900-token reindexing ablations are **NOT YET MEASURED**. No paid provider credentials were available. The local MiniLM encoder segments oversized text into 220-wordpiece windows and averages normalized vectors, avoiding silent truncation, but larger chunks require a measured quality/reindexing comparison. The reported diversification is a greedy source-count penalty, not full vector-pair MMR.

## Dev-only gate diagnostic

This table simulates the relevance gate on the stored best dense scores from development questions that actually reached retrieval. Preblocked injections and errors without retrieval are excluded, rather than treated as zero-score gate successes. It does not rerun extraction/verification, and later refusals are not attributed to the gate. Holdout questions were excluded. The configured threshold was not selected from holdout results.

| Candidate minimum score | Answerable rejected at gate | Unanswerable rejected at gate |
|---|---:|---:|
| 0.25 | n/a | n/a |
| 0.30 | n/a | n/a |
| 0.35 | n/a | n/a |
| 0.40 | n/a | n/a |
| 0.45 | n/a | n/a |
| 0.50 | n/a | n/a |
| 0.55 | n/a | n/a |
| 0.60 | n/a | n/a |

## Stage latency

One measurement per attempted question; warm model/index after startup. Stage times may overlap or be aggregate times, so do not sum every row.

| Stage | p50 ms | p95 ms |
|---|---:|---:|
| bm25 | 17.0 | 57.5 |
| dense | 5.1 | 55.4 |
| embedding | 45.9 | 200.5 |
| fusion | 0.3 | 1.7 |
| generation | 1435.4 | 124305.6 |
| retrieval | 74.6 | 248.1 |
| total | 1545.7 | 125124.5 |
| verification | 0.3 | 0.7 |

## Per-question diagnostics

Full question text, raw answer, citations, keypoints, token estimates and per-stage timing are in `results.json`. Gold evidence and scoring expressions are in `evaluation/questions.json`. Corpus validation is recorded in `gold_validation`.

| ID | Split | Category | Keypoint coverage | Hit@k | Page coverage | Answerability correct | Wall ms | Status |
|---|---|---|---:|---:|---:|---|---:|---|
| s3 | holdout | straightforward | 0.0% | 1.000 | 100.0% | yes | 125129 | PARTIAL |
| s5 | holdout | straightforward | 100.0% | 1.000 | 100.0% | yes | 1547 | PASS |
| p3 | holdout | paraphrased | 0.0% | 1.000 | 100.0% | yes | 948 | PARTIAL |
| p5 | holdout | paraphrased | 0.0% | 1.000 | 100.0% | no | 1325 | FAIL |
| m2 | holdout | multi-page | 0.0% | 1.000 | 100.0% | yes | 1857 | PARTIAL |
| m3 | holdout | multi-page | 50.0% | 1.000 | 100.0% | yes | 1168 | PARTIAL |
| m5 | holdout | multi-page | 0.0% | 1.000 | 50.0% | yes | 723 | PARTIAL |
| f2 | holdout | misleading | 0.0% | 1.000 | 100.0% | no | 2554 | FAIL |
| f4 | holdout | misleading | 0.0% | 1.000 | 100.0% | yes | 1505 | PARTIAL |
| f5 | holdout | misleading | 0.0% | 1.000 | 100.0% | no | 4565 | FAIL |
| u2 | holdout | unanswerable | n/a | n/a | n/a | yes | 2135 | PASS |
| u4 | holdout | unanswerable | n/a | n/a | n/a | no | 2051 | FAIL |
| u5 | holdout | unanswerable | n/a | n/a | n/a | yes | 771 | PASS |

## Failures to inspect

- **s3**: missing keypoints: finally runs whether or not an exception occurs. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **p3**: missing keypoints: finally runs whether or not an exception occurs. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **p5**: answerability mismatch; inspect gate score and evidence selection. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m2**: missing keypoints: a mutable default is evaluated only once, a class variable list is shared across instances. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m3**: missing keypoints: finally runs whether or not an exception occurs. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m5**: missing keypoints: module search checks directories in sys.path, pip installs packages, by default from PyPI. Expected-page retrieval miss or incomplete multi-page coverage. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **f2**: answerability mismatch; inspect gate score and evidence selection. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **f4**: missing keypoints: in-place mutable list methods return None. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **f5**: answerability mismatch; inspect gate score and evidence selection. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **u4**: answerability mismatch; inspect gate score and evidence selection. Next step: inspect development evidence and improve selection/composition against development questions only.

## Reproduce and improve

Run `python -m evaluation.run_eval --questions evaluation/questions.json --out results`. Local hardware, warm page cache, model download/cache and live source revisions affect latency and corpus content. First model/index load is reported separately. Page hashes and dependency locks help identify drift. Tune on dev only, then report a fresh unchanged holdout run. A stronger next evaluation would expand independent paraphrases/negative cases, add human claim entailment review, and evaluate the optional synthesis provider under an explicit budget. Do not interpret these 26 questions as production readiness.

| Round | Dev regex coverage | Holdout regex coverage | Change |
|---|---:|---:|---|
| Baseline only | see split table | see split table | No implementation improvement measured yet |

Original baseline outputs are retained in `baseline_original.json`. Two development-only synonym corrections were applied to the scorer (item/element and explicit denial of tuple item assignment), then the original raw answers were rescored as `baseline.json`. Before/after comparison uses those same revised expressions. Gold facts/URLs and holdout patterns did not change. See `scoring_notes.md`; the scoring revision is not an agent improvement. When final dev/holdout results are combined, their saved code/settings/corpus hashes must match; no extra holdout query run is made for reporting.

## How to interpret these numbers

1. The corpus is a bounded snapshot, not the entire Python documentation.
2. Scores depend on this snapshot's URLs and extracted text.
3. Twenty-six questions are a small sample.
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
15. LLM faithfulness judging is unmeasured here.
16. Errors count as answerability failures, never correct refusals.
17. Wilson intervals reflect small denominators, not selection bias.
18. Citation intervals ignore within-answer correlation.
19. Warm latency excludes download and initialization.
20. Improvements require development-only tuning and a frozen independent holdout.
