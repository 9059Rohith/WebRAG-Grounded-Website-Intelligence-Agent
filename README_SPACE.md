---
title: Website Grounded Agent
emoji: 📚
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

This repository can run as a Docker Hugging Face Space. Set the Space variable `PORT=7860`, `PROVIDER=local`, and `DATA_DIR=/data`; configure `API_TOKEN` as a secret for public use. Set `HF_HOME=/data/model-cache` when persistent storage is available.

The demo appears at `/`. `/healthz` confirms the server is running; `/readyz` reports readiness only after an index loads. Ingest the Python tutorial before serving by running `rag ingest` with the same data directory. An empty deployment deliberately starts unready. In an environment with terminal access, stop the server, ingest, and restart it so the application loads the new index.

The first local ingestion downloads the sentence-transformer model. The image runs as UID 10001: mount writable storage with compatible ownership. Persistent storage is required to retain the index across container rebuilds. A deployment with ephemeral storage must regenerate its index after every rebuild; there is no automatic public ingestion endpoint.

The default mode produces sourced extracts without paid API calls. To use OpenAI, set `PROVIDER=openai` and add `OPENAI_API_KEY` as a secret, then create a separate compatible index. See the repository README for local setup, verified evaluation, and limitations.
