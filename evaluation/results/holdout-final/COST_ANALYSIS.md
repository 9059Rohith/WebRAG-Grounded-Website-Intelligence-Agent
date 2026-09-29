# Cost analysis

Generated from `20260929T133418Z` on 2026-09-29T13:34:18.305889+00:00. Provider: **local**.

## Observed run

| Quantity | Value |
|---|---:|
| Questions attempted, cache disabled | 13 |
| Query input tokens reported by the agent | 0 |
| Query output tokens reported by the agent | 0 |
| Query embedding tokens reported by the agent | 8,518 |
| Query API cost estimate from usage records | $0.000000 |
| Total embedded chunk text tokens (includes headers) | 276,927 |

The run used local sentence-transformer embeddings and deterministic extractive answers. It made no paid model API calls, so API spend was $0. Token counts are local tiktoken estimates, not provider billable usage. CPU, RAM, disk, bandwidth, electricity and host costs were not measured; $0 API spend does not mean zero operating cost.

## Hypothetical OpenAI comparison — not measured

Pricing checked 2026-09-29: GPT-4o mini input **$0.15/1M** and output **$0.60/1M**, text-embedding-3-small **$0.02/1M**. Sources: [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small). These are standard token rates; no batch/cache discount is assumed.

For each local question, the runner constructed a synthesis prompt from a fresh retrieval of the original question and counted its system/user text and the returned extractive answer with tiktoken. When the local graph retried, this original-query bundle can differ from the final trace. Local semantic sentence ranking can also embed candidate evidence; those observed local embedding tokens are separate from the hypothetical single OpenAI query embedding. Mean (p95) counterfactual input: **1209.8 (1331)**, output: **53.4 (97)**, query embedding: **14.2 (20)** tokens. These are measured text lengths, not measured OpenAI usage. Chat framing, structured-output schemas, verification/retry prompts and a different generated answer would change billing. This gives an illustrative **$0.000214/query** before those overheads.

Example question: **When does a finally clause execute in a try statement?**. Retrieved context chunks: **5**. Constructed prompt/output/query embedding text: **1114/89/11** tokens; hypothetical standard-rate cost **$0.000221**; observed query API cost **$0.000000**.

| Query volume | Hypothetical no cache | Hypothetical 30% cache hits | Hypothetical observed refusal gating | Observed local API rate projected |
|---|---:|---:|---:|---:|
| 100 | $0.0214 | $0.0150 | $0.0138 | $0.00 |
| 1,000 | $0.2138 | $0.1496 | $0.1384 | $0.00 |
| 10,000 | $2.1378 | $1.4965 | $1.3841 | $0.00 |

The cache scenario assumes 30% hits and no paid query work on a hit. Gating uses the observed fraction of refused local answers (38.5%) and omits synthesis cost on those questions while retaining embedding cost; these are scenarios, not observed load or billing. Embedding the observed 276,927 embedded chunk text tokens once at the hypothetical OpenAI rate gives **$0.005539**; headers are included, but provider tokenization/billing differences can change the estimate.

## Five cost levers

1. Cache: a 30% hit rate reduces the illustrative query API cost by 30%, assuming cache hits skip embedding and synthesis.
2. Refusal gate: skipping synthesis on the observed refused queries yields the gating column; it must be balanced against false refusals.
3. Smaller top-k: removing 200 context tokens would save about **$0.000030** per synthesized query; retrieval coverage can fall, so use the measured ablation.
4. Prompt trimming: eliminating 100 input tokens saves **$0.000015** per synthesized query; remove boilerplate before evidence.
5. Model tiering/local excerpts: the observed local API cost is $0; optional paid synthesis improves readability but requires a separate quality/cost measurement. No percentage improvement is claimed without that run.

The default local embedding index cannot be reused as an OpenAI index: reingestion is required when the embedding identity changes. Context limits, output caps, batching, bounded retries and the answer cache constrain cost. A cache hit should report zero new query API usage; evaluation disables the cache so every result measures fresh query work. Monthly extrapolation is a scenario, not an observed load test or budget guarantee.
