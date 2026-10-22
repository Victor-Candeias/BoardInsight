#!/usr/bin/env bash
# BoardInsight — gera o instalador Windows (.exe) em Linux, sem root (G7).
#
# Uso (a partir de qualquer pasta):
#   deploy/windows/build-installer.sh [--skip-frontend]
#
#   --skip-frontend  reutiliza frontend/dist existente (não corre npm run build)
#
# Passos:
#  1. Frontend: npm ci (se node_modules faltar, estiver incompleto ou desatualizado) e npm run build.
#  2. Python 3.13 embeddable para Windows + dependências win_amd64 (pip --platform) + backend/app, pré-compilado.
#  3. MongoDB (só mongod.exe e vc_redist.x64.exe do ZIP oficial) e WinSW.
#  4. Inno Setup sob Wine (driver gráfico "null", sem display) -> dist/windows/BoardInsight-Setup-<versão>.exe
#
# Downloads, Wine portátil e prefixo Wine ficam em ${BOARDINSIGHT_BUILD_CACHE:-~/.cache/boardinsight-windows-build};
# cada download é verificado com o SHA256 de versions.env. Usa o Wine do sistema se existir (ou WINE=/caminho/wine).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
CACHE="${BOARDINSIGHT_BUILD_CACHE:-$HOME/.cache/boardinsight-windows-build}"
DOWNLOADS="$CACHE/downloads"
STAGE="$CACHE/stage"
APP="$STAGE/app"
OUT_DIR="${OUT_DIR:-$ROOT/dist/windows}"
# shellcheck source=versions.env
source "$HERE/versions.env"

skip_frontend=0
for arg in "$@"; do
  case "$arg" in
    --skip-frontend) skip_frontend=1 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "opção desconhecida: $arg" >&2; exit 2 ;;
  esac
done

log() { printf '==> %s\n' "$*" >&2; }
warn() { printf 'AVISO: %s\n' "$*" >&2; }
die() { printf 'ERRO: %s\n' "$*" >&2; exit 1; }

for cmd in python3 npm curl sha256sum tar rsync; do
  command -v "$cmd" >/dev/null || die "comando em falta: $cmd"
done
python3 -m pip --version >/dev/null 2>&1 || die "pip em falta (python3 -m pip)"

# Descarrega para $DOWNLOADS (se ainda não estiver lá) e valida o SHA256. Escreve o caminho no stdout.
fetch() {
  local url="$1" sha="$2" file
  file="$DOWNLOADS/$(basename "$url")"
  mkdir -p "$DOWNLOADS"
  if [[ ! -f "$file" ]] || ! echo "$sha  $file" | sha256sum -c --status; then
    log "a descarregar $(basename "$url")"
    curl -fL --retry 3 -o "$file.part" "$url"
    mv "$file.part" "$file"
    echo "$sha  $file" | sha256sum -c --status || die "SHA256 inválido: $file (atualizar versions.env?)"
  fi
  printf '%s' "$file"
}

winpath() { local p="$1"; printf 'Z:%s' "${p//\//\\}"; }

VERSION="$(python3 -c "import re,sys; print(re.search(r'__version__ = \"(.+?)\"', open(sys.argv[1]).read()).group(1))" "$ROOT/backend/app/__init__.py")"
log "BoardInsight $VERSION"

rm -rf "$STAGE"
mkdir -p "$APP" "$STAGE/winsw" "$STAGE/redist" "$OUT_DIR"

# 1. Frontend
if [[ $skip_frontend -eq 0 ]]; then
  log "frontend: build de produção"
  # npm ci se node_modules faltar, estiver incompleto (sem .package-lock.json) ou for anterior ao package-lock.json.
  ( cd "$ROOT/frontend" \
    && { [[ -f node_modules/.package-lock.json && ! package-lock.json -nt node_modules/.package-lock.json ]] \
         || npm ci --no-audit --no-fund; } \
    && npm run build )
fi
[[ -f "$ROOT/frontend/dist/index.html" ]] || die "frontend/dist em falta (correr sem --skip-frontend)"
mkdir -p "$APP/frontend"
cp -r "$ROOT/frontend/dist" "$APP/frontend/dist"

# 2. Python embeddable + dependências + backend
log "python $PYTHON_VERSION embeddable (win_amd64)"
python3 -m zipfile -e "$(fetch "$PYTHON_URL" "$PYTHON_SHA256")" "$APP/python"
# O ._pth substitui sys.path (PYTHONPATH é ignorado): stdlib, site-packages e o backend.
printf '%s\r\n' "python313.zip" "." "Lib\\site-packages" "..\\backend" "import site" > "$APP/python/python313._pth"
SITE="$APP/python/Lib/site-packages"
python3 -m pip install --quiet --disable-pip-version-check --no-deps --only-binary=:all: \
  --platform win_amd64 --python-version 3.13 --implementation cp --abi cp313 \
  --target "$SITE" -r "$ROOT/backend/requirements.lock" -r "$HERE/requirements-windows.txt"
rm -rf "$SITE/bin"
mkdir -p "$APP/backend"
rsync -a --exclude __pycache__ "$ROOT/backend/app/" "$APP/backend/app/"
if python3 -c 'import sys; sys.exit(sys.version_info[:2] != (3, 13))'; then
  # Bytecode é independente do SO; unchecked-hash não depende das datas dos ficheiros instalados.
  python3 -m compileall -q -j 0 --invalidation-mode unchecked-hash "$APP/backend" "$SITE" >/dev/null \
    || warn "alguns ficheiros não foram pré-compilados (serão compilados no 1.º arranque)"
else
  warn "python3 local não é 3.13: sem pré-compilação"
fi

# 3. MongoDB, VC++ Redistributable, WinSW e ficheiros de serviço
log "mongodb $MONGODB_VERSION (mongod.exe)"
python3 - "$(fetch "$MONGODB_URL" "$MONGODB_SHA256")" "$APP/mongodb" "$STAGE/redist" <<'PY'
import shutil, sys, zipfile
from pathlib import Path

archive, dest, redist = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
wanted = {"bin/mongod.exe": dest / "bin", "LICENSE-Community.txt": dest, "MPL-2": dest,
          "THIRD-PARTY-NOTICES": dest, "README": dest, "bin/vc_redist.x64.exe": redist}
with zipfile.ZipFile(archive) as z:
    for info in z.infolist():
        rel = info.filename.split("/", 1)[-1]
        if rel in wanted:
            target = wanted.pop(rel) / Path(rel).name
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
if wanted:
    sys.exit(f"em falta no ZIP do MongoDB: {sorted(wanted)}")
PY
cp "$(fetch "$WINSW_URL" "$WINSW_SHA256")" "$STAGE/winsw/WinSW-x64.exe"
cp "$HERE"/services/*.xml "$HERE/sync.cmd" "$APP/"
mkdir -p "$APP/config"
cp "$HERE/env.windows" "$APP/config/env.windows"

# 4. Inno Setup sob Wine
if [[ -z "${WINE:-}" ]]; then
  if command -v wine >/dev/null; then
    WINE="$(command -v wine)"
  else
    wine_dir="$CACHE/wine-$WINE_VERSION"
    if [[ ! -x "$wine_dir/bin/wine" ]]; then
      log "wine $WINE_VERSION portátil"
      tarball="$(fetch "$WINE_URL" "$WINE_SHA256")"
      rm -rf "$wine_dir.tmp" && mkdir -p "$wine_dir.tmp"
      tar -xJf "$tarball" -C "$wine_dir.tmp" --strip-components=1
      mv "$wine_dir.tmp" "$wine_dir"
    fi
    WINE="$wine_dir/bin/wine"
  fi
fi
export WINEPREFIX="${WINEPREFIX:-$CACHE/wineprefix}" WINEDEBUG=-all WINEDLLOVERRIDES="mscoree,mshtml="
ISCC_DIR="C:\\innosetup-$INNOSETUP_VERSION"
if [[ ! -f "$WINEPREFIX/drive_c/innosetup-$INNOSETUP_VERSION/ISCC.exe" ]]; then
  log "inno setup $INNOSETUP_VERSION no prefixo Wine $WINEPREFIX"
  "$WINE" wineboot -i >/dev/null 2>&1 || true
  # Sem display: o driver "null" permite ao instalador do Inno criar janelas invisíveis.
  "$WINE" reg add 'HKCU\Software\Wine\Drivers' /v Graphics /d null /f >/dev/null 2>&1
  # Esperar que o prefixo acabe de inicializar (senão: "Invalid window handle").
  wineserver_bin="$(dirname "$WINE")/wineserver"
  [[ -x "$wineserver_bin" ]] || wineserver_bin="$(command -v wineserver || true)"
  [[ -z "$wineserver_bin" ]] || "$wineserver_bin" -w
  "$WINE" "$(fetch "$INNOSETUP_URL" "$INNOSETUP_SHA256")" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER "/DIR=$ISCC_DIR" >/dev/null 2>&1 || true
  [[ -f "$WINEPREFIX/drive_c/innosetup-$INNOSETUP_VERSION/ISCC.exe" ]] || die "falhou a instalação do Inno Setup sob Wine"
fi

log "a compilar o instalador (Inno Setup; demora alguns minutos)"
"$WINE" "$ISCC_DIR\\ISCC.exe" /Q "/DAppVersion=$VERSION" "/DStageDir=$(winpath "$STAGE")" "/O$(winpath "$OUT_DIR")" \
  "$(winpath "$HERE/boardinsight.iss")" 2>&1 | grep -v '^[0-9a-f]\{4\}:\(fixme\|err\):' || true
EXE="$OUT_DIR/BoardInsight-Setup-$VERSION.exe"
[[ -f "$EXE" && "$EXE" -nt "$STAGE/app/config/env.windows" ]] || die "o ISCC não gerou $EXE"
( cd "$OUT_DIR" && sha256sum "$(basename "$EXE")" > "$(basename "$EXE").sha256" )
[[ "${KEEP_STAGE:-0}" == 1 ]] || rm -rf "$STAGE"
log "instalador: $EXE ($(du -h "$EXE" | cut -f1))"
