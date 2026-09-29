"""Provider adapters and complete fixture ingestion without external API calls."""

from __future__ import annotations

import asyncio
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from pydantic import SecretStr
from tests_support import build_test_store

from rag_agent.config import Settings
from rag_agent.embeddings import EmbeddingProvider
from rag_agent.errors import LLMError
from rag_agent.graph import Agent
from rag_agent.ingest import ingest
from rag_agent.schemas import Claim, Draft, Page, Section, Usage


class FakeEmbeddingModel:
    tokenizer = SimpleNamespace(
        encode=lambda text, add_special_tokens=False: list(range(len(text.split()))),
        decode=lambda ids: "text " * len(ids),
    )

    def encode(self, texts: list[str], **kwargs: Any) -> Any:
        return np.array([[1.0, 0.0, 0.0] for _ in texts])

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_local_embedding_cache_and_large_text(tmp_path: Path) -> None:
    embeddings = EmbeddingProvider(Settings(data_dir=tmp_path, _env_file=None))
    embeddings._model = FakeEmbeddingModel()
    vectors, usage = embeddings.embed_with_usage(["hello website", "long text " * 250])
    assert vectors == [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]] and usage.embedding_tokens > 0
    assert usage.estimated_usd == 0 and embeddings.last_cache_hits == 0
    cached, usage = embeddings.embed_with_usage(["hello website", "long text " * 250])
    assert cached == vectors and usage.embedding_tokens == 0 and embeddings.last_cache_hits == 2
    assert embeddings.embed([]) == []


def test_openai_embedding_accounting_without_api(tmp_path: Path) -> None:
    settings = Settings(
        provider="openai",
        openai_api_key=SecretStr("unit-test-placeholder"),
        data_dir=tmp_path,
        _env_file=None,
    )
    embeddings = EmbeddingProvider(settings)
    embeddings._model = FakeEmbeddingModel()
    _, usage = embeddings.embed_with_usage(["website embedding test"])
    assert usage.estimated_usd > 0 and usage.provider == "openai"


class FakeProvider:
    last_cache_hits = 0

    def __init__(self, settings: Settings) -> None:
        pass

    def embed_with_usage(self, texts: list[str]) -> tuple[list[list[float]], Usage]:
        return [[1.0, 0.0, 0.0] for _ in texts], Usage(embedding_tokens=7)


def test_full_http_fixture_ingest_then_grounded_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    site = tmp_path / "site"
    site.mkdir()
    text = (
        "Lists are mutable sequences that allow adding and removing items. "
        + "A list supports append and pop operations to change its content. " * 8
    )
    (site / "index.html").write_text(
        "<html><main><h1>Lists</h1><p>"
        + text
        + '</p><a href="/tuples.html">Tuples</a></main></html>',
        encoding="utf-8",
    )
    (site / "tuples.html").write_text(
        "<html><main><h1>Tuples</h1><p>Tuples are immutable sequences and cannot change their items. "
        + "A tuple groups values in an immutable sequence. " * 10
        + "</p></main></html>",
        encoding="utf-8",
    )
    (site / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(site))
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/"
        settings = Settings(
            data_dir=tmp_path / "index",
            start_url=url + "index.html",
            allowed_prefix=url,
            test_allow_localhost=True,
            crawl_delay_s=0,
            max_pages=2,
            _env_file=None,
        )
        monkeypatch.setattr("rag_agent.ingest.EmbeddingProvider", FakeProvider)
        report = asyncio.run(ingest(settings))
        assert report["pages"] == 2 and report["chunks"] >= 2
        agent = Agent(settings, embeddings=FakeProvider(settings))  # type: ignore[arg-type]
        answer = agent.ask("Are lists mutable?")
        assert answer.answerable
        assert all(c.url.startswith(url) for c in answer.sources)
        assert all(c.evidence in agent.store.by_id[c.chunk_id].text for c in answer.sources)
        again = asyncio.run(ingest(settings))
        assert again["diff"]["unchanged"] == report["chunks"]
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_ingest_dry_run_and_empty_preserves_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(data_dir=tmp_path, _env_file=None)

    async def empty(settings: Settings, force: bool = False, dry_run: bool = False) -> Any:
        return [], {"dry_run": dry_run}

    monkeypatch.setattr("rag_agent.ingest.crawl", empty)
    assert asyncio.run(ingest(settings, dry_run=True)) == {"dry_run": True}
    with pytest.raises(ValueError, match="previous index preserved"):
        asyncio.run(ingest(settings))
    page = Page(
        url="https://example.com/",
        title="Thin",
        text="",
        sections=[Section(heading_path="", text="")],
        content_hash="empty",
    )

    async def thin(settings: Settings, force: bool = False, dry_run: bool = False) -> Any:
        return [page], {}

    monkeypatch.setattr("rag_agent.ingest.crawl", thin)
    with pytest.raises(ValueError, match="No usable chunks"):
        asyncio.run(ingest(settings))


class ScriptedLLM:
    def __init__(self, mode: str = "success") -> None:
        self.mode = mode
        self.calls = 0

    def with_structured_output(self, schema: Any, include_raw: bool = True) -> Any:
        parent = self

        def invoke(messages: Any) -> dict[str, Any]:
            parent.calls += 1
            if parent.mode == "error":
                raise RuntimeError("private provider internals")
            parsed = (
                Draft(
                    answerable=True,
                    claims=[
                        Claim(
                            text="Lists are mutable sequences.",
                            chunk_id="test",
                            evidence="Lists are mutable sequences.",
                        )
                    ],
                )
                if schema is Draft
                else schema(
                    explanation="Fixture evidence assessment.",
                    supported=parent.mode != "unsupported",
                )
            )
            if parent.mode == "invalid":
                parsed = None
            return {
                "parsed": parsed,
                "raw": SimpleNamespace(usage_metadata={"input_tokens": 20, "output_tokens": 10}),
            }

        return SimpleNamespace(invoke=invoke)


def paid_agent(tmp_path: Path, mode: str = "success") -> Agent:
    settings = Settings(
        data_dir=tmp_path,
        provider="openai",
        openai_api_key=SecretStr("unit-test-placeholder"),
        _env_file=None,
    )
    store = build_test_store(settings)
    agent = Agent(settings, store=store, embeddings=FakeProvider(settings))  # type: ignore[arg-type]
    agent._llm = ScriptedLLM(mode)
    return agent


def test_paid_graph_usage_and_self_check_are_accumulated(tmp_path: Path) -> None:
    agent = paid_agent(tmp_path)
    answer = agent.ask("Are lists mutable?")
    assert answer.answerable and answer.mode == "llm"
    assert answer.usage.input_tokens == 40 and answer.usage.output_tokens == 20
    assert answer.usage.estimated_usd > 0 and answer.usage.token_source == "api_reported"


@pytest.mark.parametrize("mode", ["invalid", "error"])
def test_paid_graph_provider_failures_safe(tmp_path: Path, mode: str) -> None:
    agent = paid_agent(tmp_path, mode)
    with pytest.raises(LLMError):
        agent.ask("Are lists mutable?")


def test_paid_graph_unsupported_claims_refuse(tmp_path: Path) -> None:
    agent = paid_agent(tmp_path, "unsupported")
    answer = agent.ask("Are lists mutable?")
    assert not answer.answerable and answer.attempts == 2
    assert answer.usage.input_tokens == 80 and answer.usage.output_tokens == 40
