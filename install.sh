#!/data/data/com.termux/files/usr/bin/bash
set -e
VER="2.3.2"
URL="https://github.com/anyelolordmerab-maker/termux-native/releases/download/opencode-v${VER}/opencode-${VER}-termux-aarch64.tar.zst"
DEST="$HOME/.cache/opencode-update"
PKG="opencode-${VER}-termux-aarch64"
MODE="${1:-install}"

echo "== opencode ${VER} (Termux aarch64 nativo) =="
for c in curl tar; do command -v "$c" >/dev/null 2>&1 || pkg install -y "$c"; done
command -v zstd >/dev/null 2>&1 || pkg install -y zstd || true

if [ ! -x "$HOME/$PKG/opencode" ] || [ "$MODE" = "download" ]; then
  rm -rf "$DEST"
  mkdir -p "$DEST"
  echo "[1/3] Descargando (~107 MB)..."
  curl -fL --progress-bar -o "$DEST/oc.tar.zst" "$URL"
  echo "[2/3] Extrayendo en ~/$PKG ..."
  rm -rf "$HOME/$PKG"
  tar --zstd -xf "$DEST/oc.tar.zst" -C "$HOME"
  rm -rf "$DEST"
else
  echo "Usando ~/$PKG ya descargado."
fi

if [ "$MODE" = "test" ]; then
  echo "[3/3] Prueba aislada (no toca tu opencode ni tus datos)..."
  export LD_LIBRARY_PATH="$HOME/$PKG/lib/opencode:${LD_LIBRARY_PATH:-}"
  export OPENTUI_LIB_PATH="$HOME/$PKG/lib/libopentui.so"
  export XDG_DATA_HOME="$HOME/.cache/opencode-test-data"
  export XDG_CONFIG_HOME="$HOME/.cache/opencode-test-config"
  mkdir -p "$XDG_DATA_HOME" "$XDG_CONFIG_HOME"
  "$HOME/$PKG/opencode" --version
  "$HOME/$PKG/opencode" --help >/dev/null 2>&1 && echo "HELP OK"
  echo
  echo "PRUEBA OK. No se instaló nada ni se tocaron tus datos."
  echo "Para instalar de verdad (con backup automático):"
  echo "  bash ~/$PKG/install.sh"
  exit 0
fi

echo "[3/3] Instalando (backup automático de binario y datos)..."
bash "$HOME/$PKG/install.sh"
echo
echo "Listo. Ejecuta: source ~/.bashrc"
echo "Rollback: bash ~/$PKG/rollback.sh <carpeta-en-~/backups/opencode-*>"
