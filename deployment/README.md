Run `python scripts/prepare_vercel.py` from the repository after building
`web/dist`. Deploy the resulting `deployment/` directory with Vercel's FastAPI
framework preset. `app.py` exports the original FastAPI application and loads
the original LangGraph agent and Chroma index from `runtime/rag_agent`.

Set `OPENAI_API_KEY` in the Vercel project environment. Never upload `.env`.
The wrapper forces `PROVIDER=openai`, disables dotenv loading, and seeds a
versioned writable copy of the bundled public index under `/tmp`. The shipped
index survives every cold start. Per-instance query/embedding caches and rate
limits are ephemeral; a deployment is not a durable ingestion service.

Python 3.12 is selected by `.python-version`. The separate pinned runtime
requirements exclude Torch, Transformers, Sentence Transformers, and local
model weights. Chroma's supported dependency tree still includes ONNX Runtime
and Tokenizers. The preparation command prints public file counts and bytes,
and verifies the active snapshot and Chroma collection before packaging.

The CLI and crawler remain included in the copied application source.
Ingestion remains an owner-operated CLI operation: reingest in the normal
repository, rerun preparation, then redeploy to change the bundled corpus.
The HTTP API exposes the existing question, statistics, health, and readiness
routes; it does not accept arbitrary public crawling jobs.

See the repository deployment instructions for authentication, environment
configuration, frontend builds, and CI.
