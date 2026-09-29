"""Polite, bounded BFS crawler with DNS pinning and reproducible raw artifacts."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import ssl
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpcore
import httpx
from bs4 import BeautifulSoup, Tag

from rag_agent.cleaner import clean_html
from rag_agent.config import Settings
from rag_agent.schemas import Page
from rag_agent.ssrf import normalize_url, resolve_public_addresses, validate_url

logger = logging.getLogger(__name__)


class _PublicNetworkBackend(httpcore.AsyncNetworkBackend):
    """Resolve/validate once at connection time, then connect directly to that IP.

    TLS SNI and HTTP Host remain the original hostname in httpcore. This closes
    the DNS validation-to-connection rebinding gap without weakening TLS checks.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.backend = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any = None,
    ) -> httpcore.AsyncNetworkStream:
        addresses = await asyncio.to_thread(resolve_public_addresses, host, port, self.settings)
        last_error: Exception | None = None
        for address in addresses:
            try:
                return await self.backend.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (OSError, httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        raise httpcore.ConnectError("Public-address connection failed") from last_error

    async def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options: Any = None
    ) -> httpcore.AsyncNetworkStream:
        raise httpcore.ConnectError("Unix socket connections are forbidden")

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class _PublicTransport(httpx.AsyncHTTPTransport):
    def __init__(self, settings: Settings) -> None:
        super().__init__(trust_env=False)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            max_connections=1,
            max_keepalive_connections=1,
            network_backend=_PublicNetworkBackend(settings),
        )


def _atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _cache_key(settings: Settings) -> str:
    values = {
        key: getattr(settings, key)
        for key in (
            "start_url",
            "allowed_prefix",
            "max_pages",
            "max_depth",
            "max_response_bytes",
            "user_agent",
        )
    }
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


async def _fetch(
    client: httpx.AsyncClient,
    url: str,
    settings: Settings,
    *,
    robots: RobotFileParser | None = None,
    check_scope: bool = True,
    polite_delay: float = 0,
) -> tuple[int, str, dict[str, str], bytes]:
    current = url
    for redirect_index in range(6):
        if redirect_index:
            await asyncio.sleep(max(settings.crawl_delay_s, polite_delay))
        current = await asyncio.to_thread(validate_url, current, settings, check_scope)
        if robots is not None and not robots.can_fetch(settings.user_agent, current):
            raise ValueError("robots.txt disallows redirected URL")
        for attempt in range(3):
            try:
                async with client.stream("GET", current) as response:
                    headers = dict(response.headers)
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                        try:
                            retry_delay = min(
                                10.0, max(0.5, float(headers.get("retry-after", 2**attempt)))
                            )
                        except ValueError:
                            retry_delay = float(2**attempt)
                        await asyncio.sleep(max(settings.crawl_delay_s, retry_delay))
                        continue
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = headers.get("location")
                        if not location:
                            raise ValueError("Redirect lacks location")
                        candidate = urljoin(current, location)
                        if not check_scope and urlsplit(candidate).netloc != urlsplit(url).netloc:
                            raise ValueError("robots.txt redirect leaves original origin")
                        current = candidate
                        break
                    try:
                        declared_size = int(headers.get("content-length", "0"))
                    except ValueError as exc:
                        raise ValueError("Invalid response size declaration") from exc
                    if declared_size > settings.max_response_bytes:
                        raise ValueError("Response exceeds configured size limit")
                    body = bytearray()
                    async for block in response.aiter_bytes():
                        body.extend(block)
                        if len(body) > settings.max_response_bytes:
                            raise ValueError("Response exceeds configured size limit")
                    return response.status_code, current, headers, bytes(body)
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 2:
                    raise
                await asyncio.sleep(max(settings.crawl_delay_s, 0.5 * 2**attempt))
        else:
            raise ValueError("Request retry limit exceeded")
    raise ValueError("Redirect limit exceeded")


async def crawl(
    settings: Settings, force: bool = False, dry_run: bool = False
) -> tuple[list[Page], dict[str, Any]]:
    """Crawl English pages sequentially; save raw content and a detailed manifest.

    Cache reuse requires an identical crawl configuration and a nonempty corpus.
    A failed recrawl leaves any previously saved corpus intact for recovery.
    """
    start = await asyncio.to_thread(validate_url, settings.start_url, settings)
    started = time.perf_counter()
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "start_url": start,
        "allowed_prefix": normalize_url(settings.allowed_prefix),
        "cache_key": _cache_key(settings),
        "started_at": datetime.now(UTC).isoformat(),
        "page_count": 0,
        "attempted_count": 0,
        "fetched": [],
        "errors": [],
        "skipped": [],
        "cached": False,
        "dry_run": dry_run,
        "crawl_strategy": "sequential_bfs",
    }
    if dry_run:
        return [], manifest
    pages_path = settings.data_dir / "pages.json"
    manifest_path = settings.data_dir / "crawl_manifest.json"
    if not force and pages_path.exists() and manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            pages = [
                Page.model_validate(row)
                for row in json.loads(pages_path.read_text(encoding="utf-8"))
            ]
            if existing.get("cache_key") == manifest["cache_key"] and pages:
                existing["cached"] = True
                return pages, existing
        except (ValueError, OSError, TypeError, KeyError):
            logger.warning("Crawl cache invalid; fetching a fresh corpus")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = settings.data_dir / "raw"
    raw_dir.mkdir(exist_ok=True)
    pages = []
    queue = deque([(start, 0)])
    seen = {start}
    hashes: set[str] = set()
    downloaded: set[str] = set()
    async with httpx.AsyncClient(
        transport=_PublicTransport(settings),
        timeout=settings.request_timeout_s,
        follow_redirects=False,
        trust_env=False,
        headers={
            "User-Agent": settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8",
        },
    ) as client:
        robots_url = urljoin(start, "/robots.txt")
        robots = RobotFileParser(robots_url)
        try:
            status, final_url, _, body = await _fetch(
                client, robots_url, settings, check_scope=False
            )
            manifest["robots"] = {
                "url": final_url,
                "status": status,
                "checked_at": datetime.now(UTC).isoformat(),
            }
            if status in {404, 410}:
                robots.parse([])
            elif status == 200:
                robots.parse(body.decode("utf-8", errors="replace").splitlines())
            else:
                raise ValueError(f"robots.txt unavailable (HTTP {status}); crawl denied")
        except (ValueError, httpx.HTTPError, OSError) as exc:
            manifest["errors"].append({"url": robots_url, "reason": f"robots.txt failure: {exc}"})
            queue.clear()
        rate = robots.request_rate(settings.user_agent) or robots.request_rate("*")
        rate_delay = rate.seconds / rate.requests if rate and rate.requests > 0 else 0
        delay = max(
            settings.crawl_delay_s,
            float(robots.crawl_delay(settings.user_agent) or robots.crawl_delay("*") or 0),
            rate_delay,
        )
        manifest["effective_delay_s"] = delay
        last_request = time.monotonic()
        while queue and len(pages) < settings.max_pages:
            url, depth = queue.popleft()
            if url in downloaded:
                continue
            if not robots.can_fetch(settings.user_agent, url):
                manifest["skipped"].append({"url": url, "reason": "robots.txt disallows URL"})
                continue
            await asyncio.sleep(max(0, delay - (time.monotonic() - last_request)))
            manifest["attempted_count"] += 1
            try:
                status, final_url, headers, raw = await _fetch(
                    client, url, settings, robots=robots, polite_delay=delay
                )
                last_request = time.monotonic()
                downloaded.add(final_url)
                if status != 200:
                    raise ValueError(f"HTTP {status}")
                if (
                    "text/html" not in headers.get("content-type", "").lower()
                    and "application/xhtml+xml" not in headers.get("content-type", "").lower()
                ):
                    manifest["skipped"].append(
                        {"url": final_url, "reason": "Non-HTML content type"}
                    )
                    continue
                # aiter_bytes already decompresses the stream. Preserve charset
                # metadata without applying Content-Encoding for a second time.
                text_headers = {
                    key: value
                    for key, value in headers.items()
                    if key not in {"content-encoding", "content-length"}
                }
                response = httpx.Response(status, headers=text_headers, content=raw)
                html = response.text
                fetched_at = datetime.now(UTC).isoformat()
                raw_name = hashlib.sha256(final_url.encode()).hexdigest() + ".html"
                (raw_dir / raw_name).write_bytes(raw)
                page = clean_html(html, final_url, fetched_at)
                manifest["fetched"].append(
                    {
                        "url": final_url,
                        "requested_url": url,
                        "depth": depth,
                        "raw_path": f"raw/{raw_name}",
                        "bytes": len(raw),
                        "status": status,
                        "crawled_at": fetched_at,
                        "content_hash": page.content_hash if page else None,
                    }
                )
                if page is None:
                    manifest["skipped"].append(
                        {"url": final_url, "reason": "Empty or non-English main content"}
                    )
                elif page.content_hash in hashes:
                    manifest["skipped"].append(
                        {"url": final_url, "reason": "Duplicate page content"}
                    )
                else:
                    pages.append(page)
                    hashes.add(page.content_hash)
                    logger.info("Crawled page %d/%d: %s", len(pages), settings.max_pages, final_url)
                if depth >= settings.max_depth:
                    continue
                link_soup = BeautifulSoup(html, "lxml")
                link_root = cast(
                    Tag,
                    link_soup.find("main")
                    or link_soup.find("article")
                    or link_soup.find(attrs={"role": "main"})
                    or link_soup.select_one("div.body")
                    or link_soup,
                )
                # Content links prioritize documentation over repeated site menus.
                for anchor in link_root.find_all("a", href=True):
                    href = str(anchor["href"])
                    if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
                        continue
                    try:
                        # Full DNS validation occurs before requesting. Checking the
                        # normalized scope here avoids resolving every menu link.
                        candidate = normalize_url(urljoin(final_url, href))
                        parsed = urlsplit(candidate)
                        prefix = urlsplit(manifest["allowed_prefix"])
                        base_path = prefix.path.rstrip("/")
                        if (parsed.scheme, parsed.netloc) != (prefix.scheme, prefix.netloc) or not (
                            parsed.path == base_path or parsed.path.startswith(base_path + "/")
                        ):
                            continue
                        if parsed.query or Path(parsed.path).suffix.lower() in {
                            ".pdf",
                            ".zip",
                            ".png",
                            ".jpg",
                            ".jpeg",
                            ".gif",
                            ".svg",
                            ".css",
                            ".js",
                            ".txt",
                            ".gz",
                            ".xml",
                        }:
                            continue
                        name = Path(parsed.path).name.lower()
                        if name.startswith("genindex") or name in {
                            "py-modindex.html",
                            "search.html",
                            "improve-page-nojs.html",
                        }:
                            continue
                    except ValueError:
                        continue
                    if candidate not in seen:
                        seen.add(candidate)
                        queue.append((candidate, depth + 1))
            except (ValueError, httpx.HTTPError, OSError) as exc:
                last_request = time.monotonic()
                manifest["errors"].append({"url": url, "reason": str(exc)})
                logger.warning("Skipping crawl URL %s: %s", url, exc)
    manifest["page_count"] = len(pages)
    manifest["finished_at"] = datetime.now(UTC).isoformat()
    manifest["elapsed_s"] = round(time.perf_counter() - started, 3)
    manifest["queued_remaining"] = len(queue)
    if pages:
        _atomic_json(pages_path, [page.model_dump(mode="json") for page in pages])
        _atomic_json(manifest_path, manifest)
    elif not pages_path.exists():
        _atomic_json(manifest_path, manifest)
    else:
        _atomic_json(settings.data_dir / "crawl_failed_manifest.json", manifest)
    return pages, manifest
