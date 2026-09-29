# Interview preparation — 20 questions

1. **Why 200-token chunks and 30-token overlap?**
   The local MiniLM encoder has a short wordpiece input window; 200 tiktoken tokens is a conservative compromise. Oversized inputs split into 220-wordpiece windows and vectors are averaged; overlap preserves some boundary context.

2. **Why this embedding model?**
   The measured OpenAI path uses text-embedding-3-small with its own provider identity/index; the local fallback uses real 384-dimensional all-MiniLM-L6-v2 vectors without paid credentials. Switching providers requires compatible reingestion.

3. **Why hybrid retrieval?**
   BM25 preserves identifiers such as `sys.path`; dense retrieval helps paraphrases. RRF combines ranks without pretending BM25 and cosine scores share a scale; the evaluation reports both alternatives.

4. **Why top-k eight and a 0.25 gate?**
   The frozen main configuration allows more complementary evidence, with relevant comparison facets reserved before the remaining slots are chosen. Report measured top-k/threshold trade-offs; a lower cosine gate or retrieval hit does not establish answer correctness.

5. **Is the diversification true MMR?**
   No: it applies a greedy penalty to repeated source URLs using the configured lambda. Full vector-pair MMR would require additional similarity comparisons and a separate measured trade-off.

6. **How do you prevent hallucination?**
   OpenAI claims select exact quote IDs and matching chunk IDs; the server restores source evidence, checks provenance, and requests a separate semantic completeness verdict. Local fallback quotes sources. These controls reduce risk but do not guarantee correctness.

7. **How are unanswerable questions detected?**
   Relevance gates first; inadequate or unsupported evidence refuses after at most one retry. `Draft.answerable` means evidence supports an answer, including a documented negative answer or false-premise correction; it is not a yes/no truth value.

8. **How do URLs survive the pipeline?**
   Page URLs and titles enter stable chunk metadata, remain in retrieval hits and are validated at citation time. Output citation URLs come from the stored chunks, rather than model-generated links.

9. **Why LangGraph?**
   Conditional retrieve/generate/verify/retry/refuse transitions are visible and testable. The graph is bounded and has no model-controlled tools, rather than an unconstrained action loop.

10. **How do you handle source changes?**
    Explicit reingestion replaces the index and version; cache entries include that version. Saved crawl reuse preserves a snapshot, but automatic scheduling and ETag freshness are deferred.

11. **What happens if sources contradict each other?**
    The current system preserves evidence/source provenance but has no robust contradiction resolver. A production version should return conflicting quotes with dates and uncertainty instead of merging them silently.

12. **What is the cost at 10,000 queries?**
    Use the final cost report's observed query usage for the selected OpenAI run, plus separately recorded embedding/evaluation work and clearly labeled cache/refusal scenarios. The historical local API rate was $0; operating costs and an account invoice remain separate.

13. **What are the evaluation weaknesses?**
    The original 26 questions were explored during local development; 12 extra independent holdout questions help assess the frozen paid path. Regex and small samples remain limited. Separate any model-judge measurements from deterministic provenance and independent human review.

14. **How does prompt-injection protection work?**
    Sources and quote-table entries are escaped untrusted data with no execution privileges. Reference binding, exact evidence checks, a separate semantic verdict and injection fixtures add checks; filtering and model verification are not formal security proofs.

15. **What is the SSRF boundary?**
    URLs, scopes, redirects and every resolved IP are checked; validated public IPs are pinned when connecting while preserving TLS hostname checks. Production egress policy is still useful defense beyond application checks.

16. **How would you scale to a million pages?**
    Separate scheduled ingestion workers from serving, persist incremental content/version metadata and use a server vector database plus shared lexical search. Add crawl queues, observability, shard/tenant partitioning and evaluation for recall/cost.

17. **How would you add multiple tenants?**
    Scope each tenant's corpus/index/cache, require tenant authorization and test isolation at every retrieval/metadata boundary. This assessment is single-tenant; merely adding a tenant ID to prompts is insufficient.

18. **What does the cache store?**
    A bounded TTL LRU holds verified answers keyed by normalized question and index identity/version. A hit reports zero new query API cost; current cache and rate limiting are process-local.

19. **How are latency and failures measured?**
    Record wall time and named stages, including provider generation and separate semantic checks, with answer caching disabled during evaluation. Preserve errors and startup/warmup details. Lazy local-encoder outliers belong to the historical local report, not the paid headline.

20. **What would you improve first?**
    Keep the final application frozen while reporting its paid assessment. Next improve independent human-reviewed tests, freshness, shared quotas and comparison coverage in a newly labeled development cycle rather than tuning against final holdout results.
