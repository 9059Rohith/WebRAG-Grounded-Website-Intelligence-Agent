# Cost analysis

Generated from `20260929T142544Z` on 2026-09-29T14:25:44.466874+00:00. Provider: **openai**.

## Observed run

| Quantity | Value |
|---|---:|
| Questions attempted, cache disabled | 38 |
| Query input tokens reported by the agent | 325,827 |
| Query output tokens reported by the agent | 5,760 |
| Query embedding tokens reported by the agent | 583 |
| Query API cost estimate from usage records | $0.052342 |
| Auxiliary retrieval/reporting API cost estimate | $0.000000 |
| Query plus auxiliary API cost estimate, excludes ingestion | $0.052342 |
| Total embedded chunk text tokens (includes headers) | 276,927 |

Provider usage records feed the cost estimate. The estimate is not an invoice and does not verify account-level billing. Failed calls, retries and usage not returned by the provider can cause uncertainty; inspect the per-question records.

## Saved ingestion observations

| Ingestion | Created UTC | Wall seconds | Embedding cache hits | Miss text tokens estimated | API cost estimate |
|---|---|---:|---:|---:|---:|
| Latest saved rebuild | 2026-09-29T13:51:46.486481+00:00 | 33.731 | 0 | 276,927 | $0.005539 |

The ingestion rows are separate observations and must not be summed when they identify the same run. A cached rebuild can report zero new embedding tokens while retaining the same corpus. Chunk token counts include title/heading headers. Embedding tokens are tiktoken estimates of text sent or locally encoded on cache misses, not API-returned embedding billing metadata. Paid embedding estimates use the configured standard rate.

## Standard pricing used for estimates

Pricing checked 2026-09-29: GPT-4o mini input **$0.15/1M** and output **$0.60/1M**, text-embedding-3-small **$0.02/1M**. Sources: [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small). These are standard token rates; no batch/cache discount is assumed.

## Observed provider usage extrapolation — scenario, not invoice

Mean observed answer-query API cost estimate: **$0.001377/query**, including the synthesis and verification/retry usage returned by the agent. Chat token-source labels in this run: **api_reported, estimated_tiktoken**. API-reported chat token counts include provider framing where metadata is returned; fallback counts and all embedding counts remain local text estimates. Failed calls or automatic client retries without returned usage can undercount spend. Auxiliary retrieval ablations are charged separately and excluded from this per-answer rate.

| Query volume | Observed per-query rate extrapolated | Assumed 30% cache hits |
|---|---:|---:|
| 100 | $0.1377 | $0.0964 |
| 1,000 | $1.3774 | $0.9642 |
| 10,000 | $13.7741 | $9.6419 |

The no-cache column extrapolates this small benchmark's actual mix of responses, refusals and retries. The cache column assumes 30% of requests incur no new provider work. Neither column is a measured load test or a billing guarantee. Refusals can already include paid generation/verification before refusal, so no additional zero-cost refusal discount is applied.

Example question: **What does list.append do?**. Observed returned usage: **9996/209/0** input/output/estimated embedding tokens; observed API cost estimate **$0.001625**.

Stored reconstructed prompt/answer text counts are diagnostics, not a second usage ledger: mean input/output **415.8/44.5** tokens. They omit chat framing, schemas, semantic-check prompts and retries and can differ from the actual provider request. They are not used to replace or discount the usage above. The archived local report retains its separate hypothetical OpenAI comparison.


## Five cost levers

1. Cache: a 30% hit rate reduces the illustrative query API cost by 30%, assuming cache hits skip embedding and synthesis.
2. Refusal gate: refusing before synthesis can reduce generation work, balanced against false refusals. A refusal after paid generation/verification still incurs that cost.
3. Smaller top-k: removing 200 context tokens would save about **$0.000030** per synthesized query; retrieval coverage can fall, so use the measured ablation.
4. Prompt trimming: eliminating 100 input tokens saves **$0.000015** per synthesized query; remove boilerplate before evidence.
5. Model tiering/local excerpts: the archived local run had $0 API cost. Compare paid synthesis quality on the actual saved benchmark; no semantic-quality improvement is inferred from model selection alone.

The default local embedding index cannot be reused as an OpenAI index: reingestion is required when the embedding identity changes. Context limits, output caps, batching, bounded retries and the answer cache constrain cost. A cache hit should report zero new query API usage; evaluation disables the cache so every result measures fresh query work. Monthly extrapolation is a scenario, not an observed load test or budget guarantee.
