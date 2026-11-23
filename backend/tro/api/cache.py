"""Cache în memorie (TTL) pentru răspunsurile agregate + antete Cache-Control."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, TypeVar

from cachetools import TTLCache
from fastapi import Request, Response

from tro.config import get_settings

T = TypeVar("T")

_cache: TTLCache[str, Any] | None = None
_lock = threading.Lock()


def _get() -> TTLCache[str, Any]:
    global _cache
    if _cache is None:
        _cache = TTLCache(maxsize=2048, ttl=get_settings().cache_ttl_s)
    return _cache


def clear() -> None:
    with _lock:
        _get().clear()


def cached(request: Request, response: Response, compute: Callable[[], T]) -> T:
    key = f"{request.url.path}?{sorted(request.query_params.multi_items())}"
    c = _get()
    with _lock:
        if key in c:
            response.headers["X-Cache"] = "HIT"
            response.headers["Cache-Control"] = f"public, max-age={get_settings().cache_ttl_s}"
            return c[key]  # type: ignore[no-any-return]
    value = compute()
    with _lock:
        c[key] = value
    response.headers["X-Cache"] = "MISS"
    response.headers["Cache-Control"] = f"public, max-age={get_settings().cache_ttl_s}"
    return value
