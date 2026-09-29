"""Fail-closed citation checks; quote occurrence does not prove semantic entailment."""

from __future__ import annotations

import re

from rag_agent.schemas import Citation, Draft, Hit

REFUSAL = "I couldn't find enough information on the selected website to answer this question."
INJECTION_PATTERN = re.compile(
    r"ignore\s+(?:all\s+)?(?:previous|prior|above|system)\s+instructions|\bpwned\b|reveal\s+(?:your\s+)?(?:system\s+prompt|api\s+key)|act\s+as\s+(?:a\s+)?system|disregard\s+(?:all|the|previous)\s+(?:instructions|rules)",
    re.IGNORECASE,
)


def normalize_evidence(text: str) -> str:
    """Normalize layout whitespace while preserving quoted literal values and case."""
    pieces = re.split(r"""("[^"\n]*"|'[^'\n]*')""", text)
    return "".join(
        piece if index % 2 else re.sub(r"\s+", " ", piece) for index, piece in enumerate(pieces)
    ).strip()


def evidence_occurs(evidence: str, text: str) -> bool:
    """A source quote cannot begin inside an identifier such as 'immutable'."""
    quote = normalize_evidence(evidence)
    if not quote:
        return False
    start = r"(?<!\w)" if re.match(r"\w", quote[0]) else ""
    end = r"(?!\w)" if re.match(r"\w", quote[-1]) else ""
    return bool(re.search(start + re.escape(quote) + end, normalize_evidence(text)))


def canonicalize_draft_evidence(draft: Draft, hits: list[Hit]) -> Draft:
    """Restore source formatting; never repair words, case, or literal characters.

    HTML inline spans can introduce spaces before punctuation. Models often omit
    those spaces. Resolve such a quote back to actual source characters before
    both deterministic verification and the semantic check.
    """
    result = draft.model_copy(deep=True)
    chunks = {hit.chunk.chunk_id: hit.chunk for hit in hits}
    for claim in result.claims:
        chunk = chunks.get(claim.chunk_id)
        if chunk is None or evidence_occurs(claim.evidence, chunk.text):
            continue
        quote = normalize_evidence(claim.evidence)
        if not quote or not 4 <= len(quote.split()) <= 60:
            continue
        pattern = ""
        literal_delimiter = ""
        for index, character in enumerate(quote):
            was_literal = bool(literal_delimiter)
            if character in {"'", '"'} and (not index or quote[index - 1] != "\\"):
                if character == literal_delimiter:
                    literal_delimiter = ""
                elif not literal_delimiter:
                    literal_delimiter = character
            if character.isspace():
                previous = quote[index - 1] if index else ""
                following = quote[index + 1] if index + 1 < len(quote) else ""
                if was_literal:
                    pattern += re.escape(character)
                else:
                    previous_word = previous.isalnum() or previous == "_"
                    following_word = following.isalnum() or following == "_"
                    pattern += r"\s+" if previous_word and following_word else r"\s*"
            else:
                pattern += re.escape(character)
                if index + 1 < len(quote):
                    following = quote[index + 1]
                    if (
                        not was_literal
                        and not literal_delimiter
                        and not following.isspace()
                        and (
                            not (character.isalnum() or character == "_")
                            or not (following.isalnum() or following == "_")
                        )
                    ):
                        pattern += r"\s*"
        start = r"(?<!\w)" if re.match(r"\w", quote[0]) else ""
        end = r"(?!\w)" if re.match(r"\w", quote[-1]) else ""
        match = re.search(start + pattern + end, chunk.text)
        if match:
            claim.evidence = match.group(0)
    return result


def resolve_quote_references(draft: Draft, quotes: dict[str, tuple[str, str]]) -> Draft:
    """Bind a selected reference to its source; unknown or mismatched IDs stay invalid."""
    result = draft.model_copy(deep=True)
    for claim in result.claims:
        reference = quotes.get(claim.evidence)
        if reference and claim.chunk_id == reference[0]:
            claim.evidence = reference[1]
    return result


def verify_draft(draft: Draft, hits: list[Hit]) -> tuple[bool, list[Citation]]:
    """Reject the whole answer if any claimed source or evidence is invalid."""
    if not draft.answerable or not draft.claims:
        return False, []
    chunks = {hit.chunk.chunk_id: hit.chunk for hit in hits}
    citations: list[Citation] = []
    for claim in draft.claims:
        chunk = chunks.get(claim.chunk_id)
        quote = normalize_evidence(claim.evidence)
        if chunk is None or not 4 <= len(quote.split()) <= 60 or not claim.text.strip():
            return False, []
        if not evidence_occurs(claim.evidence, chunk.text) or INJECTION_PATTERN.search(
            claim.evidence
        ):
            return False, []
        citations.append(
            Citation(
                url=chunk.source_url,
                title=chunk.title,
                evidence=claim.evidence,
                chunk_id=chunk.chunk_id,
            )
        )
    return True, citations
