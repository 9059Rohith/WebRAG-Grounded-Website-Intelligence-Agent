"""Real embedding providers with a content-addressed, pickle-free disk cache."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from rag_agent.config import Settings
from rag_agent.cost import token_count, usage_cost
from rag_agent.schemas import Usage


class EmbeddingProvider:
    """Use real local sentence embeddings or LangChain OpenAI embeddings."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cache_dir = settings.data_dir / "embedding_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._model: Any = None
        self._lock = threading.Lock()
        self.last_usage = Usage(provider=settings.provider)
        self.last_cache_hits = 0

    def _load(self) -> Any:
        if self._model is None:
            if self.settings.provider == "local":
                # Use only PyTorch; host TensorFlow/Keras packages are unrelated.
                os.environ.setdefault("USE_TF", "0")
                os.environ.setdefault("USE_FLAX", "0")
                import torch
                from sentence_transformers import SentenceTransformer

                torch.set_num_threads(4)
                options = {
                    "device": "cpu",
                    "trust_remote_code": False,
                    "model_kwargs": {"use_safetensors": True},
                }
                try:
                    # A warm local model must not re-check online metadata on
                    # every CLI invocation or on the first uncached query.
                    self._model = SentenceTransformer(
                        self.settings.local_embedding_model, local_files_only=True, **options
                    )
                except OSError:
                    self._model = SentenceTransformer(
                        self.settings.local_embedding_model, **options
                    )
            else:
                from langchain_openai import OpenAIEmbeddings

                self._model = OpenAIEmbeddings(
                    model=self.settings.embedding_model,
                    api_key=self.settings.openai_api_key,
                    request_timeout=self.settings.llm_timeout_s,
                    max_retries=self.settings.llm_max_retries,
                )
        return self._model

    def embed_with_usage(self, texts: list[str]) -> tuple[list[list[float]], Usage]:
        """Cache each model/text pair and charge only cache misses."""
        with self._lock:
            result: list[list[float] | None] = [None] * len(texts)
            misses: list[tuple[int, str, Path]] = []
            for i, text in enumerate(texts):
                key = hashlib.sha256(
                    (self.settings.embedding_id + "\0" + text).encode()
                ).hexdigest()
                path = self.cache_dir / f"{key}.json"
                if path.exists():
                    result[i] = json.loads(path.read_text(encoding="utf-8"))
                else:
                    misses.append((i, text, path))
            tokens = sum(token_count(t) for _, t, _ in misses)
            if misses:
                model = self._load()
                pending = [t for _, t, _ in misses]
                if self.settings.provider == "local":
                    # Embed every token: MiniLM has a 256 wordpiece window. Average
                    # vectors for larger chunks rather than silently truncate them.
                    import numpy as np

                    segments: list[str] = []
                    groups: list[tuple[int, int]] = []
                    for text in pending:
                        ids = model.tokenizer.encode(text, add_special_tokens=False)
                        start = len(segments)
                        for offset in range(0, len(ids), 220):
                            segments.append(model.tokenizer.decode(ids[offset : offset + 220]))
                        groups.append((start, len(segments)))
                    values = model.encode(
                        segments, batch_size=64, normalize_embeddings=True, show_progress_bar=False
                    )
                    vectors = []
                    for start, end in groups:
                        vector = np.mean(values[start:end], axis=0)
                        vector = vector / max(float(np.linalg.norm(vector)), 1e-12)
                        vectors.append(vector.tolist())
                else:
                    vectors = model.embed_documents(pending)
                for (index, _, path), vector in zip(misses, vectors, strict=True):
                    result[index] = vector
                    # Separate CLI/API provider instances can write this key at
                    # once. Each writer needs its own file before atomic replace.
                    temporary = path.with_name(f".{path.stem}.{uuid.uuid4().hex}.tmp")
                    try:
                        temporary.write_text(json.dumps(vector), encoding="utf-8")
                        temporary.replace(path)
                    finally:
                        temporary.unlink(missing_ok=True)
            self.last_cache_hits = len(texts) - len(misses)
            usage = Usage(
                embedding_tokens=tokens,
                provider=self.settings.provider,
                estimated_usd=usage_cost(tokens, 0, 0, self.settings.provider),
            )
            self.last_usage = usage
            if any(v is None for v in result):
                raise RuntimeError("Embedding provider returned an incomplete batch")
            return [v for v in result if v is not None], usage

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return vectors for ingestion; query paths use explicit usage too."""
        return self.embed_with_usage(texts)[0]
