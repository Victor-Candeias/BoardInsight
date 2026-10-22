"""Arranque da API com o host e a porta do `.env` (`APP_HOST`/`APP_PORT`).

Usado pelo serviço Windows `boardinsight-api` (a porta escolhida no instalador fica só no `.env`).
Uso: python -m app.serve
"""

import uvicorn

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, workers=1, access_log=False)


if __name__ == "__main__":
    main()
