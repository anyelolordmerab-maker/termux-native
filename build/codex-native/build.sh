#!/usr/bin/env bash
set -euo pipefail
TAG="${1:?usage: build.sh rust-v0.171.0}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="${2:-$PWD/out}"
mkdir -p "$OUT"
SRC="$OUT/codex-src"
if [ ! -d "$SRC/.git" ]; then
  git clone --depth 1 --branch "$TAG" https://github.com/openai/codex.git "$SRC"
fi
cd "$SRC/codex-rs"

# --- parches Android (idempotentes) ---
python3 "$ROOT/patch-android.py" "$SRC"

# --- toolchain ---
TOOLCHAIN="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64"
API=28
export CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER="$TOOLCHAIN/bin/aarch64-linux-android${API}-clang"
export CC_aarch64_linux_android="$TOOLCHAIN/bin/aarch64-linux-android${API}-clang"
export CXX_aarch64_linux_android="$TOOLCHAIN/bin/aarch64-linux-android${API}-clang++"
export AR_aarch64_linux_android="$TOOLCHAIN/bin/llvm-ar"
export CFLAGS_aarch64_linux_android="-D__ANDROID_API__=$API --target=aarch64-linux-android$API"
export BINDGEN_EXTRA_CLANG_ARGS="--target=aarch64-linux-android$API -isystem $TOOLCHAIN/sysroot/usr/include -isystem $TOOLCHAIN/sysroot/usr/include/aarch64-linux-android"
export CXXFLAGS="-D__ANDROID_API__=$API"
export RUSTFLAGS="-C link-arg=-Wl,-z,max-page-size=16384"
cargo build --release --target aarch64-linux-android -p codex-cli --bin codex

BIN="$SRC/codex-rs/target/aarch64-linux-android/release/codex"
file "$BIN"; readelf -h "$BIN" | grep -E 'Class|Machine|Type'; readelf -d "$BIN" | grep NEEDED || true
mkdir -p "$OUT/package/bin" "$OUT/package/etc"
cp "$BIN" "$OUT/package/bin/codex"
chmod 755 "$OUT/package/bin/codex"
cp "$ROOT/config.toml" "$OUT/package/etc/config.toml"
cat > "$OUT/package/bin/codex-termux" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
mkdir -p "$CODEX_HOME"
[ -f "$CODEX_HOME/config.toml" ] || cp "$ROOT/etc/config.toml" "$CODEX_HOME/config.toml"
export LD_LIBRARY_PATH="$ROOT/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$ROOT/bin/codex" "$@"
EOF
chmod 755 "$OUT/package/bin/codex-termux"
mkdir -p "$OUT/package/lib"
cp "$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so" "$OUT/package/lib/" 2>/dev/null || true
TAR="codex-${TAG#rust-v}-termux-aarch64.tar.zst"
tar --zstd -cf "$OUT/$TAR" -C "$OUT/package" .
sha256sum "$OUT/$TAR" > "$OUT/$TAR.sha256"
echo "BUILD_OK $OUT/$TAR"
