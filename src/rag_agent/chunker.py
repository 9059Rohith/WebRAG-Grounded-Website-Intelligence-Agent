"""Deterministic token-bounded section chunks with explicit source context."""

from __future__ import annotations

import hashlib
import re
from bisect import bisect_left

import tiktoken

from rag_agent.config import Settings
from rag_agent.schemas import Chunk, Page, Section


def _encode(encoder: tiktoken.Encoding, text: str) -> list[int]:
    # Website text is ordinary data even when it resembles tokenizer markers.
    return encoder.encode(text, disallowed_special=())


def _safe_prefix(encoder: tiktoken.Encoding, tokens: list[int], limit: int) -> str:
    while limit > 0:
        try:
            return encoder.decode_bytes(tokens[:limit]).decode("utf-8")
        except UnicodeDecodeError:
            limit -= 1
    return ""


def chunk_pages(pages: list[Page], settings: Settings) -> list[Chunk]:
    """Split at nearby paragraph/sentence boundaries and include overlap/context."""
    encoder = tiktoken.get_encoding("cl100k_base")
    chunks: list[Chunk] = []
    for page in pages:
        index = 0
        for section in page.sections or [Section(heading_path=page.title, text=page.text)]:
            title = page.title
            heading = section.heading_path
            context = f"{title}\n{heading}\n"
            context_tokens = _encode(encoder, context)
            # Untrusted giant headings cannot consume the complete chunk budget.
            if len(context_tokens) > settings.chunk_tokens // 3:
                context = (
                    _safe_prefix(encoder, context_tokens, settings.chunk_tokens // 3).strip() + "\n"
                )
            budget = settings.chunk_tokens - len(_encode(encoder, context)) - 2
            tokens = _encode(encoder, section.text)
            source_text, offsets = encoder.decode_with_offsets(tokens)
            offsets.append(len(source_text))
            overlap = min(settings.chunk_overlap_tokens, max(0, budget // 2))
            start = 0
            while start < len(tokens):
                # Token boundaries may fall inside UTF-8 characters. Move an
                # overlapping start forward and an end backward to safe points.
                while start > 0 and start < len(tokens) and offsets[start] == offsets[start - 1]:
                    start += 1
                if start >= len(tokens):
                    break
                end = min(start + budget, len(tokens))
                while end > start and end < len(tokens) and offsets[end] == offsets[end - 1]:
                    end -= 1
                raw_body = source_text[offsets[start] : offsets[end]]
                body = raw_body.strip()
                if end < len(tokens):
                    boundaries = list(re.finditer(r"\n\n|(?<=[.!?])\s+", raw_body))
                    if boundaries:
                        boundary = boundaries[-1].end()
                        if boundary >= len(raw_body) * 0.65:
                            end = bisect_left(
                                offsets, offsets[start] + boundary, lo=start + 1, hi=end + 1
                            )
                            body = source_text[offsets[start] : offsets[end]].strip()
                embedded = context + body
                while body and len(_encode(encoder, embedded)) > settings.chunk_tokens:
                    end -= 1
                    while end > start and end < len(tokens) and offsets[end] == offsets[end - 1]:
                        end -= 1
                    body = source_text[offsets[start] : offsets[end]].strip()
                    embedded = context + body
                if body and (
                    start > 0
                    or len(_encode(encoder, body)) >= settings.min_chunk_tokens
                    or len(tokens) < settings.min_chunk_tokens
                ):
                    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
                    identity = f"v1\0{page.url}\0{heading}\0{index}\0{body}"
                    chunks.append(
                        Chunk(
                            chunk_id=hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                            source_url=page.url,
                            title=title,
                            heading_path=heading,
                            text=body,
                            embedded_text=embedded,
                            token_count=len(_encode(encoder, embedded)),
                            content_hash=content_hash,
                            chunk_index=index,
                            crawled_at=page.crawled_at,
                        )
                    )
                    index += 1
                if end >= len(tokens):
                    break
                start = max(start + 1, end - overlap)
    return chunks
