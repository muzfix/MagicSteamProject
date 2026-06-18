"""
Thread-safe TTL + LRU in-process search cache.

Zero external dependencies — pure Python stdlib (threading, hashlib, json, time,
collections).  One global instance (search_cache) is shared across all requests
within a single process.  With multiple Gunicorn workers each worker has its own
cache; that is fine and expected — no coordination needed for a read-only catalogue.

Key design decisions
--------------------
- Cache key is derived from the *parsed* query structure (ParsedQuery), not the raw
  string, so "black dragon" / "dragon black" / "BLACK  DRAGON" all share one entry.
- Values are arbitrary (callers store rendered HTML strings so session-bound ORM
  objects never enter the cache).
- TTL = 5 minutes (cards update weekly; mid-session staleness is acceptable).
- Max size = 1 000 entries (≈ 10 MB for 10 KB HTML fragments average).
- Eviction: LRU (OrderedDict trick — O(1) promote / O(1) evict).
- Thread safety: one RLock guards all mutations (safe under Gunicorn + uvicorn).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from typing import Any

from app.modules.catalogue.search_parser import ParsedQuery


# ---------------------------------------------------------------------------
# Cache key
# ---------------------------------------------------------------------------

def make_cache_key(parsed: ParsedQuery) -> str:
    """
    Deterministic cache key from a ParsedQuery.

    All list fields are sorted so query-word order does not create duplicate
    entries.  The result is a short (8-char) hex string — cheap to compute,
    negligible collision risk for a 1 000-entry cache.
    """
    canonical = {
        "colors":        tuple(sorted(parsed.colors)),
        "colorless":     parsed.colorless,
        "multicolor":    parsed.multicolor,
        "monocolor":     parsed.monocolor,
        "rarities":      tuple(sorted(parsed.rarities)),
        "formats":       tuple(sorted(parsed.formats)),
        "text_tokens":   tuple(sorted(t.lower().strip() for t in parsed.text_tokens)),
        "oracle_tokens": tuple(sorted(t.lower().strip() for t in parsed.oracle_tokens)),
        "type_tokens":   tuple(sorted(t.lower().strip() for t in parsed.type_tokens)),
        "cmc_exact":     parsed.cmc_exact,
        "cmc_max":       parsed.cmc_max,
        "cmc_min":       parsed.cmc_min,
    }
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.md5(blob.encode(), usedforsecurity=False).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Cache implementation
# ---------------------------------------------------------------------------

class TTLLRUCache:
    """
    Thread-safe TTL + LRU cache backed by OrderedDict.

    get()  — O(1)  (hash lookup + move_to_end)
    set()  — O(1)  (insert + optional eviction of oldest)
    clear  — O(n)  (one dict clear)
    """

    def __init__(self, max_size: int = 1_000, ttl_seconds: float = 300.0) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self._cache:
                return None
            value, expiry = self._cache[key]
            if time.monotonic() >= expiry:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)   # mark as most-recently used
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                del self._cache[key]       # remove to update LRU position
            elif len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)   # evict oldest
            self._cache[key] = (value, time.monotonic() + self.ttl_seconds)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def evict_expired(self) -> int:
        """Remove all TTL-expired entries; returns count removed."""
        with self._lock:
            now = time.monotonic()
            stale = [k for k, (_, exp) in self._cache.items() if now >= exp]
            for k in stale:
                del self._cache[k]
            return len(stale)

    def stats(self) -> dict:
        with self._lock:
            return {
                "size":            len(self._cache),
                "max_size":        self.max_size,
                "ttl_seconds":     self.ttl_seconds,
                "fill_pct":        round(len(self._cache) / self.max_size * 100, 1),
            }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

search_cache = TTLLRUCache(max_size=1_000, ttl_seconds=300.0)
