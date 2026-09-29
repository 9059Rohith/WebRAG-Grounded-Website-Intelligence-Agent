# Architecture

![Ingestion and query architecture](architecture.svg)

## Deployed application

```mermaid
flowchart LR
  Owner[Owner CLI crawl / ingest] --> Seed[Validated immutable index bundle]
  Seed --> Tmp[Cold-start copy to writable /tmp]
  Browser[React / Vite workspace] --> API[Same-origin Vercel FastAPI]
  API --> Graph[Original grounded LangGraph workflow]
  Tmp --> Graph
  Graph --> OpenAI[Server-side embeddings and synthesis / verification]
  Graph --> Response[Answer / exact sources / usage]
  Response --> Browser
```

The compiled UI and full question-answering backend run together on Vercel. The corpus is durable in the bundle; instance caches and rate limits are ephemeral. Crawling/reingestion remains an owner-operated CLI step, followed by preparation and redeployment. See [deployment instructions](VERCEL.md).



The main measured assessment path uses OpenAI `text-embedding-3-small` retrieval and `gpt-4o-mini` structured synthesis, followed by a separate semantic `Check` verdict. The credential-free local fallback uses real Sentence Transformers embeddings and returns source excerpts. `Settings` still defaults to local mode; the recorded provider configuration identifies the main run. Both paths share deterministic citation verification and bounded LangGraph control flow. Website content is untrusted data and has no execution privileges.

```mermaid
flowchart TB
  subgraph Ingest[Offline ingestion]
    URL[Public start URL + allowed prefix] --> Guard[URL / DNS / redirect SSRF guard]
    Guard --> Crawl[Polite robots-aware crawler]
    Crawl --> Raw[Raw HTML + HTTP manifest]
    Raw --> Clean[Semantic main extraction + deduplication]
    Clean --> Chunk[Heading-aware token chunks + source metadata]
    Chunk --> Embed[Local Sentence Transformers or OpenAI embeddings]
    Embed --> Dense[(Persistent Chroma cosine index)]
    Chunk --> Sparse[(JSON chunks + rebuilt BM25)]
  end
  subgraph Query[Query request]
    Input[CLI / FastAPI question] --> Validate[Validate + limits + optional auth]
    Validate --> Cache{Versioned TTL cache hit?}
    Cache -- yes --> Final[Answer + verified sources + usage + timings]
    Cache -- no --> Retrieve[Dense + BM25 + comparison facets → RRF → diversification]
    Dense --> Retrieve
    Sparse --> Retrieve
    Retrieve --> Gate{Top 8 evidence; cosine gate 0.25}
    Gate -- no --> Refuse[Canonical insufficient-evidence refusal]
    Gate -- yes --> Generate[Local source excerpts or OpenAI claims + quote IDs]
    Generate --> Restore[Resolve quote IDs to exact server-owned evidence]
    Restore --> Verify{Exact source evidence valid?}
    Verify -- valid OpenAI --> Semantic{Separate supported Check: all claims and all parts?}
    Verify -- valid local --> Final
    Semantic -- yes --> Final
    Semantic -- no, first attempt --> Retry
    Semantic -- no, retry exhausted --> Refuse
    Verify -- no, first attempt --> Retry[Bounded query expansion]
    Retry --> Retrieve
    Verify -- no, retry exhausted --> Refuse
    Refuse --> Final
    Final --> Metrics[Per-request tokens / API estimate / stage timings]
  end
```

Metadata flows from the original page URL/title/heading through each stable chunk ID into retrieval hits and citation validation. The response URL is taken from stored chunk metadata; a model cannot invent a new citation URL. Embedding identity and index version prevent querying incompatible collections or reusing answers from an old corpus. A changed corpus requires deliberate ingestion.

OpenAI generation receives a table of exact source quotations identified as `q001`, `q002`, and so on. Each structured claim selects its quote ID and matching chunk ID. The server restores the actual quotation; unknown references or mismatched chunks remain invalid. It validates source occurrence, literal case, and provenance before a separate semantic prompt judges entailment and completeness. Unusable proposed claims may be removed before that complete-answer verdict, so the verdict must reject any resulting omission. This is a guardrail, not independent human verification or an unconditional correctness guarantee.

`Draft.answerable` means the website evidence supports an answer, including a supported negative answer or false-premise correction. It is not the truth value of a yes/no question. Explicit conjunction/comparison facets can reserve complementary dense evidence before the remaining top-eight slots are selected. The frozen relevance threshold is 0.25; source diversification remains a greedy URL penalty rather than full vector-pair MMR. Final evaluation and cost reports describe the recorded quality, errors, token usage, and latency of this configuration.

The rendered SVG is a dependency-free depiction of this flow. The compiled LangGraph diagram is captured below after the graph exists; it is separate from the full product architecture above.

<!-- GENERATED_GRAPH_START -->
```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	validate_input(validate_input)
	retrieve(retrieve)
	generate(generate)
	verify(verify)
	expand_query(expand_query)
	refuse(refuse)
	finalize(finalize)
	__end__([<p>__end__</p>]):::last
	__start__ --> validate_input;
	expand_query --> retrieve;
	generate --> verify;
	refuse --> finalize;
	retrieve -.-> generate;
	retrieve -.-> refuse;
	validate_input -.-> refuse;
	validate_input -.-> retrieve;
	verify -.-> expand_query;
	verify -.-> finalize;
	verify -.-> refuse;
	finalize --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```
<!-- GENERATED_GRAPH_END -->
