import logging
import time
import uuid
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.api.errors import error_body
from app.core.logging import request_id_var

logger = logging.getLogger("boardinsight.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["x-request-id"] = request_id
            return response
        finally:
            logger.info(
                "pedido",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                },
            )
            request_id_var.reset(token)


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Recusa escritas vindas de páginas de outra origem (a API não tem autenticação).

    Pedidos sem cabeçalho `Origin` (curl, timer, worker) passam; a mesma origem é a do `Host`.
    """

    def __init__(self, app, allowed_origins: list[str]):
        super().__init__(app)
        self.allowed = {o.rstrip("/").lower() for o in allowed_origins}

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method in UNSAFE_METHODS and origin and not self._allowed(origin, request):
            logger.warning("origem recusada", extra={"origin": origin, "path": request.url.path})
            return JSONResponse(error_body("origin_not_allowed", "origem não autorizada"), status_code=403)
        return await call_next(request)

    def _allowed(self, origin: str, request: Request) -> bool:
        origin = origin.rstrip("/").lower()
        if origin in self.allowed:
            return True
        parsed = urlsplit(origin)
        host = request.headers.get("host", "").lower()
        return parsed.scheme in {"http", "https"} and parsed.netloc == host
