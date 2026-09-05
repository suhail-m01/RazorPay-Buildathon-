"""Rate limiting — Redis when configured, in-process fixed-window otherwise."""
from __future__ import annotations

import time

_buckets: dict[str, tuple[int, float]] = {}

try:  # pragma: no cover - optional dependency
    import redis.asyncio as aioredis

    _redis = None

    async def _get_redis():
        global _redis
        from app.core.config import get_settings

        if not get_settings().redis_url:
            return None
        if _redis is None:
            _redis = aioredis.from_url(get_settings().redis_url, decode_responses=True)
        return _redis
except ImportError:  # pragma: no cover
    async def _get_redis():
        return None


async def rate_limit(key: str, max_hits: int, window_seconds: int) -> bool:
    """True = allowed. Fixed window; swap the store for Redis at scale."""
    r = await _get_redis()
    if r is not None:
        n = await r.incr(f"rl:{key}")
        if n == 1:
            await r.expire(f"rl:{key}", window_seconds)
        return n <= max_hits
    now = time.time()
    hits, reset = _buckets.get(key, (0, 0.0))
    if reset < now:
        _buckets[key] = (1, now + window_seconds)
        return True
    if hits >= max_hits:
        return False
    _buckets[key] = (hits + 1, reset)
    return True
