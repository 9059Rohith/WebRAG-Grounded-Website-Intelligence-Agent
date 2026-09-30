# Vercel deployment

[Live application](https://webrag-assessment.vercel.app) · [Health](https://webrag-assessment.vercel.app/healthz) · [Readiness](https://webrag-assessment.vercel.app/readyz) · [API schema](https://webrag-assessment.vercel.app/openapi.json)

The production deployment includes the React UI, FastAPI, the original LangGraph workflow, real OpenAI embeddings/synthesis, Chroma/BM25, and the public Python documentation corpus: 40 pages and 1,597 passages. It is not a frontend-only demo. The key is a sensitive Vercel server environment variable and is never shipped to the browser.

## Reproduce or update the corpus

Use Python 3.12 and Node 22+. Follow the root README to install dependencies and configure the ignored local environment for OpenAI with DATA_DIR=data_openai. Ingestion is an owner-run CLI operation; the public API accepts questions against the bundled corpus.

```powershell
.venv\Scripts\rag.exe ingest
npm ci --prefix web
npm run build --prefix web
.venv\Scripts\python.exe scripts/prepare_vercel.py --require-frontend
vercel link --yes --project webrag-assessment --scope rohiths-projects-5e14931b --cwd deployment
# Enter the existing key privately at the CLI prompt; do not put it in command arguments.
vercel env add OPENAI_API_KEY production --sensitive --cwd deployment
vercel deploy --prod --yes --scope rohiths-projects-5e14931b --cwd deployment
```

For another account, use its own project and scope. Do not overwrite unrelated applications. Vercel detects `deployment/app.py:app` with the FastAPI preset; Python 3.12 and a 300-second maximum function duration are configured. The recorded build completed successfully at approximately 407 MB before dependency optimization and bytecode. Lean pinned requirements exclude Torch, Transformers, Sentence Transformers and downloaded local model weights.

Preparation verifies the provider, dimensions, active snapshot and public source URLs. It backs up/VACUUMs SQLite and copies only active Chroma data, required snapshots/stats, Python runtime source and compiled frontend assets. The generated directories are ignored by Git; they must exist before CLI deployment. `.env`, query embedding caches, raw pages, model weights and failed staging directories are excluded. GitHub automatic redeployment is not configured; build, prepare and deploy deliberately after a change.

## Persistence and operational limits

The immutable function bundle preserves the indexed corpus across cold starts. Each instance copies that index into versioned writable `/tmp` storage under a lock, because Chroma needs writable files. Per-instance query/embedding caches and rate limits are ephemeral. New public crawling jobs are not exposed; reingest locally and redeploy to update the corpus. This practical assessment deployment is single tenant, with no durable shared query cache or distributed rate limit. Estimated API costs exclude Vercel hosting and network charges.

The UI and API share an origin. Compiled scripts, styles and fonts are local assets permitted by the Content Security Policy; source text is rendered as plain text/React text nodes. Unknown API paths remain 404, and the repository/index/private environment files are never mounted as static content.

## Verify the actual public backend

```powershell
.venv\Scripts\python.exe scripts/verify_live.py --url https://webrag-assessment.vercel.app --out artifacts/vercel-http-smoke.json --allow-cold-cache
```

The cold-cache flag acknowledges that two serverless requests can reach different instances. Any observed cache hit must still report zero new usage and cost. Verification records include real answers/refusals, exact citations, usage, invalid input, readiness and browser interactions. GitHub Actions is active, but its jobs are blocked by the owner's GitHub billing lock; see [CI status](ci/README.md).

The machine-readable API schema is `/openapi.json`. The optional CDN-based Swagger/ReDoc pages are constrained by the strict CSP; use the local React workspace or the JSON schema for the hosted application.
