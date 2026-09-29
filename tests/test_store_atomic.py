"""A failed snapshot publication must leave the prior index readable."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from rag_agent.config import Settings
from rag_agent.schemas import Chunk
from rag_agent.vectorstore import VectorStore


def fixture_chunk(index: int, generation: str = "new") -> Chunk:
    text = f"{generation} explanatory source content number {index}."
    return Chunk(
        chunk_id=f"{generation}-{index}",
        source_url=f"https://example.test/{generation}/{index}",
        title="Guide",
        heading_path="Guide",
        text=text,
        embedded_text=text,
        token_count=8,
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
        chunk_index=index,
    )


def test_second_batch_failure_preserves_readable_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path, _env_file=None)
    store = VectorStore(settings, create=True)
    original = fixture_chunk(0, "original")
    store.replace([original], [[1.0, 0.0]], {"pages": 1})
    previous_pointer = store.stats_path.read_bytes()
    collection_class = type(store.collection)
    real_upsert = collection_class.upsert
    calls = 0

    def interrupted(collection: Any, *args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated second-batch storage interruption")
        return real_upsert(collection, *args, **kwargs)

    monkeypatch.setattr(collection_class, "upsert", interrupted)
    with pytest.raises(RuntimeError, match="second-batch"):
        store.replace([fixture_chunk(i) for i in range(101)], [[1.0, 0.0]] * 101, {"pages": 101})
    assert calls == 2
    assert store.stats_path.read_bytes() == previous_pointer
    reloaded = VectorStore(settings)
    assert reloaded.collection.count() == 1
    assert [chunk.chunk_id for chunk in reloaded.chunks] == [original.chunk_id]
    assert reloaded.search([1.0, 0.0], 1)[0][0].chunk_id == original.chunk_id


def test_stats_publication_failure_preserves_prior_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path, _env_file=None)
    store = VectorStore(settings, create=True)
    original = fixture_chunk(0, "original")
    store.replace([original], [[1.0, 0.0]], {"pages": 1})
    previous_pointer = store.stats_path.read_bytes()
    real_replace = Path.replace

    def publication_error(path: Path, target: str | Path) -> Path:
        if Path(target) == store.stats_path:
            raise OSError("simulated stats pointer publication interruption")
        return real_replace(path, target)

    monkeypatch.setattr(Path, "replace", publication_error)
    with pytest.raises(OSError, match="publication interruption"):
        store.replace([fixture_chunk(1)], [[0.0, 1.0]], {"pages": 1})
    assert store.stats_path.read_bytes() == previous_pointer
    reloaded = VectorStore(settings)
    assert [chunk.chunk_id for chunk in reloaded.chunks] == [original.chunk_id]
    assert reloaded.search([1.0, 0.0], 1)[0][0].chunk_id == original.chunk_id


def test_convenience_export_failure_does_not_invalidate_committed_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path, _env_file=None)
    store = VectorStore(settings, create=True)
    store.replace([fixture_chunk(0, "original")], [[1.0, 0.0]], {"pages": 1})
    real_replace = Path.replace

    def export_error(path: Path, target: str | Path) -> Path:
        if Path(target) == store.chunk_path:
            raise OSError("simulated convenience export failure")
        return real_replace(path, target)

    monkeypatch.setattr(Path, "replace", export_error)
    replacement = fixture_chunk(1)
    result = store.replace([replacement], [[0.0, 1.0]], {"pages": 1})
    assert result["added"] == 1
    reloaded = VectorStore(settings)
    assert [chunk.chunk_id for chunk in reloaded.chunks] == [replacement.chunk_id]
    assert reloaded.search([0.0, 1.0], 1)[0][0].chunk_id == replacement.chunk_id
