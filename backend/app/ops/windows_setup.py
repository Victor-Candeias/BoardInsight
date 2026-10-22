"""Configuração pós-instalação no Windows (chamada pelo instalador Inno Setup a cada instalação/atualização).

1. Cria o `.env` a partir do modelo (se não existir; numa atualização acrescenta as opções novas do modelo) e grava os
   valores escolhidos no instalador, com `APP_HOST=127.0.0.1` (G9) e `AUTH_ENABLED=false` (G10); gera a
   password MongoDB da aplicação se estiver vazia. A API key chega pela variável de ambiente
   `BOARDINSIGHT_SETUP_API_KEY` (nunca pela linha de comandos); vazia = manter a atual.
2. Cria os utilizadores MongoDB: `admin` (root, password em `--admin-secret`) pela localhost exception na
   primeira execução e o utilizador da aplicação (readWrite na base); nas seguintes autentica como admin.
3. Cria os índices e regista o board inicial (metadados + job `sync_board`) se ainda não existir.

Idempotente. Códigos de saída: 0 ok, 1 falha no MongoDB, 2 board inicial não registado (não fatal),
3 falha a preparar o `.env`/segredo. Erros ficam sempre no `--log`.
Uso: python -m app.ops.windows_setup --env FICH --template FICH --admin-secret FICH [--url URL]
     [--board ID] [--port N] [--frontend-dist DIR] [--log FICH]
"""

import argparse
import asyncio
import logging
import os
import re
import secrets
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import OperationFailure, PyMongoError

from app.core.config import Settings
from app.core.database import create_client
from app.core.indexes import ensure_indexes
from app.core.logging import JsonFormatter, Redactor
from app.integrations.businessmap import BusinessmapClient
from app.repositories.boards import BoardRepository
from app.repositories.jobs import JobRepository
from app.services.boards import fetch_board_metadata
from app.services.sync import ClientFactory

logger = logging.getLogger("app.ops.windows_setup")

API_KEY_ENV = "BOARDINSIGHT_SETUP_API_KEY"
ADMIN_USER = "admin"
EXIT_OK, EXIT_MONGO, EXIT_BOARD, EXIT_CONFIG = 0, 1, 2, 3


class SetupError(RuntimeError):
    pass


def _key_pattern(key: str) -> re.Pattern[str]:
    return re.compile(rf"^\s*{re.escape(key)}\s*=(.*)$")


def read_env_value(path: Path, key: str) -> str | None:
    pattern = _key_pattern(key)
    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            return match.group(1).strip().strip("'\"")
    return None


def set_env_values(path: Path, values: dict[str, str]) -> None:
    """Substitui `KEY=valor` mantendo comentários e ordem; acrescenta as chaves em falta no fim."""
    lines = path.read_text(encoding="utf-8").splitlines()
    pending = dict(values)
    for i, line in enumerate(lines):
        for key in list(pending):
            if _key_pattern(key).match(line):
                lines[i] = f"{key}={pending.pop(key)}"
                break
    lines += [f"{key}={value}" for key, value in pending.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def missing_template_lines(env_path: Path, template: Path) -> list[str]:
    """Linhas `KEY=valor` do modelo cujas chaves não existem no `.env` (novas opções numa atualização)."""
    existing = env_path.read_text(encoding="utf-8").splitlines()
    missing = []
    for line in template.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*([A-Z][A-Z0-9_]*)\s*=", line)
        if match and not any(_key_pattern(match.group(1)).match(current) for current in existing):
            missing.append(line.strip())
    return missing


def prepare_env(
    env_path: Path,
    template: Path,
    *,
    url: str | None = None,
    board: int | None = None,
    port: int | None = None,
    api_key: str | None = None,
    frontend_dist: Path | None = None,
) -> None:
    if env_path.is_dir():
        # Pasta no lugar do ficheiro (ex.: `mkdir` manual): remover se vazia; com conteúdo, não arriscar.
        try:
            env_path.rmdir()
        except OSError as exc:
            raise SetupError(f"{env_path} é uma pasta e não um ficheiro; remover a pasta e voltar a instalar") from exc
    if not env_path.exists():
        env_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template, env_path)
    else:
        added = missing_template_lines(env_path, template)
        if added:
            text = env_path.read_text(encoding="utf-8").rstrip("\n")
            header = "# Opções novas acrescentadas na atualização (ver o modelo env.windows):"
            env_path.write_text("\n".join([text, "", header, *added]) + "\n", encoding="utf-8")
    # A API só aceita ligações desta máquina (G9): sem acesso pela rede, nem em instalações antigas com 0.0.0.0.
    # Sem janela de login (G10): desliga também instalações feitas com o pacote que a ligava; o código G9 fica disponível.
    values: dict[str, str] = {
        "EXPORT_DIR": str(env_path.parent / "exports"),
        "APP_HOST": "127.0.0.1",
        "AUTH_ENABLED": "false",
    }
    if url:
        values["BUSINESSMAP_BASE_URL"] = url.strip().rstrip("/")
    if board:
        values["BUSINESSMAP_BOARD_ID"] = str(board)
    if port:
        values["APP_PORT"] = str(port)
    if api_key and api_key.strip():
        values["BUSINESSMAP_API_KEY"] = api_key.strip()
    if frontend_dist is not None:
        values["FRONTEND_DIST"] = str(frontend_dist)
    if not read_env_value(env_path, "MONGODB_PASSWORD"):
        values["MONGODB_PASSWORD"] = secrets.token_urlsafe(32)
    set_env_values(env_path, values)


def ensure_secret_file(path: Path) -> str:
    if path.exists() and path.read_text(encoding="utf-8").strip():
        return path.read_text(encoding="utf-8").strip()
    value = secrets.token_urlsafe(32)
    path.write_text(value + "\n", encoding="utf-8")
    return value


def _client(settings: Settings, **auth: Any) -> MongoClient:
    return MongoClient(
        host=settings.mongodb_host,
        port=settings.mongodb_port,
        directConnection=True,
        serverSelectionTimeoutMS=settings.mongodb_timeout_ms,
        **auth,
    )


def wait_for_mongo(settings: Settings, timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            with _client(settings) as client:
                client.admin.command("ping")
            return
        except PyMongoError:
            if time.monotonic() >= deadline:
                raise SetupError(f"MongoDB não respondeu em {settings.mongodb_host}:{settings.mongodb_port}") from None
            time.sleep(2)


def _authenticates(settings: Settings, username: str, password: str, source: str) -> bool:
    try:
        with _client(settings, username=username, password=password, authSource=source) as client:
            client[source].command("connectionStatus")
        return True
    except OperationFailure:
        return False


def ensure_mongo_users(settings: Settings, admin_password: str) -> str:
    """Garante o admin e o utilizador da aplicação. Devolve 'existing', 'updated' ou 'created'."""
    user = settings.mongodb_username
    if not user or settings.mongodb_password is None:
        raise SetupError("MONGODB_USERNAME/MONGODB_PASSWORD em falta no .env")
    password = settings.mongodb_password.get_secret_value()
    database = settings.mongodb_database
    source = settings.mongodb_auth_source or database
    if _authenticates(settings, user, password, source):
        return "existing"
    if not _authenticates(settings, ADMIN_USER, admin_password, "admin"):
        try:
            with _client(settings) as anonymous:
                anonymous.admin.command("createUser", ADMIN_USER, pwd=admin_password, roles=[{"role": "root", "db": "admin"}])
        except OperationFailure as exc:
            raise SetupError("o MongoDB já tem utilizadores e a password de admin guardada não é válida") from exc
        logger.info("utilizador admin do MongoDB criado")
    with _client(settings, username=ADMIN_USER, password=admin_password, authSource="admin") as admin:
        target = admin[source]
        if target.command("usersInfo", user)["users"]:
            target.command("updateUser", user, pwd=password)
            result = "updated"
        else:
            target.command("createUser", user, pwd=password, roles=[{"role": "readWrite", "db": database}])
            result = "created"
    logger.info("utilizador da aplicação no MongoDB", extra={"user": user, "result": result})
    return result


async def register_board(db: Database, settings: Settings, board_id: int, client_factory: ClientFactory | None = None) -> bool:
    """Regista o board (como `POST /api/v1/boards`) se ainda não existir. Devolve True se o criou."""
    repo = BoardRepository(db)
    if repo.get(board_id) is not None:
        return False
    factory = client_factory or (lambda: BusinessmapClient.from_settings(settings))
    async with factory() as client:
        metadata = await fetch_board_metadata(client, board_id)
    repo.upsert_metadata(board_id, metadata)
    JobRepository(db).enqueue("sync_board", {"boardId": board_id})
    return True


def _configure_logging(secrets: list[str], log_path: Path | None) -> None:
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    handler: logging.Handler = logging.FileHandler(log_path, encoding="utf-8") if log_path else logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(Redactor(secrets)))
    root = logging.getLogger()
    for old in root.handlers:
        if isinstance(old, logging.FileHandler):
            old.close()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)


def run(args: argparse.Namespace) -> int:
    api_key = os.environ.get(API_KEY_ENV) or ""
    _configure_logging([api_key], args.log)
    try:
        prepare_env(
            args.env,
            args.template,
            url=args.url,
            board=args.board,
            port=args.port,
            api_key=api_key,
            frontend_dist=args.frontend_dist,
        )
        admin_password = ensure_secret_file(args.admin_secret)
        settings = Settings(_env_file=args.env)
    except (SetupError, OSError) as exc:
        logger.error("falha a preparar a configuração: %s", exc)
        return EXIT_CONFIG
    except ValidationError as exc:
        # Só os nomes dos campos: as mensagens do pydantic incluem os valores.
        logger.error("configuração inválida em %s: %s", args.env, sorted(str(e["loc"][0]) for e in exc.errors() if e["loc"]))
        return EXIT_CONFIG
    _configure_logging(settings.secret_values(), args.log)
    logger.info("configuração Windows iniciada", extra={"env": str(args.env)})
    try:
        wait_for_mongo(settings, args.wait)
        ensure_mongo_users(settings, admin_password)
        db = create_client(settings)[settings.mongodb_database]
        ensure_indexes(db, settings)
    except (SetupError, PyMongoError) as exc:
        logger.error("falha na configuração do MongoDB: %s", exc)
        return EXIT_MONGO
    board_id = args.board or settings.businessmap_board_id
    try:
        created = asyncio.run(register_board(db, settings, board_id))
    except Exception as exc:
        logger.warning("board inicial não registado: %s", type(exc).__name__, extra={"board_id": board_id, "detail": str(exc)})
        return EXIT_BOARD
    logger.info("configuração Windows concluída", extra={"board_id": board_id, "board_created": created})
    return EXIT_OK


def main() -> None:
    parser = argparse.ArgumentParser(description="Configuração pós-instalação BoardInsight (Windows)")
    parser.add_argument("--env", type=Path, required=True, help="ficheiro .env da instalação")
    parser.add_argument("--template", type=Path, required=True, help="modelo do .env (usado se o .env não existir)")
    parser.add_argument("--admin-secret", type=Path, required=True, help="ficheiro com a password do admin MongoDB")
    parser.add_argument("--url", help="URL da instância Businessmap")
    parser.add_argument("--board", type=int, help="board inicial")
    parser.add_argument("--port", type=int, help="porta do site")
    parser.add_argument("--frontend-dist", type=Path, help="pasta frontend/dist servida pela API")
    parser.add_argument("--log", type=Path, help="ficheiro de log (por omissão stdout)")
    parser.add_argument("--wait", type=float, default=90, help="segundos à espera do MongoDB")
    raise SystemExit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
