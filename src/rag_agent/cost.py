"""Token estimates and API cost arithmetic, separate from local compute costs."""

from __future__ import annotations

from functools import lru_cache

import tiktoken

from rag_agent.config import PRICING


@lru_cache(maxsize=1)
def encoding() -> tiktoken.Encoding:
    """Reuse the tokenizer so estimates are inexpensive and deterministic."""
    return tiktoken.get_encoding("cl100k_base")


def token_count(text: str) -> int:
    """Count text tokens; chat framing/provider schemas are additional overhead."""
    return len(encoding().encode(text, disallowed_special=()))


def usage_cost(embedding: int, input_tokens: int, output_tokens: int, provider: str) -> float:
    """Estimate standard uncached API billing without claiming local compute is free."""
    if provider == "local":
        return 0.0
    return (
        embedding * PRICING["embedding"]
        + input_tokens * PRICING["input"]
        + output_tokens * PRICING["output"]
    ) / 1_000_000
