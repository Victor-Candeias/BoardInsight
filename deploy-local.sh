#!/usr/bin/env bash
# BoardInsight — deploy local completo em /opt/BoardInsight (systemd de utilizador).
#
# Uso (a partir do checkout do repositório, sem sudo):
#   ./deploy-local.sh [--test] [--no-restart]
#
#   --test        corre scripts/test.sh (backend + frontend) antes do deploy
#   --no-restart  copia e compila, mas não reinicia os serviços
#
# Passos:
# - Copia backend/frontend/deploy/.env.example/README.md para /opt/BoardInsight (rsync --delete;
#   nunca toca em .env, data/, .venv, node_modules).
# - Backend: venv + requirements.lock + pacote em modo editável.
# - Frontend: npm ci (só se o package-lock.json mudou) e build de produção.
# - Instala as units de deploy/systemd-user em ~/.config/systemd/user, ativa-as e reinicia
#   API, worker e site; verifica /ready e o site.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="${APP_DIR:-/opt/BoardInsight}"
ENV_FILE="$APP_DIR/.env"
UNIT_DIR="$HOME/.config/systemd/user"
API_URL="${API_URL:-http://127.0.0.1:8000}"
WEB_URL="${WEB_URL:-http://127.0.0.1:5180}"
SERVICES=(boardinsight-api.service boardinsight-worker.service boardinsight-web.service)
ENABLE=("${SERVICES[@]}" boardinsight-sync.timer)

run_tests=0
restart=1
for arg in "$@"; do
  case "$arg" in
    --test) run_tests=1 ;;
    --no-restart) restart=0 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '==> %s\n' "$*"; }
warn() { printf 'AVISO: %s\n' "$*" >&2; }
die() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }

[[ $EUID -ne 0 ]] || die "não correr com sudo: o deploy local usa o systemd do utilizador"
[[ "$SRC" != "$APP_DIR" ]] || die "correr a partir do checkout do repositório, não de $APP_DIR"
for cmd in python3 rsync npm node systemctl curl; do
  command -v "$cmd" >/dev/null || die "comando em falta: $cmd"
done
[[ -d "$APP_DIR" && -w "$APP_DIR" ]] || die "$APP_DIR não existe ou não tem permissão de escrita (sudo install -d -o $USER $APP_DIR)"
[[ -f "$ENV_FILE" ]] || die "$ENV_FILE em falta (copiar de .env.example e preencher MONGODB_PASSWORD e BUSINESSMAP_API_KEY)"

commit="$(git -C "$SRC" rev-parse --short HEAD 2>/dev/null || echo desconhecido)"
if [[ -n "$(git -C "$SRC" status --porcelain 2>/dev/null)" ]]; then
  warn "há alterações por commitar; o deploy inclui o estado atual dos ficheiros"
  commit="$commit+alterações"
fi

if (( run_tests )); then
  log "testes"
  "$SRC/scripts/test.sh"
fi

log "código em $APP_DIR (commit $commit)"
rsync -a --delete \
  --exclude '.git/' --exclude '.env' --exclude '.venv/' --exclude 'node_modules/' \
  --exclude '__pycache__/' --exclude '.pytest_cache/' --exclude '*.egg-info/' \
  --exclude 'frontend/dist/' --exclude '*.tsbuildinfo' --exclude 'backend/samples/' \
  "$SRC/backend" "$SRC/frontend" "$SRC/deploy" "$SRC/.env.example" "$SRC/README.md" "$APP_DIR/"
chmod 600 "$ENV_FILE"
mkdir -p "$APP_DIR/data/exports"

log "backend: venv e dependências fixadas"
cd "$APP_DIR/backend"
[[ -x .venv/bin/python ]] || python3 -m venv .venv
.venv/bin/pip install -q --disable-pip-version-check -r requirements.lock
.venv/bin/pip install -q --disable-pip-version-check --no-deps -e .

log "frontend: dependências e build de produção"
cd "$APP_DIR/frontend"
lock_hash="$(sha256sum package-lock.json | cut -d' ' -f1)"
stamp=node_modules/.deploy-lock-sha256
if [[ ! -f "$stamp" || "$(cat "$stamp")" != "$lock_hash" ]]; then
  npm ci --no-audit --no-fund --loglevel=error
  echo "$lock_hash" > "$stamp"
fi
npm run -s build
[[ -f dist/index.html ]] || die "frontend/dist/index.html em falta"
echo "$commit $(date -Iseconds)" > "$APP_DIR/DEPLOYED_COMMIT"

log "systemd de utilizador"
mkdir -p "$UNIT_DIR"
install -m 644 "$APP_DIR"/deploy/systemd-user/boardinsight-* "$UNIT_DIR/"
systemctl --user daemon-reload
systemctl --user enable --quiet "${ENABLE[@]}"
[[ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" == yes ]] \
  || warn "linger desativado: os serviços só arrancam com sessão iniciada (sudo loginctl enable-linger $USER)"

if (( ! restart )); then
  log "concluído sem reiniciar (--no-restart)"
  exit 0
fi

log "reiniciar ${SERVICES[*]}"
systemctl --user restart "${SERVICES[@]}"
systemctl --user start boardinsight-sync.timer

log "verificação"
ok=0
for _ in $(seq 1 30); do
  if curl -fsS "$API_URL/ready" >/dev/null 2>&1; then ok=1; break; fi
  sleep 1
done
(( ok )) || { journalctl --user -u boardinsight-api.service -n 30 --no-pager >&2; die "API não ficou pronta em $API_URL/ready"; }
for _ in $(seq 1 15); do
  if curl -fsS -o /dev/null "$WEB_URL/"; then ok=2; break; fi
  sleep 1
done
(( ok == 2 )) || die "site não responde em $WEB_URL"
for unit in "${ENABLE[@]}"; do
  [[ "$(systemctl --user is-active "$unit")" == active ]] || die "$unit não está ativo"
done
log "deploy concluído: commit $commit — API $API_URL, site $WEB_URL"
