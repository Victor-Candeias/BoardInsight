#!/usr/bin/env bash
# Corre todos os testes (backend + frontend). Uso: scripts/test.sh [backend|frontend]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
target="${1:-all}"

if [[ "$target" == "all" || "$target" == "backend" ]]; then
  echo "==> backend (pytest)"
  cd "$ROOT/backend"
  if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements-dev.lock
    .venv/bin/pip install -q --no-deps -e .
  fi
  .venv/bin/pytest -m "not live"
fi

if [[ "$target" == "all" || "$target" == "frontend" ]]; then
  echo "==> frontend (tsc + vitest)"
  cd "$ROOT/frontend"
  [[ -d node_modules ]] || npm ci --no-audit --no-fund
  npx tsc -b --noEmit
  npx vitest run
fi
