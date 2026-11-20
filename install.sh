#!/data/data/com.termux/files/usr/bin/bash
set -e
VER="2.3.2"
URL="https://github.com/anyelolordmerab-maker/termux-native/releases/download/opencode-v${VER}/opencode-${VER}-termux-aarch64.tar.zst"
DEST="$HOME/.cache/opencode-update"
PKG="opencode-${VER}-termux-aarch64"

echo "== opencode ${VER} (Termux aarch64 nativo) =="
for c in curl tar; do command -v "$c" >/dev/null 2>&1 || pkg install -y "$c"; done
command -v zstd >/dev/null 2>&1 || pkg install -y zstd || true

rm -rf "$DEST"
mkdir -p "$DEST"
echo "[1/3] Descargando (~107 MB)..."
curl -fL --progress-bar -o "$DEST/oc.tar.zst" "$URL"

echo "[2/3] Extrayendo..."
tar --zstd -xf "$DEST/oc.tar.zst" -C "$HOME"

echo "[3/3] Instalando (backup automático de binario y datos)..."
bash "$HOME/$PKG/install.sh"

rm -rf "$DEST"
echo
echo "Listo. Ejecuta: source ~/.bashrc"
echo "Rollback (si hace falta): bash ~/$PKG/rollback.sh <carpeta-en-~/backups/opencode-*>"
