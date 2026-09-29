# Technical decisions

## ADR 01 — OpenAI assessment path and runnable local fallback
Choice: measure the assessment's main path using OpenAI embeddings and structured synthesis, while retaining real Sentence Transformers embeddings and source excerpts as a credential-free local fallback. Configuration still defaults to local mode.
Reason: the owner subsequently authorized paid-provider work and privately supplied a key. Recorded provider evaluation, HTTP evidence, and usage distinguish that main run from the earlier local baseline. Fakes remain confined to offline tests. Provider semantic verification is not independent human review; any separate model-judge results must identify their sample and cost.

## ADR 02 — Website and scope
Choice: English Python documentation, seed `/3/tutorial/index.html`, scope `/3/`, default 40 pages.
Reason: static technical pages retain source structure and provide multi-page and false-premise material. Candidate evidence is retained in [site_selection.json](site_selection.json).
Trade-off: `/3/` can move with the current Python release; page hashes describe the evaluated snapshot. The tutorial alone is too small for the page-count requirement.

Live 2026-09-29 shallow probes all returned HTTP 200, allowed seed crawling via robots and provided raw main text: Hugging Face Transformers 5,041 characters / 11 directly scoped seed links; LangChain 8,404 / 33; Python tutorial index 6,122 / 30. These seed counts are not exhaustive website counts. The successful Python BFS then fetched 40 scoped content pages in 34.924 seconds with no recorded crawl errors, 0.5-second effective delay and 3,728,116 raw bytes. Mean extracted content was 21,370.2 characters across those pages; the final 1,597 chunks contained 276,927 text tokens, maximum 199 per chunk. The earlier candidates were not conclusively disqualified by a full crawl; selecting Python after these shallow probes is a documented practical deviation from the requested first-passing-candidate rule, not a claim that those sites cannot be crawled.

## ADR 03 — Chunk window follows the embedding model
Options: requested 600-token defaults or a size compatible with the local short-window encoder.
Choice: 200 tiktoken tokens with 30-token overlap and title/heading headers; minimum 20 tokens.
Reason: the original local baseline's MiniLM accepts approximately 256 wordpieces. Oversized local inputs split into 220-wordpiece windows and normalized segment vectors are averaged. The same small source chunks are retained for the paid index to keep the corpus comparison stable. Averaging can dilute meaning; larger chunk-size ablations remain unmeasured.

## ADR 04 — Explicit graph rather than a free-running agent
Choice: LangGraph retrieve/gate/generate/verify/retry/refuse/finalize with one query retry.
Reason: bounded transitions are auditable, testable and constrain cost. Retrieved text has no execution privileges.
Trade-off: graph retry is a simple deterministic expansion, not a research agent with arbitrary browsing tools.

## ADR 05 — Persistent embedded retrieval
Options: Chroma, Qdrant or Postgres/pgvector; dense-only or hybrid retrieval.
Choice: Chroma cosine index plus JSON-backed BM25 and reciprocal rank fusion. Embedding identity/version checks prevent silent index mismatch.
Reason: low operational complexity for a bounded corpus. Immutable generation collections and JSON snapshots switch via one atomic stats.json pointer, preserving old readers when rebuild fails; pages absent from bounded recrawls are retained rather than silently deleted. Per-chunk incremental upsert is deferred.

## ADR 06 — Source diversity approximation
Choice: greedy repeated-source penalty rather than pairwise vector MMR or a paid reranker.
Reason: inexpensive source diversity improves chances of multi-page evidence and is easy to inspect. Dense/hybrid/diversity/top-k ablations report actual differences.
Trade-off: this does not optimize full MMR and cannot guarantee all required facts are in the selected evidence.

## ADR 07 — Quote validation has a narrow claim
Choice: supply OpenAI generation an exact quote table, accept quote-reference IDs with matching chunk IDs, restore source-owned evidence on the server, then validate occurrence and provenance. A separate semantic `Check` judges every claim and completeness against the actual question.
Reason: models can alter literal quotes when asked to regenerate them. Reference restoration preserves source words and case; the separate verdict avoids confusing the generation schema's answerability flag with a yes/no truth value.
Trade-off: exact quote provenance alone is not entailment, correctness or completeness. The semantic check is another provider call with cost and model-error risk, rather than an independent human guarantee.

## ADR 08 — Evaluation without impersonating a judge
Choice: retain the original 26 source-checked development/holdout questions and add 12 independent holdout questions for the final frozen paid assessment. Record deterministic keypoint coverage, retrieval, refusals, Wilson intervals, raw outputs, and separately identified provider/model-judge measurements where run.
Reason: local development experiments already used the original benchmark. Extra independent questions provide another view of generalization; transparent diagnostics and saved failures prevent unsupported quality claims.
Trade-off: regex scoring can miss synonyms and reward incidental matches; hand-written samples remain small and biased. Earlier exploration limits how strongly the original holdout can be treated as unseen. No retrospective gold edits or application tuning belong after the final freeze.

## ADR 09 — Cost estimates are separate from expenditure
Choice: report actual returned OpenAI usage metadata for the authorized main run, including generation, semantic checks, retries and evaluation auxiliary work where recorded. Preserve the earlier local $0 API baseline and its hypothetical synthesis projections as historical comparisons.
Reason: an API estimate is distinct from an account invoice. Failed calls or absent metadata can create uncertainty; computation and hosting remain unpriced. The final cost report identifies the provider and separates observation from scenarios at 100/1,000/10,000 queries.
Sources: [GPT-4o mini](https://developers.openai.com/api/docs/models/gpt-4o-mini), [embedding model](https://developers.openai.com/api/docs/models/text-embedding-3-small).

## ADR 10 — Politeness and crawl cache are explicit
Choice: sequential breadth-first crawl, robots checks, public DNS connection pinning and bounded responses/redirects.
Reason: global host delay is simple to enforce, and network-level pinning closes validation/connection DNS rebinding gaps.
Trade-off: parallel crawl, sitemap discovery, ETag/Last-Modified conditional requests and semantic near-deduplication are deferred. Reusing a saved snapshot does not prove freshness.

## ADR 11 — Submission authenticity
Choice: provide the repository, a disclosed synthetic project walkthrough, optional personal recording notes, and an unsent email draft with project-specific links.
Reason: the optional preferred Vidyard webcam narration requires the owner; repository and deployment publication require usable account access. The assessment labels Vidyard as a pro tip.
Trade-off: a GitHub blob/download link is distinct from a dedicated hosted video viewer. Confirm the final regenerated video and recipient access before sending. No synthetic narration is presented as the candidate's personal voice or webcam recording.

## ADR 12 — Explicit Chroma audit acceptance
Choice: document and narrowly ignore four unpatched Chroma server/RBAC advisories in the audit command.
Reason: this product uses embedded PersistentClient and exposes no Chroma HTTP routes, attacker-selected model or remote-code option. The audit feed and IDs remain in SECURITY.md.
Trade-off: this is a deployment-specific scope acceptance, not remediation. Dynamic models, a Chroma server or tenant support require reevaluation; the audit wrapper maps the official CPU wheel to its upstream release for advisory checks, preserving the provenance/normalization note.

## ADR 13 — Safer local weight and cache handling
Choice: safetensors-only local weights, remote code disabled, unique temporary cache files and atomic file replacement.
Reason: avoid remote model code/pickle weight execution and concurrent same-key writer collisions; failure cleanup is tested.
Trade-off: the Hub model revision is not explicitly pinned yet. Model/provider identity checks do not detect an upstream weight revision; pin and fingerprint weights before stronger reproducibility claims.

## ADR 14 — Development-driven evidence improvements
Historical local development regex coverage was 60% after the documented scorer correction. Semantic sentence ranking and topic coverage produced 55% in round 1; expanded evidence selection produced 65% in round 2.
Round 3 retained numeric qualifiers and added explicit conjunction facets for complementary retrieval/quotation; local development coverage stayed 65%. Those earlier local measurements are retained separately from the final frozen OpenAI assessment.
Reason: improve evidence choice and refusal conservatism using development diagnostics, with every saved round retained. Holdout expressions and gold facts/URLs were unchanged; final scores and remaining failures determine the honest outcome.

## ADR 15 — Video preparation and authenticity
Choice: provide a local walkthrough with explicitly disclosed synthetic narration as supplementary material, alongside the personal 12-minute Vidyard recording script.
Reason: a generated narrated video can demonstrate the artifact. The assessment presents personal Vidyard webcam/voice recording as an optional pro tip, and the owner can choose that preferred format.
Trade-off: synthetic narration is disclosed and does not impersonate the candidate. The email remains a draft; its supplementary video link needs verification and its optional personal-recording line can be removed if unused.

## ADR 16 — Retain final latency setup and outliers
Historical local run: preserve its raw responses and approximately 49-second/125-second lazy encoder-load outliers. Its cache-served warmup did not force encoder loading, so those percentiles mixed reuse with lazy local-model work.
Current main run: report OpenAI network, generation and separate semantic-check latency from the frozen paid evaluation. Do not carry the historical local outlier explanation into the paid headline. Startup, warm/cold state, errors and answer-cache settings remain explicit in the final report.

## ADR 17 — Frozen retrieval and answerability semantics
Choice: top-eight evidence, cosine gate 0.25, explicit comparison-facet reservation, RRF and a greedy source penalty. OpenAI structured claims choose quote IDs; the server restores exact evidence before deterministic and separate semantic checks.
Reason: a combined query can otherwise fill context with one side of a comparison. Reserving relevant facet evidence makes both concepts available. `Draft.answerable=true` means evidence supports an answer to the question, including a negative answer or false-premise correction; it does not mean the premise is true.
Trade-off: threshold/facet heuristics and the model verdict can still fail or over-refuse. Freeze this implementation before the final assessment and report errors, partial answers and auxiliary paid costs rather than changing the application to fit final results.
