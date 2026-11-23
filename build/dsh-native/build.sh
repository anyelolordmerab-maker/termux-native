#!/usr/bin/env bash
# Transforma @deepseek-ai/dsh (ultima version) en un despliegue nativo Termux/aarch64.
# Corre en GitHub Actions (x86_64 para NDK / arm64 para el bundle).
set -euo pipefail

VER="${1:?usage: build.sh VERSION}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="${2:-$PWD/out}"
STAGE="$OUT/stage"
PATCHES="$ROOT/patches"
REFSHA="${REFSHA:-v0.1.0-termux.1}"

echo "==> DSH native build version=$VER"
rm -rf "$STAGE" && mkdir -p "$STAGE" "$OUT"

# 1) paquete npm oficial (sin scripts: no compila nada en el host)
echo "==> [1/7] npm pack @deepseek-ai/dsh@$VER"
cd "$OUT"
npm pack "@deepseek-ai/dsh@$VER" --silent >/dev/null
TARBALL=$(ls -1 deepseek-ai-dsh-*.tgz | head -1)
mkdir -p "$STAGE/package"
tar xzf "$TARBALL" -C "$STAGE/package" --strip-components=1

# 2) dependencias JS (sin scripts nativos)
echo "==> [2/7] npm install --ignore-scripts"
cd "$STAGE/package"
npm install --ignore-scripts --no-audit --no-fund --engine-strict=false >/dev/null 2>&1
# fallback WASM de sharp (nativo x64 del runner no sirve en Android)
npm install @img/sharp-wasm32 --no-save --ignore-scripts --no-audit --no-fund >/dev/null 2>&1 || true

# 3) parches Android desde el repo de referencia
echo "==> [3/7] applying Android patches"
apply_all() {
  local patch="$1" pkg="$2" n=0
  while IFS= read -r dir; do
    if (cd "$dir" && patch -p1 --forward --fuzz=3 < "$patch" >/dev/null 2>&1); then
      echo "    OK $(basename "$patch") -> ${dir#$STAGE/package/node_modules/}"
      n=$((n+1))
    fi
  done < <(find "$STAGE/package/node_modules" -type d -path "*/@deepseek-ai/$pkg" -print)
  echo "    applied $n copies of $(basename "$patch")"
}
apply_all "$PATCHES/01-terminal-bash-android-shell.patch" dsh-terminal-bash
apply_all "$PATCHES/02-session-persistence-link-rename.patch" dsh-session-persistence-jsonl
apply_all "$PATCHES/03-subprocess-local-android.patch" dsh-subprocess-local
apply_all "$PATCHES/04-host-apiproxy-termux-open-index.patch" dsh-host-apiproxy
apply_all "$PATCHES/04-host-apiproxy-termux-open-opener.patch" dsh-host-apiproxy
apply_all "$PATCHES/05-host-directory-picker-native-android.patch" dsh-host-directory-picker-native
apply_all "$PATCHES/06-workspace-archive-skip-session-known-check.patch" dsh-workspace
apply_all "$PATCHES/07-sandbox-local-proot-runner.patch" dsh-sandbox-local
apply_all "$PATCHES/08-dsh-tool-fs-search-android-rg.patch" dsh-tool-fs-search

# 4) nativos bionic/aarch64 desde el release de referencia (N-API ABI-stable)
echo "==> [4/7] prebuilt native modules"
cd "$OUT"
curl -fsSL -o ref.tgz "https://github.com/Vengisk/deepseek-harness-termux/releases/download/$REFSHA/dsh-termux.tgz"
mkdir -p ref && tar xzf ref.tgz -C ref --strip-components=1
PTY="$STAGE/package/node_modules/node-pty"
install -Dm755 ref/prebuilt/android-arm64/pty.node "$PTY/build/Release/pty.node"
install -Dm755 ref/prebuilt/android-arm64/pty.node "$PTY/prebuilds/android-arm64/pty.node"
install -Dm755 ref/prebuilt/android-arm64/koffi.node "$STAGE/package/node_modules/koffi/build/koffi/android_arm64/koffi.node"

# 5) ripgrep shim de Termux
echo "==> [5/7] ripgrep android shim"
mkdir -p "$STAGE/package/node_modules/@vscode/ripgrep-android-arm64/bin"
ln -sf /data/data/com.termux/files/usr/bin/rg \
  "$STAGE/package/node_modules/@vscode/ripgrep-android-arm64/bin/rg"

# 6) koffi statx patch + abwrap (bwrap-compatible) compilado con NDK
echo "==> [6/7] koffi statx + abwrap NDK"
apply_all "$PATCHES/koffi-statx.patch" koffi
if [ -n "${ANDROID_NDK_HOME:-}" ]; then
  git clone --depth 1 https://github.com/dukmu/abwrap-android.git "$OUT/abwrap-android"
  (cd "$OUT/abwrap-android" && BUILD_DIR="$OUT/abwrap-android/build-release" sh scripts/build-android.sh arm64-v8a)
  install -Dm755 "$OUT/abwrap-android/build-release/abwrap" "$STAGE/package/bin/abwrap"
  cat > "$STAGE/package/bin/bwrap" <<'EOF'
#!/usr/bin/env bash
AB="${DSH_ABWRAP_BIN:-$(dirname "$(readlink -f "$0")")/abwrap}"
ARGS=(--android-base)
for arg in "$@"; do
  case "$arg" in --unshare-pid) ;; *) ARGS+=("$arg");; esac
done
exec "$AB" "${ARGS[@]}"
EOF
  chmod 755 "$STAGE/package/bin/bwrap"
fi

# 7) launcher + metadata + pack
echo "==> [7/7] launcher, metadata, package"
cat > "$STAGE/package/bin/dsh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
exec node --expose-internals "$ROOT/node_modules/@deepseek-ai/dsh/lib/bin.js" "$@"
EOF
chmod 755 "$STAGE/package/bin/dsh"
node -e '
const fs=require("fs"),p=process.argv[1],v=process.argv[2];
const j=JSON.parse(fs.readFileSync(p,"utf8"));
j.name="dsh-termux"; j.version=v+"-termux.1";
j.bin={dsh:"bin/dsh","dsh-termux":"bin/dsh"};
j.bundleDependencies=Object.keys(j.dependencies||{});
j.description=(j.description||"")+" (native Termux aarch64 build)";
fs.writeFileSync(p,JSON.stringify(j,null,2)+"\n");
' "$STAGE/package/package.json" "$VER"
NODE_BIN=$(command -v node)
BINJS="$STAGE/package/node_modules/@deepseek-ai/dsh/lib/bin.js"
if [ -f "$BINJS" ] && ! head -1 "$BINJS" | grep -q -- "--expose-internals"; then
  { printf '#!%s --expose-internals\n' "$NODE_BIN"; tail -n +2 "$BINJS"; } > "$BINJS.new"
  mv "$BINJS.new" "$BINJS"; chmod 755 "$BINJS"
fi
TAR="dsh-$VER-termux-aarch64.tar.zst"
tar --zstd -cf "$OUT/$TAR" -C "$STAGE" package
sha256sum "$OUT/$TAR" > "$OUT/$TAR.sha256"
echo "BUILD_OK $OUT/$TAR"
