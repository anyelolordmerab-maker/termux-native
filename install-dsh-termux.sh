#!/data/data/com.termux/files/usr/bin/bash
# Instalador de DSH 0.2.2-rc.5 para Termux (binario/natives aarch64-bionic).
#
#   (sin opción) interactivo: si ya hay dsh, elige AISLADO por defecto.
#   --isolated  instala en $HOME/.local/dsh-termux + comando dsh241.
#   --live      reemplaza $PREFIX/bin/dsh con backup.
#
# No usa pkill; no toca HOME/XDG/TMPDIR del dsh existente en modo aislado.
set -euo pipefail

REPO="anyelolordmerab-maker/termux-native"
TAG="${TAG:-dsh-v0.2.2-rc.5-termux}"
ASSET="dsh-0.2.2-rc.5-termux-aarch64.tar.zst"
SHA="${ASSET}.sha256"
BASE="https://github.com/${REPO}/releases/download/${TAG}"
MODE=""
DEST="${HOME}/.local/dsh-termux"

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "[instalar] $*"; }

case "${1:-}" in
  --isolated) MODE="isolated" ;;
  --live) MODE="live" ;;
  -h|--help) sed -n '1,16p' "$0"; exit 0 ;;
  "") ;;
  *) die "opción desconocida: $1 (usa --isolated o --live)" ;;
esac

if [ -z "$MODE" ]; then
  if command -v dsh >/dev/null 2>&1 || [ -e "${PREFIX:-}/bin/dsh" ]; then
    echo "Detecté un dsh instalado. El modo LIVE lo reemplazaría."
    echo "  1) Aislado -> \$HOME/.local/dsh-termux + dsh241 (recomendado)"
    echo "  2) Live    -> reemplaza \$PREFIX/bin/dsh (con backup)"
    printf "Elige [1/2] (1): "
    read -r ans || ans=""
    case "$ans" in 2|2*) MODE="live" ;; *) MODE="isolated" ;; esac
  else
    echo "No detecté dsh instalado."
    echo "  1) Live    -> instala en \$PREFIX/bin/dsh"
    echo "  2) Aislado -> \$HOME/.local/dsh-termux + dsh241"
    printf "Elige [1/2] (1): "
    read -r ans || ans=""
    case "$ans" in 2|2*) MODE="isolated" ;; *) MODE="live" ;; esac
  fi
fi
if [ "$MODE" = "live" ] && [ "${1:-}" != "--live" ]; then
  printf "CONFIRMA reemplazar \$PREFIX/bin/dsh [s/N]: "
  read -r ok || ok=""
  case "$ok" in s|si|S|SI) ;; *) die "cancelado por el usuario" ;; esac
fi

[ "$(uname -m)" = "aarch64" ] || die "este binario es aarch64; tu arquitectura es $(uname -m)"
for c in curl sha256sum tar zstd node; do command -v "$c" >/dev/null || die "falta $c"; done

CACHE="${HOME}/.cache/dsh-termux"
mkdir -p "$CACHE"
TMP="$(mktemp -d "${TMPDIR:-$CACHE}/dsh241.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

dl() {
  local url="$1" out="$2"
  if [ -s "$out" ]; then
    echo "[descarga] reanudando $(basename "$out") ($(stat -c%s "$out") bytes ya bajados)"
    curl -fL --retry 5 --retry-delay 2 -C - -o "$out" "$url" || echo "[descarga] aviso: reanudación no aplicable; verifico sha"
  else
    echo "[descarga] iniciando $(basename "$out")"
    curl -fL --retry 5 --retry-delay 2 -o "$out" "$url"
  fi
}

log "descargando ${TAG} (un solo archivo comprimido, reanudable)"
dl "$BASE/$ASSET" "$CACHE/$ASSET"
dl "$BASE/$SHA" "$CACHE/$SHA"
awk '{n=split($NF,a,"/"); print $1 "  " a[n]}' "$CACHE/$SHA" > "$CACHE/check.sha256"
( cd "$CACHE" && sha256sum -c check.sha256 ) || die "sha256 no coincide; no se instala nada"

mkdir -p "$TMP/x"
tar --zstd -xf "$CACHE/$ASSET" -C "$TMP/x"
ROOT_SRC="$TMP/x/package"
[ -x "$ROOT_SRC/bin/dsh" ] || die "el archive no trae package/bin/dsh"

if [ "$MODE" = "isolated" ]; then
  mkdir -p "$DEST" "$HOME/.local/bin"
  cp -a "$ROOT_SRC" "$DEST/app"
  cat > "$HOME/.local/bin/dsh241" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
ROOT="$DEST"
export HOME="\$ROOT/home"
export XDG_DATA_HOME="\$ROOT/home/.local/share"
export XDG_CACHE_HOME="\$ROOT/home/.cache"
export XDG_CONFIG_HOME="\$ROOT/home/.config"
export XDG_STATE_HOME="\$ROOT/home/.local/state"
export TMPDIR="\$ROOT/tmp"
# No heredar nada del dsh 0.2.2-rc.1 ni del opencode 2.0.31.
unset LD_LIBRARY_PATH OPENTUI_LIB_PATH OPENTUI_LIBC
unset OPENCODE_SESSION_ID OPENCODE OPENCODE_TERMINAL AI_AGENT
unset DSH_CONFIG DSH_PROFILE DSH_LOG_LEVEL
export PATH="\$ROOT/app/bin:\$PREFIX/bin:\$PATH"
mkdir -p "\$HOME" "\$XDG_DATA_HOME" "\$XDG_CACHE_HOME" "\$XDG_CONFIG_HOME" "\$XDG_STATE_HOME" "\$TMPDIR"
exec "\$ROOT/app/bin/dsh" "\$@"
EOF
  chmod 700 "$HOME/.local/bin/dsh241"
  log "instalado en modo AISLADO: $HOME/.local/bin/dsh241"
  log "NO se tocó \$PREFIX/bin/dsh ni tu configuración actual"
  FINAL="$HOME/.local/bin/dsh241"
else
  PREFIX_BIN="${PREFIX}/bin/dsh"
  [ -n "${PREFIX:-}" ] || die "PREFIX no definido (¿no estás en Termux?)"
  if [ -e "$PREFIX_BIN" ]; then
    STAMP="$(date +%Y%m%d-%H%M%S)"
    cp -a "$PREFIX_BIN" "${PREFIX_BIN}.bak-${STAMP}"
    log "backup: ${PREFIX_BIN}.bak-${STAMP}"
  fi
  rm -rf "$PREFIX/lib/dsh-termux"
  cp -a "$ROOT_SRC" "$PREFIX/lib/dsh-termux"
  printf '#!/data/data/com.termux/files/usr/bin/bash\nexport PATH="%s/lib/dsh-termux/bin:$PREFIX/bin:$PATH"\nexec "%s/lib/dsh-termux/bin/dsh" "$@"\n' "$PREFIX" "$PREFIX" > "$PREFIX_BIN"
  chmod 700 "$PREFIX_BIN"
  log "instalado en modo LIVE: $PREFIX_BIN"
  FINAL="$PREFIX_BIN"
fi

log "verificación rápida:"
"$FINAL" --version 2>&1 | head -3 || true
log "listo"
