# Cost analysis

Generated from `20260929T133418Z-combined` on 2026-09-29T13:34:18.305889+00:00. Provider: **local**.

## Observed run

| Quantity | Value |
|---|---:|
| Questions attempted, cache disabled | 26 |
| Query input tokens reported by the agent | 0 |
| Query output tokens reported by the agent | 0 |
| Query embedding tokens reported by the agent | 8,825 |
| Query API cost estimate from usage records | $0.000000 |
| Total embedded chunk text tokens (includes headers) | 276,927 |

The run used local sentence-transformer embeddings and deterministic extractive answers. It made no paid model API calls, so API spend was $0. Token counts are local tiktoken estimates, not provider billable usage. CPU, RAM, disk, bandwidth, electricity and host costs were not measured; $0 API spend does not mean zero operating cost.

## Saved ingestion observations

| Ingestion | Created UTC | Wall seconds | Embedding cache hits | Miss text tokens estimated | API cost estimate |
|---|---|---:|---:|---:|---:|
| Initial real ingestion | 2026-09-29T13:06:14.678654+00:00 | 291.978 | 0 | 276,927 | $0.000000 |
| Latest saved rebuild | 2026-09-29T13:10:06.647270+00:00 | 51.704 | 1597 | 0 | $0.000000 |

The initial ingestion record and latest rebuild are separate observations. A cached rebuild can report zero new embedding tokens while retaining the same corpus; it does not mean the index contains no tokens. Chunk token counts include title/heading embedding headers. Local embedding tokens represent estimated text encoded on cache misses, including candidate sentences during queries, rather than billable LLM usage.

## Hypothetical OpenAI comparison — not measured

Pricing checked 2026-09-29: GPT-4o mini input **$0.15/1M** and output **$0.60/1M**, text-embedding-3-small **$0.02/1M**. Sources: [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [text-embedding-3-small](https://developers.openai.com/api/docs/models/text-embedding-3-small). These are standard token rates; no batch/cache discount is assumed.

For each local question, the runner constructed a synthesis prompt from a fresh retrieval of the original question and counted its system/user text and the returned extractive answer with tiktoken. When the local graph retried, this original-query bundle can differ from the final trace. Local semantic sentence ranking can also embed candidate evidence; those observed local embedding tokens are separate from the hypothetical question/facet OpenAI retrieval embeddings. Mean (p95) counterfactual input: **1245.5 (1396)**, output: **71.2 (141)**, query/facet embedding: **16.7 (32)** tokens. These are measured text lengths, not measured OpenAI usage. Embedding estimates include the original question and deterministic explicit-conjunction facets; retry embeddings are excluded. Chat framing, structured-output schemas, verification/retry prompts and a different generated answer would change billing. This gives an illustrative **$0.000230/query** before those overheads.

Example question: **What does list.append do?**. Retrieved context chunks: **5**. Constructed prompt/output/query embedding text: **1297/129/6** tokens; hypothetical standard-rate cost **$0.000272**; observed query API cost **$0.000000**.

| Query volume | Hypothetical no cache | Hypothetical 30% cache hits | Hypothetical observed refusal gating | Observed local API rate projected |
|---|---:|---:|---:|---:|
| 100 | $0.0230 | $0.0161 | $0.0166 | $0.00 |
| 1,000 | $0.2299 | $0.1609 | $0.1657 | $0.00 |
| 10,000 | $2.2987 | $1.6091 | $1.6569 | $0.00 |

The cache scenario assumes 30% hits and no paid query work on a hit. Gating uses the observed fraction of refused local answers (30.8%) and omits synthesis cost on those questions while retaining embedding cost; these are scenarios, not observed load or billing. Embedding the observed 276,927 embedded chunk text tokens once at the hypothetical OpenAI rate gives **$0.005539**; headers are included, but provider tokenization/billing differences can change the estimate.

## Five cost levers

1. Cache: a 30% hit rate reduces the illustrative query API cost by 30%, assuming cache hits skip embedding and synthesis.
2. Refusal gate: skipping synthesis on the observed refused queries yields the gating column; it must be balanced against false refusals.
3. Smaller top-k: removing 200 context tokens would save about **$0.000030** per synthesized query; retrieval coverage can fall, so use the measured ablation.
4. Prompt trimming: eliminating 100 input tokens saves **$0.000015** per synthesized query; remove boilerplate before evidence.
5. Model tiering/local excerpts: the observed local API cost is $0; optional paid synthesis improves readability but requires a separate quality/cost measurement. No percentage improvement is claimed without that run.

The default local embedding index cannot be reused as an OpenAI index: reingestion is required when the embedding identity changes. Context limits, output caps, batching, bounded retries and the answer cache constrain cost. A cache hit should report zero new query API usage; evaluation disables the cache so every result measures fresh query work. Monthly extrapolation is a scenario, not an observed load test or budget guarantee.
