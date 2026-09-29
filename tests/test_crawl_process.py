"""Ingestion safety and deterministic processing contracts."""

from __future__ import annotations

import gzip
import json
import socket

import httpx
import pytest
import respx
import tiktoken

from rag_agent.chunker import chunk_pages
from rag_agent.cleaner import clean_html
from rag_agent.config import Settings
from rag_agent.crawler import crawl
from rag_agent.schemas import Page, Section
from rag_agent.ssrf import normalize_url, validate_url


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://example.test/space here",
        "https://example.test/\\path",
        "https://example.test:invalid/",
        "https://[broken/",
        "https://[fe80::1%25eth0]/",
        "https://example.test/%0a/path",
    ],
)
def test_invalid_url_syntax_fails_before_fetch(url: str) -> None:
    with pytest.raises(ValueError):
        normalize_url(url)


def test_dns_failure_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable(*args, **kwargs):
        raise socket.gaierror("unresolvable hostname")

    monkeypatch.setattr(socket, "getaddrinfo", unavailable)
    with pytest.raises(ValueError, match="DNS lookup failed"):
        validate_url("https://docs.python.org/3/", Settings())


def test_malformed_dns_address_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("invalid-address", 443))],
    )
    with pytest.raises(ValueError, match="public"):
        validate_url("https://docs.python.org/3/", Settings())


@pytest.fixture
def public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
    )


def test_normalize_url() -> None:
    assert (
        normalize_url("HTTPS://Example.COM:443/3/tutorial/../index.html#top")
        == "https://example.com/3/index.html"
    )


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://user:pass@docs.python.org/3/",
        "https://docs.python.org:444/3/",
        "http://127.0.0.1/3/",
        "http://[::1]/3/",
        "http://[::ffff:127.0.0.1]/3/",
        "http://169.254.169.254/3/",
        "http://224.0.0.1/3/",
        "http://[ff02::1]/3/",
        "https://docs.python.org.evil.test/3/",
        "https://docs.python.org/30/",
        "https://docs.python.org/3/%2e%2e/admin",
    ],
)
def test_unsafe_urls_rejected(url: str, public_dns: None) -> None:
    with pytest.raises(ValueError):
        validate_url(url, Settings())


def test_all_dns_answers_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fd00::1", 443, 0, 0)),
        ],
    )
    with pytest.raises(ValueError, match="public"):
        validate_url("https://docs.python.org/3/", Settings())


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://224.0.0.1/",
        "http://[ff02::1]/",
        "http://[2002:7f00:1::]/",
    ],
)
def test_unsafe_ip_rejected_without_scope_check(url: str) -> None:
    with pytest.raises(ValueError, match="public"):
        validate_url(url, Settings(), check_scope=False)


def test_programmatic_ipv6_fixture_allowed() -> None:
    settings = Settings(
        start_url="http://[::1]:8088/docs/",
        allowed_prefix="http://[::1]:8088/docs/",
        test_allow_localhost=True,
    )
    assert validate_url(settings.start_url, settings) == settings.start_url


def test_localhost_exception_is_scoped() -> None:
    settings = Settings(
        start_url="http://127.0.0.1:8088/docs/",
        allowed_prefix="http://127.0.0.1:8088/docs/",
        test_allow_localhost=True,
    )
    assert validate_url(settings.start_url, settings) == settings.start_url
    with pytest.raises(ValueError):
        validate_url("http://127.0.0.1:8088/private", settings)
    with pytest.raises(ValueError):
        validate_url("http://169.254.169.254:8088/docs/", settings, check_scope=False)


def test_localhost_exception_cannot_be_enabled_by_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setenv("TEST_ALLOW_LOCALHOST", "true")
    assert Settings().test_allow_localhost is False
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_ALLOW_LOCALHOST=true\n", encoding="utf-8")
    assert Settings(_env_file=env_file).test_allow_localhost is False
    assert Settings(test_allow_localhost=True).test_allow_localhost is True


def test_cleaner_extracts_content_and_heading_paths() -> None:
    html = """<html lang="en"><title>Example docs</title><body><nav>BOILERPLATE</nav>
    <main><h1>Lists<a class="headerlink">¶</a></h1><p>Lists store ordered values.</p>
    <h2>Append</h2><p>Use append to add one value.</p><pre>items.append(1)\nprint(items)</pre>
    <script>malicious()</script><footer>FOOTER</footer></main></body></html>"""
    page = clean_html(html, "https://example.test/docs")
    assert page is not None
    assert page.title == "Example docs"
    assert "BOILERPLATE" not in page.text and "malicious" not in page.text
    assert page.sections[-1].heading_path == "Lists > Append"
    assert "items.append(1)\nprint(items)" in page.text
    assert page.content_hash == clean_html(html, page.url).content_hash


def test_empty_and_non_english_pages_skipped() -> None:
    assert (
        clean_html("<html><script>x</script><nav>menu</nav></html>", "https://example.test/")
        is None
    )
    assert (
        clean_html(
            '<html lang="fr"><main><p>Une page française.</p></main></html>',
            "https://example.test/",
        )
        is None
    )


def test_chunks_are_bounded_stable_and_contextual() -> None:
    body = " ".join(f"value{i}" for i in range(400))
    page = Page(
        url="https://example.test/doc",
        title="Guide",
        text=body,
        sections=[Section(heading_path="Guide > Arrays", text=body)],
        content_hash="hash",
    )
    settings = Settings(chunk_tokens=80, chunk_overlap_tokens=15, min_chunk_tokens=10)
    chunks = chunk_pages([page], settings)
    enc = tiktoken.get_encoding("cl100k_base")
    assert len(chunks) > 1
    assert all(0 < c.token_count <= 80 for c in chunks)
    assert all(c.token_count == len(enc.encode(c.embedded_text)) for c in chunks)
    assert all(c.embedded_text.startswith("Guide\nGuide > Arrays\n") for c in chunks)
    assert [c.chunk_id for c in chunks] == [c.chunk_id for c in chunk_pages([page], settings)]
    assert (
        chunks[0].chunk_id
        != chunk_pages([page.model_copy(update={"url": page.url + "2"})], settings)[0].chunk_id
    )


def test_untrusted_special_tokens_and_unicode_preserved() -> None:
    text = "Literal <|endoftext|> example. " + "🙂漢字 " * 200
    page = Page(
        url="https://example.test/unicode",
        title="Guide",
        text=text,
        sections=[Section(heading_path="Unicode", text=text)],
        content_hash="hash",
    )
    chunks = chunk_pages([page], Settings(chunk_tokens=60, chunk_overlap_tokens=0))
    assert chunks and all("\ufffd" not in c.text and c.token_count <= 60 for c in chunks)
    assert "<|endoftext|>" in chunks[0].text
    assert "".join(c.text for c in chunks).replace(" ", "") == text.replace(" ", "")


@pytest.mark.asyncio
async def test_crawler_scope_robots_dedup_persistence_and_cache(tmp_path, public_dns: None) -> None:
    settings = Settings(
        start_url="https://example.test/docs/",
        allowed_prefix="https://example.test/docs/",
        data_dir=tmp_path,
        crawl_delay_s=0,
        max_pages=10,
    )
    with respx.mock(assert_all_called=False) as router:
        router.get("https://example.test/robots.txt").mock(
            return_value=httpx.Response(200, text="User-agent: *\nDisallow: /docs/private\n")
        )
        router.get(settings.start_url).mock(
            return_value=httpx.Response(
                200,
                text='<main><h1>Guide</h1><p>Useful opening content.</p><a href="a#one">A</a><a href="a#two">A again</a><a href="private">Hidden</a><a href="/other">Other</a></main>',
                headers={"content-type": "text/html"},
            )
        )
        router.get("https://example.test/docs/a").mock(
            return_value=httpx.Response(
                200,
                text="<main><h1>A</h1><p>Useful second page.</p></main>",
                headers={"content-type": "text/html"},
            )
        )
        pages, manifest = await crawl(settings)
        assert len(pages) == manifest["page_count"] == 2
        assert len(list((tmp_path / "raw").glob("*.html"))) == 2
        assert json.loads((tmp_path / "crawl_manifest.json").read_text())["page_count"] == 2
        cached_pages, cached_manifest = await crawl(settings)
        assert cached_pages == pages and cached_manifest["cached"] is True


@pytest.mark.asyncio
async def test_private_redirect_blocked_and_robots_failure_closed(
    tmp_path, public_dns: None
) -> None:
    settings = Settings(
        start_url="https://example.test/docs/",
        allowed_prefix="https://example.test/docs/",
        data_dir=tmp_path,
        crawl_delay_s=0,
    )
    with respx.mock(assert_all_called=False) as router:
        router.get("https://example.test/robots.txt").mock(return_value=httpx.Response(404))
        router.get(settings.start_url).mock(
            return_value=httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
        )
        pages, manifest = await crawl(settings)
        assert pages == [] and manifest["errors"]
    with respx.mock(assert_all_called=False) as router:
        router.get("https://example.test/robots.txt").mock(return_value=httpx.Response(503))
        pages, manifest = await crawl(settings, force=True)
        assert pages == [] and any("robots" in e["reason"] for e in manifest["errors"])


@pytest.mark.asyncio
async def test_response_size_limited(tmp_path, public_dns: None) -> None:
    settings = Settings(
        start_url="https://example.test/docs/",
        allowed_prefix="https://example.test/docs/",
        data_dir=tmp_path,
        crawl_delay_s=0,
        max_response_bytes=1024,
    )
    with respx.mock(assert_all_called=False) as router:
        router.get("https://example.test/robots.txt").mock(return_value=httpx.Response(404))
        router.get(settings.start_url).mock(
            return_value=httpx.Response(
                200, content=b"x" * 1100, headers={"content-type": "text/html"}
            )
        )
        pages, manifest = await crawl(settings)
        assert pages == [] and "size" in manifest["errors"][0]["reason"]


@pytest.mark.asyncio
async def test_dry_run_creates_no_artifacts(tmp_path, public_dns: None) -> None:
    settings = Settings(data_dir=tmp_path / "never_created")
    pages, manifest = await crawl(settings, dry_run=True)
    assert not pages and manifest["dry_run"] and not settings.data_dir.exists()


@pytest.mark.asyncio
async def test_compressed_html_is_decoded_once(tmp_path, public_dns: None) -> None:
    settings = Settings(
        start_url="https://example.test/docs/",
        allowed_prefix="https://example.test/docs/",
        data_dir=tmp_path,
        crawl_delay_s=0,
    )
    html = b"<main><h1>Compressed guide</h1><p>Readable compressed documentation.</p></main>"
    with respx.mock(assert_all_called=False) as router:
        router.get("https://example.test/robots.txt").mock(return_value=httpx.Response(404))
        router.get(settings.start_url).mock(
            return_value=httpx.Response(
                200,
                content=gzip.compress(html),
                headers={"content-type": "text/html", "content-encoding": "gzip"},
            )
        )
        pages, manifest = await crawl(settings)
        assert len(pages) == 1 and not manifest["errors"]
        assert "Readable compressed documentation." in pages[0].text
        assert next((tmp_path / "raw").glob("*.html")).read_bytes() == html
