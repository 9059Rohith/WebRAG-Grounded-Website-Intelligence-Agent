FROM python:3.11-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements.txt ./
# Resolve/install dependencies before copying application code so source edits
# reuse the heavy ML dependency layer. uv downloads independent wheels in parallel.
RUN python -m pip install uv==0.11.28
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --prefix=/install --python /usr/local/bin/python \
    --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match -r requirements.txt
COPY pyproject.toml ./
COPY src/ ./src/
COPY evaluation/ ./evaluation/
RUN --mount=type=cache,target=/root/.cache/uv uv pip install --prefix=/install --python /usr/local/bin/python --no-deps .

FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/data HF_HOME=/data/model-cache PORT=8000 HOME=/home/app
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --create-home app \
    && mkdir /data /app && chown app:app /data /app
COPY --from=builder /install /usr/local
WORKDIR /app
COPY --chown=app:app evaluation/ ./evaluation/
USER app
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/healthz',timeout=4)"
CMD ["sh", "-c", "exec uvicorn rag_agent.api:create_app --factory --host 0.0.0.0 --port \"${PORT:-8000}\""]
