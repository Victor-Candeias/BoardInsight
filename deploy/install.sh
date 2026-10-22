#!/usr/bin/env bash
# BoardInsight — instalação/atualização no Debian (idempotente).
#
# Uso (no servidor, a partir de um checkout do repositório):
#   sudo deploy/install.sh [--skip-frontend-build] [--no-start]
#
# - Cria o utilizador de sistema `boardinsight` (sem login) e as pastas.
# - Copia backend/frontend/deploy para /opt/boardinsight (sem .git, .venv, node_modules, .env).
# - Cria/atualiza o venv com requirements.lock e faz o build do frontend.
# - Instala as units systemd, o site Nginx e os limites do journald.
# - Nunca escreve nem mostra o `.env` real: só o cria a partir do `.env.example` se não existir.
set -euo pipefail

APP_USER=boardinsight
APP_DIR=/opt/boardinsight
DATA_DIR=/var/lib/boardinsight
ENV_FILE="$APP_DIR/.env"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
UNITS=(businessmap-api.service businessmap-worker.service businessmap-sync.service businessmap-sync.timer)
NODE_HEAP_MB="${NODE_HEAP_MB:-768}"

build_frontend=1
start=1
for arg in "$@"; do
  case "$arg" in
    --skip-frontend-build) build_frontend=0 ;;
    --no-start) start=0 ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '==> %s\n' "$*"; }
die() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "correr com sudo/root"
[[ "$SRC" != "$APP_DIR" ]] || die "correr a partir do checkout do repositório, não de $APP_DIR"
for cmd in python3 rsync nginx systemctl curl; do
  command -v "$cmd" >/dev/null || die "comando em falta: $cmd (apt install python3-venv rsync nginx curl)"
done
python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else 1)' \
  || die "é necessário Python 3.13 (encontrado: $(python3 --version))"
python3 -c 'import venv, ensurepip' 2>/dev/null || die "falta o pacote python3-venv"
if (( build_frontend )); then
  command -v npm >/dev/null || die "npm em falta (ou usar --skip-frontend-build com frontend/dist já compilado)"
fi

log "utilizador e pastas"
if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$DATA_DIR" --no-create-home --shell /usr/sbin/nologin "$APP_USER"
fi
install -d -o root -g root -m 755 "$APP_DIR"
install -d -o "$APP_USER" -g "$APP_USER" -m 750 "$DATA_DIR" "$DATA_DIR/exports"

log "código em $APP_DIR"
rsync -a --delete \
  --exclude '.git/' --exclude '.env' --exclude '.venv/' --exclude 'node_modules/' \
  --exclude '__pycache__/' --exclude '.pytest_cache/' --exclude '*.egg-info/' \
  --exclude 'frontend/dist/' --exclude 'backend/samples/' --exclude '.maestru/' \
  "$SRC/backend" "$SRC/frontend" "$SRC/deploy" "$SRC/.env.example" "$SRC/README.md" "$APP_DIR/"
chown -R root:root "$APP_DIR/backend" "$APP_DIR/frontend" "$APP_DIR/deploy"

if [[ ! -f "$ENV_FILE" ]]; then
  install -o "$APP_USER" -g "$APP_USER" -m 600 "$APP_DIR/.env.example" "$ENV_FILE"
  log "criado $ENV_FILE a partir do .env.example — preencher MONGODB_PASSWORD e BUSINESSMAP_API_KEY"
fi
chown "$APP_USER:$APP_USER" "$ENV_FILE"
chmod 600 "$ENV_FILE"

log "backend: venv e dependências fixadas"
cd "$APP_DIR/backend"
[[ -x .venv/bin/python ]] || python3 -m venv .venv
.venv/bin/pip install -q --disable-pip-version-check -r requirements.lock
.venv/bin/pip install -q --disable-pip-version-check --no-deps -e .

if (( build_frontend )); then
  log "frontend: build de produção (lento no Atom; heap Node ${NODE_HEAP_MB} MB)"
  cd "$APP_DIR/frontend"
  npm ci --no-audit --no-fund --loglevel=error
  NODE_OPTIONS="--max-old-space-size=$NODE_HEAP_MB" npm run -s build
elif [[ -d "$SRC/frontend/dist" ]]; then
  rsync -a --delete "$SRC/frontend/dist/" "$APP_DIR/frontend/dist/"
fi
[[ -f "$APP_DIR/frontend/dist/index.html" ]] || die "frontend/dist/index.html em falta"

log "systemd, journald e Nginx"
for unit in "${UNITS[@]}"; do
  install -o root -g root -m 644 "$APP_DIR/deploy/systemd/$unit" "/etc/systemd/system/$unit"
done
install -d -m 755 /etc/systemd/journald.conf.d
install -o root -g root -m 644 "$APP_DIR/deploy/journald/boardinsight.conf" /etc/systemd/journald.conf.d/boardinsight.conf
install -o root -g root -m 644 "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/boardinsight
ln -sfn /etc/nginx/sites-available/boardinsight /etc/nginx/sites-enabled/boardinsight
if [[ -e /etc/nginx/sites-enabled/default ]]; then
  log "aviso: /etc/nginx/sites-enabled/default também usa default_server; remover se a porta 80 for só do BoardInsight"
fi
nginx -t
systemctl daemon-reload
systemctl restart systemd-journald

if (( start )); then
  log "arranque dos serviços"
  systemctl enable --now businessmap-api.service businessmap-worker.service businessmap-sync.timer
  systemctl restart businessmap-api.service businessmap-worker.service
  systemctl reload nginx
  for _ in $(seq 1 30); do
    curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break
    sleep 1
  done
  curl -fsS http://127.0.0.1:8000/health >/dev/null || die "API não respondeu em /health (journalctl -u businessmap-api)"
  curl -fsS http://127.0.0.1/health >/dev/null || die "Nginx não encaminha /health"
  if curl -fsS http://127.0.0.1/ready >/dev/null; then
    log "pronto: /ready OK"
  else
    log "aviso: /ready falhou (MongoDB ou BUSINESSMAP_API_KEY) — ver: curl -s http://127.0.0.1/ready"
  fi
fi
log "concluído"
