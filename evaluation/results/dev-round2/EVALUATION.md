# Evaluation

Run `20260929T132133Z`, 2026-09-29T13:21:33.077699+00:00. Corpus: 40 pages / 1597 chunks from [Python documentation](https://docs.python.org/3/tutorial/index.html). Corpus SHA-256: `b2605c51c659bfd6e32e6e71b8544180412ed7870557ffed45f624424a2c2b2d`. Provider: **local**; mode: **extractive**; top-k: **5**. Cache disabled. Initial model/index load: **1073 ms**, separate from query latency.

## What was measured

The 26-question file is included with fixed dev/holdout labels and source-checked gold points. Development questions support implementation and threshold selection. Holdout scores are reported separately; this small hand-written set is not a generalization guarantee. Corpus validation checks that required pages and each gold regex component occur in the actual stored page. No external LLM judges were used. The answer cache is disabled; the content-addressed embedding cache remains enabled and can avoid repeated encoding. A separate local warmup before scoring is included in initialization timing.

Keypoint coverage is a deterministic case-insensitive regex proxy over the returned answer. It can miss valid paraphrases and can reward a matching quote without a useful explanation. **It is not semantic faithfulness, answer correctness, hallucination rate, or a human rating.** Exact citation support checks nonempty evidence as a normalized substring of its stored chunk, matching URL and retrieved provenance. It proves quotation provenance, not that evidence logically entails a generated claim. No uncited claims are semantically audited. The optional OpenAI synthesis/semantic verification path was not exercised.

Retrieval Hit@k asks whether any expected URL occurs in the first k distinct retrieved URLs, MRR uses the first such URL, and page coverage counts all expected URLs. Unanswerable questions have no expected URLs and are excluded from retrieval/keypoint averages. The corpus snapshot is the authority: outside-corpus facts must refuse even when a pretrained model might know them. Misleading questions are answerable and need the corrective gold evidence.

## Overall observations

- Mean keypoint coverage: **65.0%**; all-keypoint questions: 6/10 (60.0%; 95% CI 31.3%–83.2%).
- Hit@5: 10/10 (100.0%; 95% CI 72.2%–100.0%); MRR: **0.733**; mean page coverage: **95.0%**.
- Exact supported citations: 34/34 (100.0%; 95% CI 89.8%–100.0%). This denominator is citations; multiple citations per answer are correlated, so its interval is descriptive.
- Answerability decisions: 13/13 (100.0%; 95% CI 77.2%–100.0%); refusal on unanswerable: 3/3 (100.0%; 95% CI 43.9%–100.0%); responses on answerable: 10/10 (100.0%; 95% CI 72.2%–100.0%).
- False-answer rate on unanswerable: 0/3 (0.0%; 95% CI 0.0%–56.1%); false-refusal rate on answerable: 0/10 (0.0%; 95% CI 0.0%–27.8%); answerable responses with every citation supported: 10/10 (100.0%; 95% CI 72.2%–100.0%).
- Query wall latency: mean **5692.4 ms**, empirical nearest-rank p50 **722.4 ms**, p95 **65122.4 ms**. Errors: **0**. Small-sample Wilson intervals are 95%; they do not account for question selection bias.

| Category | N | Keypoint coverage | Hit@k | MRR | Page coverage | Answerability |
|---|---:|---:|---:|---:|---:|---:|
| misleading | 2 | 100.0% | 100.0% | 0.750 | 100.0% | 100.0% |
| multi-page | 2 | 25.0% | 100.0% | 0.417 | 75.0% | 100.0% |
| paraphrased | 3 | 33.3% | 100.0% | 1.000 | 100.0% | 100.0% |
| straightforward | 3 | 100.0% | 100.0% | 0.667 | 100.0% | 100.0% |
| unanswerable | 3 | n/a | n/a | n/a | n/a | 100.0% |

| Split | N | Keypoint coverage | Hit@k | MRR | Unanswerable refusal (95% CI) |
|---|---:|---:|---:|---:|---|
| dev | 13 | 65.0% | 100.0% | 0.733 | 3/3 (100.0%; 95% CI 43.9%–100.0%) |

## Retrieval ablations

The same frozen questions and index are used; only retrieval mode/diversification changes. These are retrieval-only runs, so they do not measure generation quality. Initial model loading is excluded.

| Retrieval configuration | Hit@k | MRR | Page coverage | Mean wall ms |
|---|---:|---:|---:|---:|
| hybrid, diversity on, k=5 | 100.0% | 0.733 | 95.0% | 20.5 |
| hybrid, diversity off, k=5 | 100.0% | 0.733 | 95.0% | 15.3 |
| dense, diversity off, k=5 | 90.0% | 0.658 | 80.0% | 21.5 |
| bm25, diversity off, k=5 | 90.0% | 0.650 | 80.0% | 35.7 |
| hybrid, diversity on, k=3 | 100.0% | 0.733 | 95.0% | 18.5 |
| hybrid, diversity on, k=8 | 100.0% | 0.733 | 95.0% | 15.7 |

The LLM-self-check on/off and 400/600/900-token reindexing ablations are **NOT YET MEASURED**. No paid provider credentials were available. The local MiniLM encoder segments oversized text into 220-wordpiece windows and averages normalized vectors, avoiding silent truncation, but larger chunks require a measured quality/reindexing comparison. The reported diversification is a greedy source-count penalty, not full vector-pair MMR.

## Dev-only gate diagnostic

This table simulates the relevance gate on the stored best dense scores from development questions that actually reached retrieval. Preblocked injections and errors without retrieval are excluded, rather than treated as zero-score gate successes. It does not rerun extraction/verification, and later refusals are not attributed to the gate. Holdout questions were excluded. The configured threshold was not selected from holdout results.

| Candidate minimum score | Answerable rejected at gate | Unanswerable rejected at gate |
|---|---:|---:|
| 0.25 | 0.0% | 100.0% |
| 0.30 | 0.0% | 100.0% |
| 0.35 | 0.0% | 100.0% |
| 0.40 | 0.0% | 100.0% |
| 0.45 | 0.0% | 100.0% |
| 0.50 | 20.0% | 100.0% |
| 0.55 | 30.0% | 100.0% |
| 0.60 | 60.0% | 100.0% |

## Stage latency

One measurement per attempted question; warm model/index after startup. Stage times may overlap or be aggregate times, so do not sum every row.

| Stage | p50 ms | p95 ms |
|---|---:|---:|
| bm25 | 14.6 | 31.3 |
| dense | 4.3 | 12.0 |
| embedding | 19.2 | 40.9 |
| fusion | 0.3 | 0.6 |
| generation | 693.2 | 65096.7 |
| retrieval | 43.3 | 62.3 |
| total | 721.5 | 65116.2 |
| verification | 0.4 | 0.9 |

## Per-question diagnostics

Full question text, raw answer, citations, keypoints, token estimates and per-stage timing are in `results.json`. Gold evidence and scoring expressions are in `evaluation/questions.json`. Corpus validation is recorded in `gold_validation`.

| ID | Split | Category | Keypoint coverage | Hit@k | Page coverage | Answerability correct | Wall ms | Status |
|---|---|---|---:|---:|---:|---|---:|---|
| s1 | dev | straightforward | 100.0% | 1.000 | 100.0% | yes | 65122 | PASS |
| s2 | dev | straightforward | 100.0% | 1.000 | 100.0% | yes | 722 | PASS |
| s4 | dev | straightforward | 100.0% | 1.000 | 100.0% | yes | 734 | PASS |
| p1 | dev | paraphrased | 0.0% | 1.000 | 100.0% | yes | 794 | PARTIAL |
| p2 | dev | paraphrased | 100.0% | 1.000 | 100.0% | yes | 677 | PASS |
| p4 | dev | paraphrased | 0.0% | 1.000 | 100.0% | yes | 415 | PARTIAL |
| m1 | dev | multi-page | 50.0% | 1.000 | 50.0% | yes | 1996 | PARTIAL |
| m4 | dev | multi-page | 0.0% | 1.000 | 100.0% | yes | 1638 | PARTIAL |
| f1 | dev | misleading | 100.0% | 1.000 | 100.0% | yes | 652 | PASS |
| f3 | dev | misleading | 100.0% | 1.000 | 100.0% | yes | 1106 | PASS |
| u1 | dev | unanswerable | n/a | n/a | n/a | yes | 67 | PASS |
| u3 | dev | unanswerable | n/a | n/a | n/a | yes | 71 | PASS |
| u6 | dev | unanswerable | n/a | n/a | n/a | yes | 6 | PASS |

## Failures to inspect

- **p1**: missing keypoints: append adds an item to the end of the list. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **p4**: missing keypoints: venv creates and manages virtual environments. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m1**: missing keypoints: strings are immutable and cannot be changed. Expected-page retrieval miss or incomplete multi-page coverage. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m4**: missing keypoints: list comprehensions concisely create lists, range excludes its endpoint. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.

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
