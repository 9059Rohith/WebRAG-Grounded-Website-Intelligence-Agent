"""Ingestion composes crawl, chunk, embed and snapshot publication."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

from rag_agent.chunker import chunk_pages
from rag_agent.config import Settings
from rag_agent.crawler import crawl
from rag_agent.embeddings import EmbeddingProvider
from rag_agent.vectorstore import VectorStore


async def ingest(settings: Settings, force: bool = False, dry_run: bool = False) -> dict[str, Any]:
    """Preserve the existing index unless a usable new corpus is available."""
    import asyncio

    start = time.perf_counter()
    pages, crawl_report = await crawl(settings, force=force, dry_run=dry_run)
    if dry_run:
        return crawl_report
    if not pages:
        raise ValueError("No usable pages were crawled; previous index preserved")
    chunks = chunk_pages(pages, settings)
    if not chunks:
        raise ValueError("No usable chunks; previous index preserved")
    store = VectorStore(settings, create=True)
    # A bounded crawl is not evidence that uncrawled old pages disappeared.
    # Retain old pages absent from this successful subset. Full deletion would
    # require an authoritative complete sitemap plus confirmed 404/410 results.
    crawled_urls = {p.url for p in pages}
    chunks.extend(c for c in store.chunks if c.source_url not in crawled_urls)
    embeddings = EmbeddingProvider(settings)
    vectors, usage = await asyncio.to_thread(
        embeddings.embed_with_usage, [c.embedded_text for c in chunks]
    )
    info = {
        "pages": len({c.source_url for c in chunks}),
        "start_url": settings.start_url,
        "allowed_prefix": settings.allowed_prefix,
        "provider": settings.provider,
        "chunk_tokens": settings.chunk_tokens,
        "chunk_overlap_tokens": settings.chunk_overlap_tokens,
        "created_at": datetime.now(UTC).isoformat(),
    }
    diff = store.replace(chunks, vectors, info)
    report = {
        **info,
        "chunks": len(chunks),
        "crawl": crawl_report,
        "usage": usage.model_dump(),
        "embedding_cache_hits": embeddings.last_cache_hits,
        "diff": diff,
        "elapsed_seconds": time.perf_counter() - start,
    }
    (settings.data_dir / "ingest_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report
