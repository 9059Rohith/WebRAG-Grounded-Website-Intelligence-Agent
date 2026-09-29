# Evaluation

Run `20260929T133418Z-combined`, 2026-09-29T13:34:18.305889+00:00. Corpus: 40 pages / 1597 chunks from [Python documentation](https://docs.python.org/3/tutorial/index.html). Corpus SHA-256: `b2605c51c659bfd6e32e6e71b8544180412ed7870557ffed45f624424a2c2b2d`. Provider: **local**; mode: **extractive**; top-k: **5**. Answer cache disabled. Agent initialization: **1380 ms**, separate from query wall time. This can leave the encoder lazy when the warmup embedding is cached.

**Quality and latency targets are unmet.** Regex coverage measures incomplete excerpts, and quote provenance must not be interpreted as semantic answer quality. Inspect the holdout's false-answer/refusal rates and retained latency outlier before using this system.

Timing caveat: Local warmup was served by the embedding cache and did not force encoder loading. Lazy model loading can occur within query generation; measured timings are preserved.

## What was measured

The 26-question file is included with fixed dev/holdout labels and source-checked gold points. Development questions support implementation and threshold selection. Holdout scores are reported separately; this small hand-written set is not a generalization guarantee. Corpus validation checks that required pages and each gold regex component occur in the actual stored page. No external LLM judges were used. The answer cache is disabled; the content-addressed embedding cache remains enabled and can avoid repeated encoding. A local warmup request is included in initialization, but an embedding-cache hit does not force model loading. Final development and holdout queries included lazy encoder loading: their approximately 49-second and 125-second measured outliers are retained. A future explicit model warmup would change timing setup and requires a new clearly labeled run.

Keypoint coverage is a deterministic case-insensitive regex proxy over the returned answer. It can miss valid paraphrases and can reward a matching quote without a useful explanation. **It is not semantic faithfulness, answer correctness, hallucination rate, or a human rating.** Exact citation support checks nonempty evidence as a normalized substring of its stored chunk, matching source URL and that URL appearing in the retrieval trace. The response trace stores URLs rather than every retrieved chunk ID; this metric checks URL-level provenance, while the graph itself verifies IDs against its actual retrieval hits. It proves quotation provenance, not that evidence logically entails a generated claim. No uncited claims are semantically audited. The optional OpenAI synthesis/semantic verification path was not exercised.

Retrieval Hit@k asks whether any expected URL occurs in the first k distinct retrieved URLs, MRR uses the first such URL, and page coverage counts all expected URLs. Unanswerable questions have no expected URLs and are excluded from retrieval/keypoint averages. The corpus snapshot is the authority: outside-corpus facts must refuse even when a pretrained model might know them. Misleading questions are answerable and need the corrective gold evidence.

## Overall observations

- Mean keypoint coverage: **40.0%**; all-keypoint questions: 7/20 (35.0%; 95% CI 18.1%–56.7%).
- Hit@5: 20/20 (100.0%; 95% CI 83.9%–100.0%); MRR: **0.797**; mean page coverage: **95.0%**.
- Exact supported citations: 57/57 (100.0%; 95% CI 93.7%–100.0%). This denominator is citations; multiple citations per answer are correlated, so its interval is descriptive.
- Answerability decisions: 22/26 (84.6%; 95% CI 66.5%–93.8%); refusal on unanswerable: 5/6 (83.3%; 95% CI 43.6%–97.0%); responses on answerable: 17/20 (85.0%; 95% CI 64.0%–94.8%).
- False-answer rate on unanswerable: 1/6 (16.7%; 95% CI 3.0%–56.4%); false-refusal rate on answerable: 3/20 (15.0%; 95% CI 5.2%–36.0%); answerable responses with every citation supported: 18/18 (100.0%; 95% CI 82.4%–100.0%).
- Query wall latency: mean **7599.0 ms**, empirical nearest-rank p50 **723.2 ms**, p95 **49318.0 ms**. Errors: **0**. Small-sample Wilson intervals are 95%; they do not account for question selection bias.

| Category | N | Keypoint coverage | Hit@k | MRR | Page coverage | Answerability |
|---|---:|---:|---:|---:|---:|---:|
| misleading | 5 | 40.0% | 100.0% | 0.640 | 100.0% | 60.0% |
| multi-page | 5 | 20.0% | 100.0% | 0.750 | 80.0% | 100.0% |
| paraphrased | 5 | 20.0% | 100.0% | 1.000 | 100.0% | 80.0% |
| straightforward | 5 | 80.0% | 100.0% | 0.800 | 100.0% | 100.0% |
| unanswerable | 6 | n/a | n/a | n/a | n/a | 83.3% |

| Split | N | Keypoint coverage | Hit@k | MRR | Unanswerable refusal (95% CI) |
|---|---:|---:|---:|---:|---|
| dev | 13 | 65.0% | 100.0% | 0.725 | 3/3 (100.0%; 95% CI 43.9%–100.0%) |
| holdout | 13 | 15.0% | 100.0% | 0.870 | 2/3 (66.7%; 95% CI 20.8%–93.9%) |

## Retrieval ablations

The same frozen questions and index are used; only retrieval mode/diversification changes. These are retrieval-only runs, so they do not measure generation quality. Initial model loading is excluded.

| Retrieval configuration | Hit@k | MRR | Page coverage | Mean wall ms |
|---|---:|---:|---:|---:|
| hybrid, diversity on, k=5 | 100.0% | 0.812 | 95.0% | 27.6 |
| hybrid, diversity off, k=5 | 100.0% | 0.812 | 90.0% | 23.1 |
| dense, diversity off, k=5 | 85.0% | 0.704 | 80.0% | 27.5 |
| bm25, diversity off, k=5 | 95.0% | 0.775 | 85.0% | 31.2 |
| hybrid, diversity on, k=3 | 95.0% | 0.800 | 90.0% | 27.5 |
| hybrid, diversity on, k=8 | 100.0% | 0.812 | 97.5% | 22.6 |

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
| 0.55 | 40.0% | 100.0% |
| 0.60 | 60.0% | 100.0% |

## Stage latency

One measurement per attempted question; index loaded at startup, with embedding cache reuse and the lazy encoder caveat above. Stage times may overlap or be aggregate times, so do not sum every row.

| Stage | p50 ms | p95 ms |
|---|---:|---:|
| bm25 | 15.1 | 33.1 |
| dense | 4.9 | 15.2 |
| embedding | 33.7 | 200.5 |
| fusion | 0.3 | 0.7 |
| generation | 678.6 | 4397.6 |
| retrieval | 55.7 | 248.1 |
| total | 722.5 | 49317.4 |
| verification | 0.3 | 0.7 |

## Separate earlier CLI benchmark

`artifacts/benchmark.json` records an earlier implementation: 30 uncached runs over 6 unique questions, with cold/lazy model work included. Wall mean/p50/p95 were **4142.3/80.9/2480.4 ms** and API cost was **$0.000000**. This artifact has no matching frozen source fingerprint and is not the final dev/holdout evaluation. Its repeated questions, cache state and timing setup differ, so it is not a like-for-like latency improvement measurement.

## Per-question diagnostics

Full question text, raw answer, citations, keypoints, token estimates and per-stage timing are in `results.json`. Gold evidence and scoring expressions are in `evaluation/questions.json`. Corpus validation is recorded in `gold_validation`.

| ID | Split | Category | Keypoint coverage | Hit@k | Page coverage | Answerability correct | Wall ms | Status |
|---|---|---|---:|---:|---:|---|---:|---|
| s1 | dev | straightforward | 100.0% | 1.000 | 100.0% | yes | 95 | PASS |
| s2 | dev | straightforward | 100.0% | 1.000 | 100.0% | yes | 77 | PASS |
| s4 | dev | straightforward | 100.0% | 1.000 | 100.0% | yes | 49318 | PASS |
| p1 | dev | paraphrased | 0.0% | 1.000 | 100.0% | yes | 257 | PARTIAL |
| p2 | dev | paraphrased | 100.0% | 1.000 | 100.0% | yes | 74 | PASS |
| p4 | dev | paraphrased | 0.0% | 1.000 | 100.0% | yes | 76 | PARTIAL |
| m1 | dev | multi-page | 50.0% | 1.000 | 50.0% | yes | 423 | PARTIAL |
| m4 | dev | multi-page | 0.0% | 1.000 | 100.0% | yes | 697 | PARTIAL |
| f1 | dev | misleading | 100.0% | 1.000 | 100.0% | yes | 91 | PASS |
| f3 | dev | misleading | 100.0% | 1.000 | 100.0% | yes | 130 | PASS |
| u1 | dev | unanswerable | n/a | n/a | n/a | yes | 24 | PASS |
| u3 | dev | unanswerable | n/a | n/a | n/a | yes | 27 | PASS |
| u6 | dev | unanswerable | n/a | n/a | n/a | yes | 5 | PASS |
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

- **p1**: missing keypoints: append adds an item to the end of the list. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **p4**: missing keypoints: venv creates and manages virtual environments. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m1**: missing keypoints: strings are immutable and cannot be changed. Expected-page retrieval miss or incomplete multi-page coverage. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
- **m4**: missing keypoints: list comprehensions concisely create lists, range excludes its endpoint. Excerpts omitted a gold component or regex missed equivalent phrasing; inspect raw answer. Next step: inspect development evidence and improve selection/composition against development questions only.
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

Run `python -m evaluation.run_eval --questions evaluation/questions.json --out results`. Local hardware, warm page cache, model download/cache and live source revisions affect latency and corpus content. Agent initialization is reported separately; any later lazy model load remains in query latency. Page hashes and dependency locks help identify drift. Tune on dev only, then report a fresh unchanged holdout run. A stronger next evaluation would expand independent paraphrases/negative cases, add human claim entailment review, and evaluate the optional synthesis provider under an explicit budget. Do not interpret these 26 questions as production readiness.

| Round | Dev regex coverage | Holdout regex coverage | Change |
|---|---:|---:|---|
| baseline (same revised scorer) | 60.0% | 10.0% | Original extractive implementation; development-only scorer synonyms applied to stored original answers. |
| dev-round1 | 55.0% | n/a | Saved development round; implementation changes described in DECISIONS.md. Holdout measured after final development choice only. |
| dev-round2 | 65.0% | n/a | Saved development round; implementation changes described in DECISIONS.md. Holdout measured after final development choice only. |
| dev-final (round 3) | 65.0% | 15.0% | Numeric qualifiers retained; explicit conjunction facets retrieve/select complementary evidence. Final code frozen before one holdout run. |

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
19. The final holdout includes a lazy model-load outlier; do not call all query times warm.
20. Improvements require development-only tuning and a frozen independent holdout.
