"""Thread-safe TTL/LRU answer cache isolated by index version."""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from threading import RLock

from rag_agent.schemas import Answer


class QueryCache:
    """Keep detached answers so callers cannot mutate shared cached data."""

    def __init__(
        self,
        ttl_s: float = 3600,
        max_items: int = 512,
        *,
        version: str = "",
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_s < 0 or max_items < 1:
            raise ValueError("Cache TTL must be nonnegative and capacity must be positive")
        self.ttl_s = ttl_s
        self.max_items = max_items
        self.version = version
        self._clock = clock
        self._items: OrderedDict[tuple[str, str], tuple[float, Answer]] = OrderedDict()
        self._lock = RLock()

    def get(self, key: str) -> Answer | None:
        """Return a cache hit with zero new token use and zero new API cost."""
        versioned = (self.version, key)
        with self._lock:
            item = self._items.get(versioned)
            if item is None:
                return None
            expires, answer = item
            if expires <= self._clock():
                del self._items[versioned]
                return None
            self._items.move_to_end(versioned)
            result = answer.model_copy(deep=True)
        result.cached = True
        result.usage.embedding_tokens = 0
        result.usage.input_tokens = 0
        result.usage.output_tokens = 0
        result.usage.estimated_usd = 0
        return result

    def put(self, key: str, answer: Answer) -> None:
        """Store an answer under the current version, evicting least-recently used entries."""
        if self.ttl_s == 0:
            return
        versioned = (self.version, key)
        with self._lock:
            now = self._clock()
            expired = [item_key for item_key, item in self._items.items() if item[0] <= now]
            for item_key in expired:
                del self._items[item_key]
            self._items[versioned] = (now + self.ttl_s, answer.model_copy(deep=True))
            self._items.move_to_end(versioned)
            while len(self._items) > self.max_items:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            now = self._clock()
            return sum(expires > now for expires, _ in self._items.values())
