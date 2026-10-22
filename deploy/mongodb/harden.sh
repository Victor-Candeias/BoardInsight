#!/usr/bin/env bash
# BoardInsight — hardening do MongoDB 4.4 e firewall da LAN (idempotente).
#
# Uso: sudo deploy/mongodb/harden.sh [--lan 192.168.1.0/24] [--no-firewall] [--no-restart]
#
# - Instala deploy/mongodb/mongodb44.conf em /etc/mongodb44.conf (cópia .bak da anterior).
# - Instala a rotação de logs do mongod em /etc/logrotate.d/mongodb44.
# - UFW: nega entradas por omissão, permite SSH e HTTP (80) só da LAN e nega 27017.
#   Só acrescenta regras; não faz reset das existentes.
# - Reinicia mongodb44.service e verifica com `python -m app.ops.check_mongodb`.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CONF=/etc/mongodb44.conf
UNIT=mongodb44.service
lan=""
firewall=1
restart=1
while (( $# )); do
  case "$1" in
    --lan) lan="${2:?falta a sub-rede}"; shift ;;
    --no-firewall) firewall=0 ;;
    --no-restart) restart=0 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $1" >&2; exit 2 ;;
  esac
  shift
done

log() { printf '==> %s\n' "$*"; }
die() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "correr com sudo/root"
systemctl cat "$UNIT" >/dev/null 2>&1 || die "unit $UNIT não encontrada"

log "configuração do MongoDB"
if ! cmp -s "$HERE/mongodb44.conf" "$CONF"; then
  [[ -f "$CONF" ]] && cp -p "$CONF" "$CONF.bak.$(date +%Y%m%d%H%M%S)"
  install -o root -g root -m 644 "$HERE/mongodb44.conf" "$CONF"
  changed=1
else
  changed=0
fi
install -o root -g root -m 644 "$HERE/logrotate-mongodb44" /etc/logrotate.d/mongodb44
chmod 700 /var/lib/mongodb44 /var/log/mongodb44 2>/dev/null || true

if (( firewall )); then
  command -v ufw >/dev/null || die "ufw em falta (apt install ufw) ou usar --no-firewall"
  if [[ -z "$lan" ]]; then
    iface="$(ip -4 route show default | awk '{print $5; exit}')"
    lan="$(ip -4 -o route show dev "$iface" scope link | awk '{print $1; exit}')"
    [[ -n "$lan" ]] || die "não consegui detetar a LAN; usar --lan <sub-rede>"
  fi
  log "firewall UFW (LAN $lan)"
  ufw default deny incoming
  ufw default allow outgoing
  ufw allow from "$lan" to any port 22 proto tcp comment 'SSH LAN'
  ufw allow from "$lan" to any port 80 proto tcp comment 'BoardInsight (Nginx)'
  ufw deny 27017/tcp comment 'MongoDB só loopback'
  ufw deny 8000/tcp comment 'API só via Nginx'
  ufw --force enable
  ufw status verbose
fi

if (( restart && changed )); then
  log "reinício de $UNIT"
  systemctl restart "$UNIT"
  for _ in $(seq 1 30); do
    systemctl is-active --quiet "$UNIT" && break
    sleep 1
  done
  systemctl is-active --quiet "$UNIT" || die "$UNIT não arrancou (journalctl -u $UNIT; config anterior em $CONF.bak.*)"
fi

APP_BACKEND=/opt/boardinsight/backend
if [[ -x "$APP_BACKEND/.venv/bin/python" ]]; then
  log "verificação"
  sleep 2
  (cd "$APP_BACKEND" && BOARDINSIGHT_ENV_FILE=/opt/boardinsight/.env runuser -u boardinsight -- .venv/bin/python -m app.ops.check_mongodb)
fi
log "concluído"
