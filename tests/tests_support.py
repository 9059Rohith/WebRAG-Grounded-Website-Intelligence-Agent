"""Small explicit fixture stores used in provider-adapter tests."""

from __future__ import annotations

from rag_agent.config import Settings
from rag_agent.schemas import Chunk
from rag_agent.vectorstore import VectorStore


def build_test_store(settings: Settings) -> VectorStore:
    store = VectorStore(settings, create=True)
    chunk = Chunk(
        chunk_id="test",
        source_url="https://example.com/docs",
        title="Lists",
        heading_path="Lists",
        text="Lists are mutable sequences.",
        embedded_text="Lists are mutable sequences.",
        token_count=5,
        content_hash="test",
        chunk_index=0,
    )
    store.replace([chunk], [[1.0, 0.0, 0.0]], {"pages": 1})
    return store
