#!/data/data/com.termux/files/usr/bin/bash
# Instalador de opencode 2.4.1 (binario único bionic/aarch64) para Termux.
#
# Modos:
#   (sin opción) pregunta: si ya hay opencode, elige AISLADO por defecto.
#   --isolated  instala en $HOME/.local/opencode-241 y crea el
#               comando `opencode241` con HOME/XDG/TMPDIR propios. NO toca el
#               opencode que ya funciona ni su configuración.
#   --live      reemplaza $PREFIX/bin/opencode (con backup) para quien quiera
#               usar 2.4.1 como opencode principal.
#
# Uso:
#   bash install-opencode-241.sh            # interactivo
#   bash install-opencode-241.sh --isolated  # sin preguntar
#   bash install-opencode-241.sh --live
#
# No usa pkill ni patrones: si hay que detener instancias, se hace por PID.
set -euo pipefail

REPO="anyelolordmerab-maker/termux-native"
TAG="${TAG:-opencode-v2.4.1}"
ASSET="opencode-embedded-2.4.1.tar.zst"
SHA="${ASSET}.sha256"
BASE="https://github.com/${REPO}/releases/download/${TAG}"
MODE=""
DEST="${HOME}/.local/opencode-241"

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "[instalar] $*"; }

case "${1:-}" in
  --isolated) MODE="isolated" ;;
  --live) MODE="live" ;;
  -h|--help) sed -n '1,20p' "$0"; exit 0 ;;
  "") ;;
  *) die "opción desconocida: $1 (usa --isolated o --live)" ;;
esac

# Modo interactivo: si ya hay un opencode, por defecto AISLADO para no romperlo.
if [ -z "$MODE" ]; then
  if command -v opencode >/dev/null 2>&1 || [ -e "${PREFIX:-}/bin/opencode" ]; then
    echo
    echo "Detecté un opencode instalado. El modo LIVE lo reemplazaría y podría"
    echo "afectar sus sesiones/configuración. El modo AISLADO crea otro HOME/XDG"
    echo "y el comando opencode241, sin tocar el que ya funciona."
    echo
    echo "  1) Aislado  -> \$HOME/.local/opencode-241 + opencode241  (recomendado)"
    echo "  2) Live     -> reemplaza \$PREFIX/bin/opencode (con backup)"
    printf "Elige [1/2] (1): "
    read -r ans || ans=""
    case "$ans" in
      2|2*) MODE="live" ;;
      *) MODE="isolated" ;;
    esac
  else
    echo
    echo "No detecté un opencode instalado."
    echo "  1) Live     -> instala en \$PREFIX/bin/opencode"
    echo "  2) Aislado  -> \$HOME/.local/opencode-241 + opencode241"
    printf "Elige [1/2] (1): "
    read -r ans || ans=""
    case "$ans" in
      2|2*) MODE="isolated" ;;
      *) MODE="live" ;;
    esac
  fi
fi

if [ "$MODE" = "live" ] && [ "${1:-}" != "--live" ]; then
  printf "CONFIRMA reemplazar \$PREFIX/bin/opencode [s/N]: "
  read -r ok || ok=""
  case "$ok" in s|si|S|SI) ;; *) die "cancelado por el usuario" ;; esac
fi

[ "$(uname -m)" = "aarch64" ] || die "este binario es aarch64; tu arquitectura es $(uname -m)"
command -v curl >/dev/null || die "falta curl"
command -v sha256sum >/dev/null || die "falta sha256sum (coreutils)"
command -v tar >/dev/null || die "falta tar"
if ! command -v zstd >/dev/null; then
  die "falta zstd: pkg install zstd"
fi

CACHE="${HOME}/.cache/opencode-241"
mkdir -p "$CACHE"
TMP="$(mktemp -d "${TMPDIR:-$CACHE}/oc241.XXXXXX")"
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
( cd "$CACHE" && sha256sum -c "$SHA" ) || die "sha256 no coincide; no se instala nada"

mkdir -p "$TMP/x"
tar --zstd -xf "$CACHE/$ASSET" -C "$TMP/x"
BIN="$TMP/x/opencode-embedded"
[ -x "$BIN" ] || die "el archive no trae opencode-embedded ejecutable"
file "$BIN" 2>/dev/null | grep -q 'ELF.*aarch64\|ARM aarch64' || log "aviso: file no reconoció aarch64 (seguimos con sha verificado)"

if [ "$MODE" = "isolated" ]; then
  mkdir -p "$DEST" "$HOME/.local/bin"
  cp -f "$BIN" "$DEST/opencode-embedded"
  chmod 700 "$DEST/opencode-embedded"
  cat > "$HOME/.local/bin/opencode241" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
# Entorno 100% aislado: no lee ni escribe el HOME/XDG del opencode existente.
ROOT="$DEST"
export HOME="\$ROOT/home"
export XDG_DATA_HOME="\$ROOT/home/.local/share"
export XDG_CACHE_HOME="\$ROOT/home/.cache"
export XDG_CONFIG_HOME="\$ROOT/home/.config"
export XDG_STATE_HOME="\$ROOT/home/.local/state"
export TMPDIR="\$ROOT/tmp"
mkdir -p "\$HOME" "\$XDG_DATA_HOME" "\$XDG_CACHE_HOME" "\$XDG_CONFIG_HOME" "\$XDG_STATE_HOME" "\$TMPDIR"
exec "\$ROOT/opencode-embedded" "\$@"
EOF
  chmod 700 "$HOME/.local/bin/opencode241"
  log "instalado en modo AISLADO"
  log "comando: $HOME/.local/bin/opencode241"
  log "NO se tocó \$PREFIX/bin/opencode ni tu configuración actual"
  log "agrega \$HOME/.local/bin al PATH si quieres invocarlo como opencode241"
else
  PREFIX_BIN="${PREFIX}/bin/opencode"
  [ -n "${PREFIX:-}" ] || die "PREFIX no definido (¿no estás en Termux?)"
  if [ -e "$PREFIX_BIN" ]; then
    STAMP="$(date +%Y%m%d-%H%M%S)"
    cp -a "$PREFIX_BIN" "${PREFIX_BIN}.bak-${STAMP}"
    log "backup: ${PREFIX_BIN}.bak-${STAMP}"
  fi
  cp -f "$BIN" "$PREFIX_BIN"
  chmod 700 "$PREFIX_BIN"
  log "instalado en modo LIVE: $PREFIX_BIN"
  log "para volver: cp -a ${PREFIX_BIN}.bak-* $PREFIX_BIN"
fi

if [ "$MODE" = "isolated" ]; then
  FINAL="$HOME/.local/bin/opencode241"
else
  FINAL="$PREFIX/bin/opencode"
fi
log "verificación rápida:"
"$FINAL" --version 2>&1 | head -3 || true
log "listo"
