"""Verificação do hardening do MongoDB (G2). Só leitura; não mostra credenciais.

Uso: `python -m app.ops.check_mongodb [--config /etc/mongodb44.conf]`. Sai com 1 se alguma verificação falhar.
"""

import argparse
import ipaddress
import re
import sys
from collections.abc import Iterable
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

from app.core.config import Settings, get_settings
from app.core.database import create_client

OK, WARN, FAIL = "OK", "AVISO", "FALHA"
APP_ROLES = {"read", "readWrite"}
MAX_CACHE_GB = 0.25
Finding = tuple[str, str]


def listening_addresses(port: int, tables: Iterable[str]) -> list[str]:
    """Endereços em LISTEN na porta, a partir de /proc/net/tcp{,6}."""
    found: list[str] = []
    for table in tables:
        for line in table.splitlines()[1:]:
            fields = line.split()
            if len(fields) < 4 or fields[3] != "0A":
                continue
            addr_hex, port_hex = fields[1].split(":")
            if int(port_hex, 16) != port:
                continue
            raw = bytes.fromhex(addr_hex)
            # O kernel escreve cada palavra de 32 bits em little-endian.
            packed = b"".join(raw[i : i + 4][::-1] for i in range(0, len(raw), 4))
            found.append(str(ipaddress.ip_address(packed)))
    return found


def check_bind(port: int, tables: Iterable[str]) -> list[Finding]:
    addrs = listening_addresses(port, tables)
    if not addrs:
        return [(WARN, f"nenhum socket em LISTEN na porta {port}")]
    exposed = [a for a in addrs if not ipaddress.ip_address(a).is_loopback]
    if exposed:
        return [(FAIL, f"porta {port} exposta em {', '.join(exposed)} (usar bindIp: 127.0.0.1)")]
    return [(OK, f"porta {port} só em loopback ({', '.join(sorted(set(addrs)))})")]


def check_config(text: str) -> list[Finding]:
    def value(key: str) -> str | None:
        match = re.search(rf"^\s*{key}\s*:\s*([^#\n]+?)\s*$", text, re.MULTILINE)
        return match.group(1).strip("'\"") if match else None

    findings: list[Finding] = []
    auth = value("authorization")
    findings.append((OK, "authorization: enabled") if auth == "enabled" else (FAIL, "security.authorization não está enabled"))
    bind = value("bindIp")
    loopback = bind is not None and all(h.strip() in {"127.0.0.1", "::1", "localhost"} for h in bind.split(","))
    if value("bindIpAll") == "true" or not loopback:
        findings.append((FAIL, f"net.bindIp deve ser só loopback (atual: {bind or 'omissão'})"))
    else:
        findings.append((OK, f"bindIp: {bind}"))
    cache = value("cacheSizeGB")
    if cache is None or float(cache) > MAX_CACHE_GB:
        findings.append((WARN, f"wiredTiger cacheSizeGB {cache or 'por omissão'}; recomendado ≤ {MAX_CACHE_GB}"))
    else:
        findings.append((OK, f"wiredTiger cacheSizeGB: {cache}"))
    if value("javascriptEnabled") != "false":
        findings.append((WARN, "security.javascriptEnabled não está a false"))
    if value("logRotate") != "reopen":
        findings.append((WARN, "systemLog.logRotate: reopen em falta (rotação com logrotate)"))
    return findings


def check_unauthenticated(settings: Settings) -> list[Finding]:
    client: MongoClient = MongoClient(
        settings.mongodb_host, settings.mongodb_port, serverSelectionTimeoutMS=settings.mongodb_timeout_ms
    )
    try:
        client.list_database_names()
    except OperationFailure:
        return [(OK, "ligação sem credenciais é recusada")]
    except PyMongoError as exc:
        return [(FAIL, f"MongoDB inacessível ({type(exc).__name__})")]
    finally:
        client.close()
    return [(FAIL, "ligação sem credenciais consegue listar bases (ativar authorization)")]


def check_app_roles(roles: list[dict[str, str]], database: str) -> list[Finding]:
    if not roles:
        return [(FAIL, "a aplicação liga-se sem utilizador autenticado")]
    extra = [f"{r['role']}@{r['db']}" for r in roles if r["role"] not in APP_ROLES or r["db"] != database]
    if extra:
        return [(FAIL, f"utilizador da app com privilégios a mais: {', '.join(sorted(extra))}")]
    return [(OK, f"utilizador da app limitado a {', '.join(sorted(r['role'] for r in roles))} em {database}")]


def check_app_user(settings: Settings) -> list[Finding]:
    client = create_client(settings)
    try:
        status = client[settings.mongodb_database].command("connectionStatus")
    except PyMongoError as exc:
        return [(FAIL, f"a aplicação não consegue autenticar ({type(exc).__name__})")]
    finally:
        client.close()
    return check_app_roles(status["authInfo"]["authenticatedUserRoles"], settings.mongodb_database)


def run(settings: Settings, config_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    tables = [p.read_text() for p in map(Path, ("/proc/net/tcp", "/proc/net/tcp6")) if p.exists()]
    findings += check_bind(settings.mongodb_port, tables)
    try:
        findings += check_config(config_path.read_text())
    except OSError as exc:
        findings.append((WARN, f"não consegui ler {config_path} ({exc.strerror})"))
    findings += check_unauthenticated(settings)
    findings += check_app_user(settings)
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=Path("/etc/mongodb44.conf"))
    args = parser.parse_args()
    findings = run(get_settings(), args.config)
    for level, message in findings:
        print(f"[{level}] {message}")
    sys.exit(1 if any(level == FAIL for level, _ in findings) else 0)


if __name__ == "__main__":
    main()
