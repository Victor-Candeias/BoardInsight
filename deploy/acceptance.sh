#!/usr/bin/env bash
# BoardInsight — testes de aceitação operacionais (G4). Só leitura; não mostra segredos.
#
# Uso: sudo deploy/acceptance.sh [--after-reboot] [--since "-24h"] [--base-url http://127.0.0.1]
#
#   --after-reboot  exige arranque recente (< 60 min): confirma que tudo subiu sozinho após o reboot.
#   --since         janela do journald analisada para credenciais (omissão: desde o último boot).
#
# Verifica serviços/timer (ativos e com arranque automático), HTTP (SPA, /health, /ready, API),
# portas expostas, permissões do .env e da pasta de exportações, MongoDB endurecido,
# boards sincronizados (não desatualizados) e logs sem credenciais. Sai com 1 se houver FALHA.
set -uo pipefail

APP_USER=boardinsight
APP_DIR=/opt/boardinsight
BACKEND="$APP_DIR/backend"
ENV_FILE="$APP_DIR/.env"
DATA_DIR=/var/lib/boardinsight
base_url=http://127.0.0.1
since=""
after_reboot=0
while (( $# )); do
  case "$1" in
    --after-reboot) after_reboot=1 ;;
    --since) since="${2:?falta o valor}"; shift ;;
    --base-url) base_url="${2:?falta o URL}"; shift ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $1" >&2; exit 2 ;;
  esac
  shift
done

failures=0
ok() { printf '[OK] %s\n' "$*"; }
warn() { printf '[AVISO] %s\n' "$*"; }
fail() { printf '[FALHA] %s\n' "$*"; failures=$((failures + 1)); }
check() { local msg="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$msg"; else fail "$msg"; fi; }
as_app() { (cd "$BACKEND" && runuser -u "$APP_USER" -- env BOARDINSIGHT_ENV_FILE="$ENV_FILE" .venv/bin/python "$@"); }

[[ $EUID -eq 0 ]] || { echo "ERRO: correr com sudo/root (lê o journal, o .env e o log do MongoDB)" >&2; exit 2; }

echo "== Arranque"
uptime_s=$(cut -d. -f1 /proc/uptime)
echo "boot há $((uptime_s / 60)) min ($(uptime -s))"
if (( after_reboot )); then
  if (( uptime_s < 3600 )); then ok "arranque recente (teste pós-reboot)"; else fail "--after-reboot mas o sistema arrancou há mais de 60 min"; fi
fi

echo "== Serviços"
for unit in mongodb44.service nginx.service businessmap-api.service businessmap-worker.service businessmap-sync.timer; do
  check "$unit ativo" systemctl is-active --quiet "$unit"
  check "$unit com arranque automático" systemctl is-enabled --quiet "$unit"
done
result=$(systemctl show -p Result --value businessmap-sync.service)
last=$(systemctl show -p ExecMainExitTimestamp --value businessmap-sync.service)
if [[ -z "$last" ]]; then
  if (( uptime_s < 600 )); then warn "sync ainda não correu desde o boot (timer: OnBootSec=2min)"; else fail "sync nunca correu desde o boot"; fi
elif [[ "$result" == success ]]; then
  ok "última sync pelo timer terminou bem ($last)"
else
  fail "última sync pelo timer: $result ($last) — journalctl -u businessmap-sync"
fi
next=$(systemctl show -p NextElapseUSecRealtime --value businessmap-sync.timer)
if [[ -n "$next" ]]; then ok "próxima sync agendada: $next"; else fail "timer sem próxima execução"; fi

echo "== HTTP ($base_url)"
http_ok() { curl -fsS -m 10 -o /dev/null "$1"; }
check "Nginx serve a SPA em /" bash -c "curl -fsS -m 10 '$base_url/' | grep -q 'id=\"root\"'"
check "rotas da SPA caem no index.html (/reports)" bash -c "curl -fsS -m 10 '$base_url/reports' | grep -q 'id=\"root\"'"
check "/health" http_ok "$base_url/health"
check "/ready (MongoDB e API Key)" http_ok "$base_url/ready"
check "API /api/v1/boards" http_ok "$base_url/api/v1/boards"
check "API direta em 127.0.0.1:8000/health" http_ok http://127.0.0.1:8000/health
boards=$(curl -fsS -m 10 "$base_url/api/v1/boards" 2>/dev/null || echo '[]')
stale=$(python3 -c 'import json,sys; b=json.loads(sys.argv[1]); print(",".join(str(x["boardId"]) for x in b if x.get("enabled", True) and x.get("stale")))' "$boards" 2>/dev/null)
count=$(python3 -c 'import json,sys; print(len(json.loads(sys.argv[1])))' "$boards" 2>/dev/null || echo 0)
if [[ "$count" == 0 ]]; then warn "nenhum board configurado"
elif [[ -n "$stale" ]]; then fail "boards desatualizados (sem sync bem sucedida recente): $stale"
else ok "$count board(s) sincronizado(s)"; fi

echo "== Exposição na rede"
listening() { ss -ltnH "sport = :$1" | awk '{print $4}'; }
for port in 8000 27017; do
  addrs=$(listening "$port" | tr '\n' ' ')
  if [[ -z "$addrs" ]]; then fail "nada à escuta na porta $port"
  elif listening "$port" | grep -qvE '^(127\.0\.0\.1|\[::1\]):'; then fail "porta $port exposta: $addrs"
  else ok "porta $port só em loopback"; fi
done
if [[ -n "$(listening 80)" ]]; then ok "Nginx à escuta na porta 80"; else fail "nada à escuta na porta 80"; fi
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then ok "UFW ativo"; else warn "UFW inativo (deploy/mongodb/harden.sh)"; fi

echo "== Ficheiros e permissões"
env_stat=$(stat -c '%U %a' "$ENV_FILE" 2>/dev/null)
if [[ "$env_stat" == "$APP_USER 600" ]]; then ok ".env com dono $APP_USER e modo 600"; else fail ".env: esperado '$APP_USER 600', encontrado '${env_stat:-em falta}'"; fi
check "pasta de exportações gravável pelo serviço" runuser -u "$APP_USER" -- test -w "$DATA_DIR/exports"
check "código não gravável pelo serviço" bash -c "! runuser -u $APP_USER -- test -w $BACKEND/app"

echo "== MongoDB"
as_app -m app.ops.check_mongodb || failures=$((failures + 1))

echo "== Logs sem credenciais"
journal_args=(-u 'businessmap-*' -o cat --no-pager)
if [[ -n "$since" ]]; then journal_args+=(--since "$since"); else journal_args+=(-b); fi
{
  journalctl "${journal_args[@]}"
  cat /var/log/nginx/boardinsight.access.log /var/log/nginx/boardinsight.error.log 2>/dev/null
  tail -n 5000 /var/log/mongodb44/mongod.log 2>/dev/null
} | as_app -m app.ops.check_logs || failures=$((failures + 1))

echo
if (( failures )); then echo "RESULTADO: $failures falha(s)"; exit 1; fi
echo "RESULTADO: todos os testes de aceitação passaram"
