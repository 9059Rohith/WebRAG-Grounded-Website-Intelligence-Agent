"""Extract English documentation text and ordered heading sections from HTML."""

from __future__ import annotations

import hashlib
import re
from typing import cast

from bs4 import BeautifulSoup, Tag

from rag_agent.schemas import Page, Section


def _text(tag: Tag) -> str:
    if tag.name == "pre":
        return tag.get_text().replace("\r\n", "\n").strip("\n")
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()


def clean_html(html: str, url: str, crawled_at: str = "") -> Page | None:
    """Drop menus/scripts, preserve code and produce semantically grouped text."""
    soup = BeautifulSoup(html, "lxml")
    lang_value = soup.html.get("lang", "en") if soup.html else "en"
    lang = str(lang_value or "en").lower()
    if not lang.startswith("en"):
        return None
    title = _text(soup.title) if soup.title else ""
    for node in soup.select(
        "script, style, noscript, nav, footer, aside, form, template, .headerlink, .sphinxsidebar, .related, .toc, .breadcrumb, .breadcrumbs, [aria-hidden='true']"
    ):
        node.decompose()
    root = cast(
        Tag,
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.select_one("div.body")
        or soup.body
        or soup,
    )
    headings: list[tuple[int, str]] = []
    sections: list[Section] = []
    parts: list[str] = []
    current_path = title
    captured: set[int] = set()

    def flush() -> None:
        nonlocal parts
        if parts:
            sections.append(
                Section(heading_path=current_path or title or "Document", text="\n\n".join(parts))
            )
            parts = []

    for element in root.descendants:
        if not isinstance(element, Tag):
            continue
        node = element
        if any(id(parent) in captured for parent in node.parents):
            continue
        if re.fullmatch(r"h[1-6]", node.name or ""):
            label = _text(node)
            if not label:
                continue
            flush()
            level = int(node.name[1])
            headings = [(depth, heading) for depth, heading in headings if depth < level]
            headings.append((level, label))
            current_path = " > ".join(heading for _, heading in headings)
            if not title:
                title = label
            captured.add(id(node))
        elif node.name in {"p", "pre", "li", "dt", "dd", "table", "blockquote"}:
            text = _text(node)
            if text:
                parts.append(text)
            captured.add(id(node))
    flush()
    if not sections:
        # Malformed/simple HTML often contains text directly in a content container.
        fallback = _text(root)
        if len(fallback) < 20:
            return None
        sections = [Section(heading_path=title or "Document", text=fallback)]
    text = "\n\n".join(section.text for section in sections)
    if len(text.strip()) < 10:
        return None
    return Page(
        url=url,
        title=title or "Document",
        text=text,
        sections=sections,
        content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        crawled_at=crawled_at,
        lang=lang,
    )
