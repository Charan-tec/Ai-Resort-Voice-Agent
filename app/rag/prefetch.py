import asyncio
import re
import time
from typing import Dict, List, Optional
from app.core.config import settings
from app.core.logging import logger


class SpeculativePrefetchCache:
    """
    In-memory TTL cache storing speculative RAG query results triggered by interim STT transcripts.
    """

    def __init__(self, ttl_seconds: float = 15.0, max_entries: int = 100):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._cache: Dict[str, dict] = {}  # normalized_key -> {"docs": list, "expires_at": float}
        self._lock = asyncio.Lock()

    STOP_WORDS = {
        "what", "which", "who", "when", "where", "why", "how", "is", "are", "was", "were",
        "be", "been", "being", "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "with", "about", "against", "between", "into", "through", "during", "before",
        "after", "above", "below", "from", "up", "down", "of", "off", "over", "under", "again",
        "can", "will", "just", "should", "now", "tell", "me", "do", "does", "did", "have", "has",
        "our", "you", "your", "we", "us", "i", "azure", "paradise", "resort", "time"
    }

    @classmethod
    def normalize_query(cls, query: str) -> str:
        """Strip punctuation and normalize whitespace for robust cache key matching."""
        cleaned = re.sub(r"[^\w\s]", "", query.lower().strip())
        tokens = sorted([t for t in cleaned.split() if t not in cls.STOP_WORDS and len(t) > 1])
        return " ".join(tokens)

    async def get(self, query: str) -> Optional[List[dict]]:
        """Retrieve cached documents if present and not expired."""
        async with self._lock:
            key = self.normalize_query(query)
            entry = self._cache.get(key)
            if not entry:
                # Also check substring token overlap
                query_tokens = set(key.split())
                if query_tokens:
                    for ckey, centry in self._cache.items():
                        if centry["expires_at"] > time.monotonic():
                            cached_tokens = set(ckey.split())
                            common_tokens = query_tokens & cached_tokens
                            # Prevent confusing checkin vs checkout
                            if ("checkin" in query_tokens and "checkout" in cached_tokens) or ("checkout" in query_tokens and "checkin" in cached_tokens):
                                continue
                            if len(common_tokens) >= 2 or (len(common_tokens) >= 1 and cached_tokens == query_tokens):
                                logger.info(f"Speculative RAG: Partial token cache HIT for '{query}' -> matched '{ckey}'")
                                return centry["docs"]
                return None

            if time.monotonic() > entry["expires_at"]:
                del self._cache[key]
                return None

            logger.info(f"Speculative RAG: Cache HIT for '{query}' (key: '{key}')")
            return entry["docs"]

    async def set(self, query: str, docs: List[dict]):
        """Store query results with TTL."""
        async with self._lock:
            if len(self._cache) >= self.max_entries:
                # Evict expired or oldest entry
                now = time.monotonic()
                expired = [k for k, v in self._cache.items() if v["expires_at"] <= now]
                for k in expired:
                    del self._cache[k]
                if len(self._cache) >= self.max_entries:
                    oldest = next(iter(self._cache))
                    del self._cache[oldest]

            key = self.normalize_query(query)
            self._cache[key] = {
                "docs": docs,
                "expires_at": time.monotonic() + self.ttl_seconds
            }
            logger.debug(f"Speculative RAG: Cached {len(docs)} docs for key: '{key}' (TTL={self.ttl_seconds}s)")

    async def clear(self):
        async with self._lock:
            self._cache.clear()


prefetch_cache = SpeculativePrefetchCache(
    ttl_seconds=settings.SPECULATIVE_PREFETCH_TTL_SECONDS,
    max_entries=settings.SPECULATIVE_CACHE_MAX_ENTRIES
)
