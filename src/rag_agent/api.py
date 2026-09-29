"""Bounded HTTP delivery for the same grounded agent used by the CLI."""

from __future__ import annotations

import asyncio
import re
import secrets
import time
import uuid
from collections import OrderedDict, deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from rag_agent.config import Settings
from rag_agent.logging_setup import configure_logging
from rag_agent.schemas import Answer

logger = structlog.get_logger(__name__)


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=50_000)
    use_cache: bool = True


class RateLimiter:
    """Sliding one-minute windows; reject new IPs while the capacity is active."""

    def __init__(self, limit: int, capacity: int = 10_000) -> None:
        self.limit = limit
        self.capacity = capacity
        self.windows: OrderedDict[str, deque[float]] = OrderedDict()

    def allow(self, address: str) -> bool:
        now = time.monotonic()
        for key in list(self.windows):
            window = self.windows[key]
            while window and window[0] <= now - 60:
                window.popleft()
            if not window:
                del self.windows[key]
        if address not in self.windows:
            if len(self.windows) >= self.capacity:
                return False
            self.windows[address] = deque()
        window = self.windows[address]
        if len(window) >= self.limit:
            return False
        window.append(now)
        self.windows.move_to_end(address)
        return True


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


DEMO_HTML = """<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Website-grounded answers</title>
<style>
body{max-width:760px;margin:3rem auto;padding:0 1rem;background:#f7f7f4;color:#202923;font:17px system-ui}
h1{letter-spacing:-.04em}label{display:block;margin:1rem 0 .4rem}textarea,input{box-sizing:border-box;width:100%;padding:.8rem;border:1px solid #b6bdb7;border-radius:8px;font:inherit}
button{background:#176541;color:white;border:0;border-radius:8px;padding:.8rem 1.2rem;margin-top:1rem;font:inherit;cursor:pointer}
button:disabled{opacity:.5}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;border-radius:8px;padding:1.2rem;line-height:1.6}
small{color:#536058}
</style>
<h1>Ask the Python tutorial</h1><p>Answers grounded in the indexed website, with evidence and source links.</p>
<form id="form"><label for="question">Your question</label><textarea id="question" rows="3" maxlength="500" required placeholder="How do Python lists work?"></textarea>
<label for="token">API token (if configured)</label><input id="token" type="password" autocomplete="off">
<button id="submit">Ask</button></form><pre id="output" aria-live="polite">Ready for your question.</pre>
<small>Local mode quotes source passages. Source content is displayed as plain text.</small>
<script>
const form=document.getElementById('form'),output=document.getElementById('output'),button=document.getElementById('submit');
form.addEventListener('submit',async event=>{
event.preventDefault();button.disabled=true;output.textContent='Looking up evidence…';
const headers={'Content-Type':'application/json'},token=document.getElementById('token').value;
if(token)headers.Authorization='Bearer '+token;
try{const response=await fetch('/v1/ask',{method:'POST',headers,body:JSON.stringify({question:document.getElementById('question').value})});
const data=await response.json();
if(!response.ok)throw new Error(data.error?.message||'Request failed.');
output.textContent=data.answer+'\\n\\n'+data.sources.map(source=>source.title+'\\n'+source.url+'\\n'+source.evidence).join('\\n\\n')+'\\n\\nEstimated new cost: $'+data.usage.estimated_usd.toFixed(6)+(data.cached?' (cached)':'');
}catch(error){output.textContent=error.message||'Unable to connect.';}finally{button.disabled=false;}
});
</script></html>"""


def create_app(
    settings: Settings | None = None,
    agent: Any = None,
    *,
    static_dir: Path | None = None,
) -> FastAPI:
    """Construct an application; initialization occurs off the event loop at startup."""
    configuration = settings or Settings()
    ui_directory = static_dir or Path.cwd() / "web" / "dist"
    ui_index = ui_directory / "index.html"

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_logging()
        if application.state.agent is None:
            try:
                from rag_agent.graph import Agent

                application.state.agent = await asyncio.to_thread(Agent, configuration)
            except Exception as exc:
                logger.warning("agent_load_failed", error_type=type(exc).__name__)
        yield

    application = FastAPI(title="Website Grounded Agent", version="1.0.0", lifespan=lifespan)
    application.state.agent = agent
    application.state.limiter = RateLimiter(configuration.rate_limit_per_min)
    application.state.semaphore = asyncio.Semaphore(configuration.max_concurrent_queries)
    application.state.settings = configuration
    if configuration.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=configuration.cors_origins,
            allow_methods=["POST", "GET"],
            allow_headers=["Authorization", "Content-Type"],
            allow_credentials=False,
        )

    @application.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
        detail = (
            exc.detail
            if isinstance(exc.detail, dict)
            else {"code": "request_failed", "message": "Request failed."}
        )
        return JSONResponse({"error": detail}, status_code=exc.status_code, headers=exc.headers)

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            {
                "error": {
                    "code": "invalid_request",
                    "message": "Supply a valid question and use_cache flag.",
                }
            },
            status_code=422,
        )

    @application.middleware("http")
    async def secure_response(request: Request, call_next: Any) -> Any:
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.error("http_failed", request_id=request_id, error_type=type(exc).__name__)
            response = JSONResponse(
                {
                    "error": {
                        "code": "internal_error",
                        "message": "The request could not be completed.",
                    }
                },
                status_code=500,
            )
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    def authorize(request: Request) -> None:
        token = configuration.api_token
        if token:
            supplied = request.headers.get("authorization", "")
            expected = "Bearer " + token.get_secret_value()
            if not secrets.compare_digest(supplied.encode(), expected.encode()):
                raise _error(401, "unauthorized", "A valid bearer token is required.")

    @application.get("/", response_class=HTMLResponse)
    async def demo() -> Any:
        if ui_index.is_file():
            return FileResponse(ui_index, media_type="text/html")
        return DEMO_HTML

    @application.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/readyz")
    async def ready() -> dict[str, str]:
        if application.state.agent is None:
            raise _error(503, "not_ready", "Ingest a website before querying.")
        return {"status": "ready"}

    @application.get("/stats")
    @application.get("/v1/stats")
    async def stats(request: Request) -> dict[str, Any]:
        authorize(request)
        current = application.state.agent
        if current is None:
            raise _error(503, "not_ready", "Ingest a website before querying.")
        try:
            return dict(await asyncio.to_thread(current.stats))
        except Exception as exc:
            logger.warning("stats_failed", error_type=type(exc).__name__)
            raise _error(
                503, "stats_unavailable", "Index statistics are temporarily unavailable."
            ) from None

    @application.post("/v1/ask", response_model=Answer)
    async def ask(body: AskRequest, request: Request) -> Answer:
        authorize(request)
        question = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", body.question).split())
        if not question or len(body.question) > configuration.max_question_chars:
            raise _error(
                422,
                "invalid_question",
                f"Question must contain 1–{configuration.max_question_chars} characters.",
            )
        address = request.client.host if request.client else "unknown"
        if not application.state.limiter.allow(address):
            raise HTTPException(
                429,
                detail={
                    "code": "rate_limited",
                    "message": "Too many requests; retry in one minute.",
                },
                headers={"Retry-After": "60"},
            )
        current = application.state.agent
        if current is None:
            raise _error(503, "not_ready", "Ingest a website before querying.")
        semaphore = application.state.semaphore
        started = time.monotonic()
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=configuration.api_timeout_s)
        except TimeoutError:
            raise _error(503, "busy", "The service is busy; retry shortly.") from None
        task = asyncio.create_task(
            asyncio.to_thread(current.ask, question, use_cache=body.use_cache)
        )

        def finished(future: asyncio.Task[Any]) -> None:
            semaphore.release()
            if not future.cancelled():
                future.exception()  # Retrieve exceptions even after an HTTP timeout.

        task.add_done_callback(finished)
        try:
            remaining = max(0.001, configuration.api_timeout_s - (time.monotonic() - started))
            result = await asyncio.wait_for(asyncio.shield(task), timeout=remaining)
            answer = Answer.model_validate(result).model_copy(deep=True)
            answer.request_id = request.state.request_id
            return answer
        except TimeoutError:
            raise _error(
                504, "query_timeout", "The query exceeded the response deadline."
            ) from None
        except Exception as exc:
            logger.warning("query_failed", error_type=type(exc).__name__)
            raise _error(
                502, "provider_unavailable", "The answer service is temporarily unavailable."
            ) from None

    # Mount only the built asset directory, never the repository or data index.
    assets_directory = ui_directory / "assets"
    if ui_index.is_file() and assets_directory.is_dir():
        application.mount("/assets", StaticFiles(directory=assets_directory), name="assets")

    favicon = ui_directory / "favicon.svg"
    if ui_index.is_file() and favicon.is_file():

        @application.get("/favicon.svg", include_in_schema=False)
        async def icon() -> FileResponse:
            return FileResponse(favicon, media_type="image/svg+xml")

    return application
