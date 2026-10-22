"""Frontend compilado (`frontend/dist`) servido pela própria API.

Usado na instalação Windows, onde não há Nginx: `FRONTEND_DIST` aponta para a pasta `dist`. Regras
equivalentes às do `deploy/nginx.conf`: `assets/` com cache imutável, rotas do React Router caem no
`index.html` (sem cache) e nada é servido abaixo de `api/`.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import ConfigurationError

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
}
IMMUTABLE = {**SECURITY_HEADERS, "Cache-Control": "public, max-age=31536000, immutable"}
NO_CACHE = {**SECURITY_HEADERS, "Cache-Control": "no-cache"}


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """Regista a rota catch-all do frontend; tem de ser chamada depois de todas as rotas da API."""
    dist = dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        raise ConfigurationError(f"FRONTEND_DIST não contém index.html: {dist}")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise StarletteHTTPException(404, "Not Found")
        if path:
            candidate = (dist / path).resolve()
            if candidate.is_relative_to(dist) and candidate.is_file():
                return FileResponse(candidate, headers=IMMUTABLE if path.startswith("assets/") else NO_CACHE)
            if path.startswith("assets/"):
                raise StarletteHTTPException(404, "Not Found")
        return FileResponse(index, headers=NO_CACHE)
