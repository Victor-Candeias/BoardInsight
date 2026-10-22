"""Rate limit local (janela deslizante de 60 s, em memória).

A API corre com um único worker Uvicorn, por isso um contador por processo chega.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Literal

from fastapi import Depends, Request

from app.api.deps import AppSettings
from app.api.errors import ApiError

Bucket = Literal["sync", "export"]
WINDOW_SECONDS = 60.0


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, bucket: str, key: str, limit: int, window: float = WINDOW_SECONDS) -> float | None:
        """Regista um pedido; devolve os segundos até haver vaga se o limite foi excedido."""
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault((bucket, key), deque())
            while hits and hits[0] <= now - window:
                hits.popleft()
            if len(hits) >= limit:
                return hits[0] + window - now
            hits.append(now)
            return None


def rate_limit(bucket: Bucket):
    def dependency(request: Request, settings: AppSettings) -> None:
        limit = getattr(settings, f"rate_limit_{bucket}_per_minute")
        if limit <= 0:
            return
        limiter: RateLimiter = request.app.state.rate_limiter
        client = request.client.host if request.client else "unknown"
        retry_after = limiter.hit(bucket, client, limit)
        if retry_after is not None:
            seconds = max(1, math.ceil(retry_after))
            raise ApiError(
                429,
                "rate_limited",
                f"demasiados pedidos; tente novamente dentro de {seconds} s",
                {"limitPerMinute": limit, "retryAfterSeconds": seconds},
                headers={"Retry-After": str(seconds)},
            )

    return Depends(dependency)
