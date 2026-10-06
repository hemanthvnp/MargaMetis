import hashlib
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_client = None
_hits   = 0
_misses = 0


def _redis():
    global _client
    if _client is not None:
        return _client or None  # False is the 'unavailable' sentinel
    try:
        import redis
        url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
        r = redis.from_url(url, decode_responses=True, socket_connect_timeout=2)
        r.ping()
        _client = r
        logger.info(f"Redis connected: {url}")
    except Exception as exc:
        logger.warning(f"Redis unavailable — caching disabled ({exc})")
        _client = False  # sentinel so we don't retry on every request
    return _client or None


def _key(prefix: str, *parts: str) -> str:
    raw = "|".join(p.lower().strip() for p in parts)
    return prefix + hashlib.sha256(raw.encode()).hexdigest()[:20]


def geocode_key(location: str) -> str:
    return _key("geocode:", location)


def route_key(
    origin: str,
    dest: str,
    route_type: str,
    vehicle: str,
    time_of_day: Optional[int] = None,
) -> str:
    parts = [origin, dest, route_type, vehicle]
    if time_of_day is not None:
        parts.append(str(time_of_day))
    return _key("route:", *parts)


def get(key: str) -> Optional[Any]:
    global _hits, _misses
    r = _redis()
    if r is None:
        return None
    try:
        raw = r.get(key)
        if raw:
            _hits += 1
            return json.loads(raw)
        _misses += 1
        return None
    except Exception:
        return None


def set(key: str, value: Any, ttl: int = 3600) -> None:
    r = _redis()
    if r is None:
        return
    try:
        r.setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass


def stats() -> dict:
    r = _redis()
    total = _hits + _misses
    base = {
        "hits":         _hits,
        "misses":       _misses,
        "hit_rate_pct": round(_hits / total * 100, 1) if total else 0.0,
    }
    if r is None:
        return {"status": "unavailable", **base}
    try:
        info = r.info("stats")
        keys = r.dbsize()
        return {
            "status":      "connected",
            "cached_keys": keys,
            "cmd_hits":    info.get("keyspace_hits", 0),
            "cmd_misses":  info.get("keyspace_misses", 0),
            **base,
        }
    except Exception:
        return {"status": "error", **base}
