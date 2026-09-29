# Email draft — not sent

To: [MyAdvice recruiter email]

Subject: AI Engineer Assessment — Website-grounded RAG Agent — Rohith

Hi [Recruiter name],

Thank you for the assessment. The repository contains a website-grounded retrieval agent against a bounded snapshot of Python documentation, with CLI and FastAPI interfaces, source evidence, evaluation, and cost reports.

Repository: [WebRAG — Grounded Website Intelligence Agent](https://github.com/9059Rohith/WebRAG-Grounded-Website-Intelligence-Agent)

Live application: [WebRAG on Vercel](https://webrag-assessment.vercel.app) — React UI and real grounded backend.

Supplementary walkthrough: [Project walkthrough video on GitHub](https://github.com/9059Rohith/WebRAG-Grounded-Website-Intelligence-Agent/blob/main/docs/video/WebRAG-Walkthrough.mp4). It uses explicitly disclosed **synthetic narration** and is not my voice or a webcam recording. The GitHub page provides the project-specific file/download; a personal Vidyard recording is an optional preferred format.

- Robots-aware scoped crawling with DNS/redirect guards and persisted source metadata.
- OpenAI embeddings and structured source-only synthesis, with real local embeddings/excerpts available as a credential-free fallback.
- Exact quote-reference binding and server-restored evidence, a separate semantic completeness check, and bounded refusal/retry control.
- Frozen evaluation with the original development/holdout questions plus independent holdout questions, recorded outputs, retrieval/citation/refusal diagnostics and provider usage.
- Cost analysis, security notes, dependency locks, container/deployment files and a preserved CI workflow with owner activation instructions.

<!-- EMAIL_METRICS_START -->
Independent holdout (12 questions): regex keypoint coverage **75.0%**, retrieval Hit@8 **8/8 (100.0%; 95% CI 67.6%–100.0%)**, unanswerable refusal **4/4 (100.0%; 95% CI 51.0%–100.0%)**. Query wall latency p50/p95 **4574.8/10960.4 ms**. Observed answer-query API cost estimate: **$0.052342**; ingestion and auxiliary work are separate. Paid synthesis was selected; inspect returned token metadata, errors and verification settings for actual execution. Agent/index initialization makes no provider warmup call. Query wall times include provider request/framing, synthesis, semantic verification and retries. Embedding-cache hits can skip paid encoding. Regex keypoint coverage and exact quotation provenance do not establish semantic faithfulness or human correctness. Independent semantic evaluation and human rating remain unmeasured; production quality is not established.
<!-- EMAIL_METRICS_END -->

The final README, evaluation, cost, and verification reports identify the recorded provider, exact measured results, remaining failures and limitations. The small benchmark and model-based verification do not establish production correctness; local historical measurements are retained separately.

Best regards,
Rohith

Owner checklist: fill the recipient/name and send personally. The verified 12:14 synthetic walkthrough matches the final paid run. Vidyard is an assessment pro tip; a personal recording can replace the synthetic video link if preferred. **This email is unsent.**

Current follow-up: both known false refusals were repaired; the inspected-question regression and original independent baseline are reported separately. Hosted GitHub Actions remains pending owner workflow authentication. The supplementary recording predates these UI/deployment repairs.
