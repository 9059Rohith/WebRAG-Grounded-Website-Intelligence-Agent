"""Independent provider instances must publish caches without shared temp files."""

from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import numpy as np
import pytest

from rag_agent.config import Settings
from rag_agent.embeddings import EmbeddingProvider


class FixtureModel:
    tokenizer = SimpleNamespace(
        encode=lambda text, add_special_tokens=False: [1, 2], decode=lambda ids: "fixture text"
    )

    def encode(self, segments: list[str], **kwargs: Any) -> Any:
        return np.array([[1.0, 0.0] for _ in segments])


def test_two_providers_publish_same_cache_key_without_tempfile_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path, _env_file=None)
    providers = [EmbeddingProvider(settings), EmbeddingProvider(settings)]
    for provider in providers:
        provider._model = FixtureModel()
    both_written = threading.Barrier(2)
    first_replaced = threading.Event()
    lock = threading.Lock()
    arrivals = 0
    paths: list[Path] = []
    original_replace = Path.replace

    def scheduled_replace(path: Path, target: str | Path) -> Path:
        nonlocal arrivals
        if path.suffix != ".tmp":
            return original_replace(path, target)
        with lock:
            order = arrivals
            arrivals += 1
            paths.append(path)
        both_written.wait(timeout=10)
        if order == 1:
            assert first_replaced.wait(timeout=10)
            return original_replace(path, target)
        try:
            return original_replace(path, target)
        finally:
            first_replaced.set()

    monkeypatch.setattr(Path, "replace", scheduled_replace)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(provider.embed_with_usage, ["same question"]) for provider in providers
        ]
        values = [future.result(timeout=15) for future in futures]
    assert values[0][0] == values[1][0] == [[1.0, 0.0]]
    assert len(set(paths)) == 2
    assert len(list(providers[0].cache_dir.glob("*.json"))) == 1
    assert not list(providers[0].cache_dir.glob("*.tmp"))


def test_cache_tempfile_cleaned_up_after_publication_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = EmbeddingProvider(Settings(data_dir=tmp_path, _env_file=None))
    provider._model = FixtureModel()

    def failed_replace(path: Path, target: str | Path) -> Path:
        raise OSError("simulated cache publication failure")

    monkeypatch.setattr(Path, "replace", failed_replace)
    with pytest.raises(OSError, match="publication failure"):
        provider.embed_with_usage(["new question"])
    assert not list(provider.cache_dir.iterdir())


def test_local_model_requires_safetensors_and_no_remote_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    arguments: dict[str, Any] = {}
    model = FixtureModel()

    def safe_model(*args: Any, **kwargs: Any) -> FixtureModel:
        arguments.update(kwargs)
        return model

    torch_module = ModuleType("torch")
    torch_module.set_num_threads = lambda count: None  # type: ignore[attr-defined]
    sentence_module = ModuleType("sentence_transformers")
    sentence_module.SentenceTransformer = safe_model  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "torch", torch_module)
    monkeypatch.setitem(sys.modules, "sentence_transformers", sentence_module)
    monkeypatch.setenv("USE_TF", "0")
    monkeypatch.setenv("USE_FLAX", "0")
    provider = EmbeddingProvider(Settings(data_dir=tmp_path, _env_file=None))
    assert provider._load() is model
    assert arguments["trust_remote_code"] is False
    assert arguments["model_kwargs"] == {"use_safetensors": True}
