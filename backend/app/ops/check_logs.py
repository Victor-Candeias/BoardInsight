"""Procura credenciais em logs (G4). Lê texto de ficheiros ou do stdin; nunca imprime o conteúdo das linhas.

Uso: `journalctl -u 'businessmap-*' -o cat | python -m app.ops.check_logs [ficheiro ...]`.
Sai com 1 se encontrar a API Key/password configuradas ou credenciais por redigir.
"""

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote, quote_plus

from app.core.config import Settings, get_settings
from app.core.logging import _PATTERNS, REDACTED

Leak = tuple[str, int, str]


def secret_variants(settings: Settings) -> list[str]:
    values: set[str] = set()
    for secret in settings.secret_values():
        values |= {secret, quote(secret, safe=""), quote_plus(secret)}
    return sorted((v for v in values if len(v) >= 4), key=len, reverse=True)


def find_leaks(source: str, lines: Iterable[str], secrets: list[str]) -> list[Leak]:
    leaks: list[Leak] = []
    for number, line in enumerate(lines, 1):
        if any(secret in line for secret in secrets):
            leaks.append((source, number, "segredo configurado"))
            continue
        if any(m.group(3).strip("\"'") != REDACTED for m in _PATTERNS[0].finditer(line)):
            leaks.append((source, number, "credencial (apikey/password/token) por redigir"))
        elif any(m.group(2) != REDACTED for m in _PATTERNS[1].finditer(line)):
            leaks.append((source, number, "URI MongoDB com password"))
    return leaks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="ficheiros de log (omissão: stdin)")
    args = parser.parse_args()
    secrets = secret_variants(get_settings())
    if not secrets:
        print("[AVISO] sem segredos configurados no .env; só são procurados padrões de credenciais")
    leaks: list[Leak] = []
    scanned = 0
    sources = [(str(p), p.open(encoding="utf-8", errors="replace")) for p in args.files] or [("stdin", sys.stdin)]
    for name, handle in sources:
        with handle:
            lines = list(handle)
        scanned += len(lines)
        leaks += find_leaks(name, lines, secrets)
    for source, number, reason in leaks:
        print(f"[FALHA] {source}:{number}: {reason}")
    if scanned == 0:
        print("[AVISO] nenhuma linha de log analisada")
    elif not leaks:
        print(f"[OK] {scanned} linhas de log sem credenciais")
    sys.exit(1 if leaks else 0)


if __name__ == "__main__":
    main()
