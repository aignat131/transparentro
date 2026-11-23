"""Client HTTP politicos: User-Agent identificabil, limitare de rată, reîncercări cu backoff."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

import httpx

from tro.config import get_settings

log = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, min_interval_s: float) -> None:
        self.min_interval_s = min_interval_s
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            delta = time.monotonic() - self._last
            if delta < self.min_interval_s:
                time.sleep(self.min_interval_s - delta)
            self._last = time.monotonic()


def make_client(**kwargs: Any) -> httpx.Client:
    s = get_settings()
    headers = {"User-Agent": s.user_agent}
    headers.update(kwargs.pop("headers", {}))
    return httpx.Client(headers=headers, timeout=s.http_timeout_s, follow_redirects=True, **kwargs)


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    limiter: RateLimiter | None = None,
    retries: int = 4,
    backoff_s: float = 2.0,
    **kwargs: Any,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        if limiter:
            limiter.wait()
        try:
            r = client.request(method, url, **kwargs)
            if r.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
            return r
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            wait = backoff_s * (2**attempt)
            log.warning("Cerere eșuată (%s %s): %s — reîncerc în %.0fs", method, url, exc, wait)
            time.sleep(wait)
    assert last_exc is not None
    raise last_exc


def download(url: str, dest: Path, *, client: httpx.Client | None = None, force: bool = False) -> Path:
    """Descarcă în streaming (fișiere de sute de MB) cu fișier temporar + rename atomic."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0 and not force:
        log.info("Folosesc fișierul din cache: %s", dest)
        return dest
    own = client is None
    c = client or make_client()
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        for attempt in range(4):
            try:
                with c.stream("GET", url) as r:
                    r.raise_for_status()
                    total = 0
                    with open(tmp, "wb") as f:
                        for chunk in r.iter_bytes(1 << 20):
                            f.write(chunk)
                            total += len(chunk)
                log.info("Descărcat %s (%.1f MB)", dest.name, total / 1e6)
                tmp.replace(dest)
                return dest
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                log.warning("Descărcare eșuată %s: %s (încercarea %d)", url, exc, attempt + 1)
                time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"Nu am putut descărca {url}")
    finally:
        if own:
            c.close()
