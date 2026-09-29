"""Offline delivery-contract and cache boundary checks."""

from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from rag_agent.api import RateLimiter, create_app
from rag_agent.cache import QueryCache
from rag_agent.config import Settings
from rag_agent.schemas import Answer, Usage


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def ask(self, question: str, use_cache: bool = True) -> Answer:
        self.calls.append((question, use_cache))
        return Answer(answer="Grounded <script>plain text</script>", answerable=True)

    def stats(self) -> dict[str, Any]:
        return {"pages": 3, "chunks": 8}


def settings(**overrides: Any) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_cache_ttl_and_detached_zero_cost_hit() -> None:
    now = [10.0]
    cache = QueryCache(5, 2, version="index-a", clock=lambda: now[0])
    original = Answer(
        answer="evidence",
        answerable=True,
        usage=Usage(input_tokens=12, output_tokens=5, embedding_tokens=6, estimated_usd=0.2),
    )
    cache.put("question", original)
    original.answer = "changed"
    hit = cache.get("question")
    assert hit is not None
    assert hit.answer == "evidence" and hit.cached
    assert hit.usage.model_dump() == Usage().model_dump()
    hit.answer = "mutated hit"
    assert cache.get("question").answer == "evidence"  # type: ignore[union-attr]
    now[0] = 15.0
    assert cache.get("question") is None
    assert len(cache) == 0


def test_cache_lru_version_and_disabled_cache() -> None:
    cache = QueryCache(20, 2, version="v1")
    answer = Answer(answer="one", answerable=True)
    cache.put("a", answer)
    cache.put("b", answer)
    assert cache.get("a") is not None
    cache.put("c", answer)
    assert cache.get("b") is None
    cache.version = "v2"
    assert cache.get("a") is None
    cache.put("a", answer)
    assert cache.get("a") is not None
    cache.clear()
    assert len(cache) == 0
    disabled = QueryCache(0, 1)
    disabled.put("a", answer)
    assert disabled.get("a") is None


@pytest.mark.parametrize("ttl,capacity", [(-1, 1), (2, 0)])
def test_invalid_cache_configuration(ttl: float, capacity: int) -> None:
    with pytest.raises(ValueError):
        QueryCache(ttl, capacity)


def test_cache_discards_expired_entries_on_write() -> None:
    now = [0.0]
    cache = QueryCache(5, 2, clock=lambda: now[0])
    cache.put("expired", Answer(answer="old", answerable=True))
    now[0] = 6.0
    cache.put("new", Answer(answer="fresh", answerable=True))
    assert len(cache) == 1
    assert cache.get("expired") is None


def test_rate_limit_capacity_and_window_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [0.0]
    monkeypatch.setattr("rag_agent.api.time.monotonic", lambda: now[0])
    limiter = RateLimiter(limit=1, capacity=1)
    assert limiter.allow("first")
    assert not limiter.allow("first")
    assert not limiter.allow("second")
    now[0] = 60.0
    assert limiter.allow("second")


def test_api_injected_agent_contract_and_security_headers(tmp_path: Path) -> None:
    agent = FakeAgent()
    with TestClient(create_app(settings(), agent, static_dir=tmp_path)) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.get("/readyz").status_code == 200
        assert client.get("/stats").json() == {"pages": 3, "chunks": 8}
        assert client.get("/v1/stats").json() == {"pages": 3, "chunks": 8}
        response = client.post(
            "/v1/ask", json={"question": "  Python lists?  ", "use_cache": False}
        )
        assert response.status_code == 200
        assert response.json()["answer"] == "Grounded <script>plain text</script>"
        assert agent.calls == [("Python lists?", False)]
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["request_id"] == response.headers["x-request-id"]
        assert "access-control-allow-origin" not in response.headers
        page = client.get("/").text
        assert "output.textContent=" in page and "innerHTML" not in page


def test_api_auth_token_and_stats_protected() -> None:
    agent = FakeAgent()
    with TestClient(create_app(settings(api_token=SecretStr("test-secret")), agent)) as client:
        assert client.get("/healthz").status_code == 200
        response = client.post("/v1/ask", json={"question": "Python?"})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
        assert client.get("/stats").status_code == 401
        assert (
            client.post(
                "/v1/ask", json={"question": "Python?"}, headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/v1/ask",
                json={"question": "Python?"},
                headers={"Authorization": "Bearer test-secret"},
            ).status_code
            == 200
        )
        assert len(agent.calls) == 1


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": " "},
        {"question": "\u0000\u007f"},
        {"question": "too long"},
        {"question": "  a   "},
        {"question": "a", "extra": "field"},
        {"question": 123},
    ],
)
def test_api_question_validation_does_not_call_agent(body: dict[str, Any]) -> None:
    agent = FakeAgent()
    with TestClient(create_app(settings(max_question_chars=5), agent)) as client:
        response = client.post("/v1/ask", json=body)
        assert response.status_code == 422
        assert not agent.calls
        assert "input" not in response.text


def test_api_per_ip_rate_limit() -> None:
    with TestClient(create_app(settings(rate_limit_per_min=1), FakeAgent())) as client:
        assert client.post("/v1/ask", json={"question": "Python?"}).status_code == 200
        response = client.post(
            "/v1/ask", json={"question": "Python?"}, headers={"X-Forwarded-For": "spoofed-address"}
        )
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "rate_limited"
        assert response.headers["retry-after"] == "60"


def test_missing_index_is_live_but_unready(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(configuration: Settings) -> None:
        raise FileNotFoundError("private-path-that-must-not-leak")

    monkeypatch.setitem(sys.modules, "rag_agent.graph", SimpleNamespace(Agent=missing))
    with TestClient(create_app(settings())) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503
        assert client.get("/stats").status_code == 503
        response = client.post("/v1/ask", json={"question": "Python?"})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "not_ready"
        assert "private-path" not in response.text


def test_agent_initializes_off_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    initialization_threads: list[int] = []

    def load(configuration: Settings) -> FakeAgent:
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()
        initialization_threads.append(threading.get_ident())
        return FakeAgent()

    monkeypatch.setitem(sys.modules, "rag_agent.graph", SimpleNamespace(Agent=load))
    with TestClient(create_app(settings())) as client:
        assert client.get("/readyz").status_code == 200
        assert initialization_threads
        assert initialization_threads[0] != threading.get_ident()


def test_provider_error_does_not_leak_secrets() -> None:
    class BrokenAgent(FakeAgent):
        def ask(self, question: str, use_cache: bool = True) -> Answer:
            raise RuntimeError("secret-api-key private-provider-response")

    with TestClient(create_app(settings(), BrokenAgent())) as client:
        response = client.post("/v1/ask", json={"question": "Python?"})
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "provider_unavailable"
        assert "secret" not in response.text and "private" not in response.text


def test_stats_error_is_safe() -> None:
    class BrokenStats(FakeAgent):
        def stats(self) -> dict[str, Any]:
            raise RuntimeError("private-database-path")

    with TestClient(create_app(settings(), BrokenStats())) as client:
        response = client.get("/stats")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "stats_unavailable"
        assert "private" not in response.text


@pytest.mark.asyncio
async def test_timeout_holds_concurrency_slot_until_worker_finishes() -> None:
    gate = threading.Event()

    class SlowAgent(FakeAgent):
        def ask(self, question: str, use_cache: bool = True) -> Answer:
            gate.wait(timeout=2)
            return super().ask(question, use_cache)

    application = create_app(settings(api_timeout_s=0.05, max_concurrent_queries=1), SlowAgent())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test"
    ) as client:
        try:
            response = await client.post("/v1/ask", json={"question": "Python?"})
            assert response.status_code == 504
            assert response.json()["error"]["code"] == "query_timeout"
            busy = await client.post("/v1/ask", json={"question": "Python?"})
            assert busy.status_code == 503
            assert busy.json()["error"]["code"] == "busy"
        finally:
            gate.set()
        await asyncio.sleep(0.05)
        assert (await client.post("/v1/ask", json={"question": "Python?"})).status_code == 200


def test_cors_only_explicit_origins() -> None:
    with TestClient(
        create_app(settings(cors_origins=["https://trusted.example"]), FakeAgent())
    ) as client:
        assert (
            client.get("/healthz", headers={"Origin": "https://trusted.example"}).headers[
                "access-control-allow-origin"
            ]
            == "https://trusted.example"
        )
        response = client.get("/healthz", headers={"Origin": "https://other.example"})
        assert "access-control-allow-origin" not in response.headers
