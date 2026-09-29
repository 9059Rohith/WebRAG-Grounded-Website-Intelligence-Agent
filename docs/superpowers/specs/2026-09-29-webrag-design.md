# Website-grounded RAG assessment design

Build a practical CLI/API product for MyAdvice, usable without paid credentials and optionally with OpenAI synthesis. The assignment and pasted notes define the scope; the user's explicit instruction to complete without questions overrides skill review pauses.

Ingestion: scoped public HTTP crawler with robots, DNS/IP checks, redirect validation, response limits and raw manifest; semantic HTML extraction; deterministic section/token chunks; real local sentence-transformer embeddings (or OpenAI); persistent Chroma and BM25.

Queries: LangGraph retrieve → relevance gate → generate → verify → bounded retry/refuse → finalize. Local mode returns source excerpts rather than claiming LLM synthesis. OpenAI uses strict structured claims and exact evidence citations. No model-generated tools or shell actions.

Evaluation: at least 26 real-corpus questions across five categories with dev/holdout separation, retrieval metrics, deterministic gold coverage, refusal/citation checks, latency and token/cost reports. Provider-dependent metrics remain explicitly unmeasured without credentials.

Deliverables: source, environment example, numbered README, rendered architecture, security/decisions, evaluation and cost reports, deployment/CI configurations, interview notes and 12-minute recording script. A personal webcam recording and email sending cannot be impersonated; preserve truthful handoff status.

Test unsafe URLs, malformed HTML, stale indexes, fake citations, provider failure, injection, API limits and full fixture ingestion/query. Run real website ingestion and HTTP API smoke separately. Never fabricate numbers or hide failed checks.
