#!/bin/bash
# opencode nativo bionic (aarch64) — pipeline completo e idempotente.
# Uso:  GHT=<token> bash opencode-android.sh [version]
# Fases: 0 toolchain 1 fuente 2 install 3 plant 4 build 5 patchelf 6 tests 7 empaquetar 8 publicar
set -uo pipefail
VER="${1:-2.3.2}"
TGT=linux-arm64-android
OC=/content/oc
O=/content/out
L=$O/pipeline.log
mkdir -p $O /content/bin
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a $L; }
die(){ say "FATAL: $*"; echo "FAIL $*" > $O/STATUS; exit 1; }
: > $L

# ---------- 0 toolchain ----------
if [ ! -x /content/bin/bun ]; then
  say "0 bun download"
  curl -fsSL -o /tmp/b.zip https://github.com/oven-sh/bun/releases/download/bun-v1.4.5/bun-linux-x64.zip || die "bun zip"
  (cd /tmp && unzip -oq b.zip && cp bun-linux-x64/bun /content/bin/bun && chmod +x /content/bin/bun) || die "bun unzip"
fi
export PATH=/content/bin:$PATH
bun -v >/dev/null || die "bun no ejecuta"
command -v patchelf >/dev/null || DEBIAN_FRONTEND=noninteractive apt-get -qq install -y patchelf >/dev/null 2>&1
command -v patchelf >/dev/null || die "patchelf"

# ---------- 1 fuente ----------
if [ ! -f $OC/packages/cli/script/build.ts ]; then
  say "1 fuente v$VER"
  curl -fsSL -o /tmp/oc.tgz "https://codeload.github.com/anomalyco/opencode/tar.gz/refs/tags/v$VER" || die "codeload"
  mkdir -p $OC && tar xzf /tmp/oc.tgz -C $OC --strip-components=1 || die "untar"
fi
python3 - <<'PY' || die "patch build.ts"
p="/content/oc/packages/cli/script/build.ts"
s=open(p).read()
if 'abi: "android"' not in s:
    s=s.replace('abi?: "musl"','abi?: "musl" | "android"')
    s=s.replace('{ os: "linux", arch: "arm64", abi: "musl" },',
                '{ os: "linux", arch: "arm64", abi: "musl" },\n  { os: "linux", arch: "arm64", abi: "android" },')
    open(p,"w").write(s)
print("PATCH_OK", 'abi: "android"' in s)
PY

# ---------- 2 install ----------
if [ ! -d $OC/packages/cli/node_modules/@opentui/solid ]; then
  say "2 bun install (2.9G, 60-90s)"
  (cd $OC && bun install > $O/install.log 2>&1) || die "bun install (ver $O/install.log)"
fi
[ -d $OC/packages/cli/node_modules/@opentui/solid ] || die "@opentui/solid ausente"

# ---------- 3 plant ----------
say "3 plant paquetes android"
python3 /content/build/plant.py >> $L 2>&1 || die "plant"

# ---------- 4 build ----------
say "4 build (~8 min)"
cd $OC/packages/cli || die "cd cli"
OPENCODE_CHANNEL=latest OPENCODE_VERSION=$VER OPENCODE_TARGET=$TGT BUN_COMPILE_RELEASE=bun-v1.4.5 CI=1 \
  bun run build --single --skip-install >> $L 2>&1 || die "build"
B=$(find $OC/packages/cli/dist -type f -name opencode | head -1)
[ -n "$B" ] || die "sin artefacto"
cp -f "$B" $O/opencode
say "binario $(stat -c%s $O/opencode) B"

# ---------- 5 patchelf ----------
say "5 patchelf"
curl -fsSL -o /content/libopencode-crhandler.so \
  https://github.com/anyelolordmerab-maker/termux-native/releases/download/toolchain/libopencode-crhandler.so || die "crhandler"
[ "$(sha256sum /content/libopencode-crhandler.so | cut -d' ' -f1)" = "ebf59e44e737f2ed4624d6625ca207cd1090facf24a2c9717c6eab0a643a2fc6" ] || die "crhandler sha"
patchelf --add-needed libopencode-crhandler.so --set-rpath '$ORIGIN/../lib/opencode' $O/opencode || die patchelf
chmod +x $O/opencode
cp -f $OC/packages/cli/node_modules/@opentui/core-linux-arm64-musl/libopentui.so $O/libopentui.so || die "libopentui"
readelf -d $O/opencode | grep -q crhandler || die "readelf"

# ---------- 6 tests bionic ----------
say "6 tests qemu-bionic"
command -v qemu-aarch64-static >/dev/null || DEBIAN_FRONTEND=noninteractive apt-get -qq install -y qemu-user-static >/dev/null 2>&1
command -v qemu-aarch64-static >/dev/null || die "qemu"
rm -rf /content/android /content/test
mkdir -p /content/android/system/bin /content/android/system/lib64
curl -fsSL -o /content/bionic.tgz https://github.com/anyelolordmerab-maker/termux-native/releases/download/toolchain/bionic-a14.tgz || die "bionic"
[ "$(sha256sum /content/bionic.tgz | cut -d' ' -f1)" = "425353cb971d80ca52bfe3cb0af3927fa7eec9006a1867048867526d9f594cc0" ] || die "bionic sha"
mkdir -p /tmp/bt && tar xzf /content/bionic.tgz -C /tmp/bt || die "untar bionic"
cp -f /tmp/bt/bin/linker64 /content/android/system/bin/
cp -f /tmp/bt/lib64/*.so /content/android/system/lib64/
mkdir -p /content/test/bin /content/test/lib/opencode
cp -f $O/opencode /content/test/bin/opencode
cp -f $O/libopentui.so /content/test/lib/libopentui.so
cp -f /content/libopencode-crhandler.so /content/test/lib/opencode/
export QEMU="qemu-aarch64-static -L /content/android"

V=$(cd /content/test && $QEMU ./bin/opencode --version 2>&1 | grep -v 'linker\|tzdata')
say "version: $V"
echo "VERSION=$V" > $O/TESTS.txt
(cd /content/test && $QEMU ./bin/opencode --help 2>&1 | grep -q 'USAGE') \
  && echo "HELP=OK" >> $O/TESTS.txt || echo "HELP=FAIL" >> $O/TESTS.txt

pkill -f '[o]pencode serve' 2>/dev/null
(cd /content/test && nohup setsid $QEMU ./bin/opencode serve --hostname 127.0.0.1 --port 4100 > /content/serve.log 2>&1 </dev/null &)
code=000
for i in $(seq 1 45); do
  code=$(curl -s -m 2 -o /dev/null -w '%{http_code}' http://127.0.0.1:4100/app 2>/dev/null)
  [ "$code" = "200" ] && break; sleep 2
done
echo "SERVE_HTTP=$code" >> $O/TESTS.txt
PW=$(grep -o 'server password .*' /content/serve.log | awk '{print $3}')
OPENTUI_LIB_PATH=/content/test/lib/libopentui.so OPENCODE_SERVER_PASSWORD="$PW" \
  python3 /content/build/tui_test.py > $O/tui.txt 2>&1
cat $O/tui.txt >> $O/TESTS.txt
pkill -f '[o]pencode serve' 2>/dev/null
say "$(tr '\n' ' ' < $O/TESTS.txt | cut -c1-200)"

# ---------- 7 empaquetar ----------
say "7 empaquetar"
PKG=$O/opencode-$VER-termux-aarch64
rm -rf $PKG && mkdir -p $PKG/lib/opencode
cp -f $O/opencode $PKG/opencode && chmod 700 $PKG/opencode
cp -f $O/libopentui.so $PKG/lib/libopentui.so
cp -f /content/libopencode-crhandler.so $PKG/lib/opencode/libopencode-crhandler.so
SHA=$(sha256sum $PKG/opencode | cut -d' ' -f1)
SIZE=$(stat -c%s $PKG/opencode)
printf '{"app":"opencode","version":"%s","target":"bionic-aarch64","size":%s,"sha256":"%s","bun":"1.4.5","built":"%s"}\n' \
  "$VER" "$SIZE" "$SHA" "$(date -u +%FT%TZ)" > $PKG/version.json

cat > $PKG/install.sh <<'EOS'
#!/data/data/com.termux/files/usr/bin/bash
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
P="$PREFIX"; BK="$HOME/backups/opencode-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BK"
echo "== backup =="
[ -f "$P/bin/opencode" ] && cp -a "$P/bin/opencode" "$BK/opencode"
[ -d "$HOME/.local/share/opencode" ] && cp -a "$HOME/.local/share/opencode" "$BK/share-opencode"
[ -d "$HOME/.config/opencode" ] && cp -a "$HOME/.config/opencode" "$BK/config-opencode"
echo "backup en $BK"
echo "== instalando =="
mkdir -p "$P/lib/opencode"
cp -f "$HERE/opencode" "$P/bin/opencode.new" && chmod 700 "$P/bin/opencode.new"
cp -f "$HERE/lib/libopentui.so" "$P/lib/libopentui.so"
cp -f "$HERE/lib/opencode/libopencode-crhandler.so" "$P/lib/opencode/"
grep -q 'lib/opencode' "$HOME/.bashrc" 2>/dev/null || echo "export LD_LIBRARY_PATH=\"$P/lib/opencode:\$LD_LIBRARY_PATH\"" >> "$HOME/.bashrc"
if OPENCODE_LIB_PATH= "$P/bin/opencode.new" --version >/dev/null 2>&1; then
  mv -f "$P/bin/opencode.new" "$P/bin/opencode"
  echo "OK: $(OPENCODE_LIB_PATH= "$P/bin/opencode" --version 2>/dev/null | head -1)"
else
  echo "FALLO el arranque; no se toca la instalación actual"
  rm -f "$P/bin/opencode.new"; exit 1
fi
EOS
cat > $PKG/rollback.sh <<'EOS'
#!/data/data/com.termux/files/usr/bin/bash
set -e
BK="${1:-$(ls -d "$HOME"/backups/opencode-* 2>/dev/null | tail -1)}"
[ -n "$BK" ] && [ -f "$BK/opencode" ] || { echo "uso: rollback.sh <carpeta-backup>"; exit 1; }
cp -a "$BK/opencode" "$PREFIX/bin/opencode" && chmod 700 "$PREFIX/bin/opencode"
[ -d "$BK/share-opencode" ] && rm -rf "$HOME/.local/share/opencode" && cp -a "$BK/share-opencode" "$HOME/.local/share/opencode"
[ -d "$BK/config-opencode" ] && rm -rf "$HOME/.config/opencode" && cp -a "$BK/config-opencode" "$HOME/.config/opencode"
echo "restaurado desde $BK"
EOS
chmod 755 $PKG/install.sh $PKG/rollback.sh
(cd $O && tar --zstd -cf opencode-$VER-termux-aarch64.tar.zst $(basename $PKG)) || die "tar.zst"
sha256sum $O/opencode-$VER-termux-aarch64.tar.zst > $O/opencode-$VER-termux-aarch64.tar.zst.sha256
say "pack $(stat -c%s $O/opencode-$VER-termux-aarch64.tar.zst) B"

# ---------- 8 publicar ----------
if [ -n "${GHT:-}" ]; then
  say "8 publicar en GitHub"
  R=anyelolordmerab-maker/termux-native
  TG=opencode-v$VER
  REL=$(curl -s -H "Authorization: Bearer $GHT" https://api.github.com/repos/$R/releases/tags/$TG)
  echo "$REL" | grep -q '"id"' || {
    curl -s -X POST -H "Authorization: Bearer $GHT" -H "Accept: application/vnd.github+json" \
      -d "{\"tag_name\":\"$TG\",\"name\":\"opencode $VER (native Termux aarch64)\",\"body\":\"Bionic aarch64. Bun 1.4.5. libopentui.so musl incluido.\"}" \
      https://api.github.com/repos/$R/releases > $O/rel.json
  }
  UP=$(curl -s -H "Authorization: Bearer $GHT" https://api.github.com/repos/$R/releases/tags/$TG | python3 -c 'import sys,json;print(json.load(sys.stdin)["upload_url"].split("{")[0])')
  for f in opencode-$VER-termux-aarch64.tar.zst opencode-$VER-termux-aarch64.tar.zst.sha256 opencode; do
    for a in $(curl -s -H "Authorization: Bearer $GHT" https://api.github.com/repos/$R/releases/tags/$TG | python3 -c 'import sys,json;print(" ".join(str(x["id"]) for x in json.load(sys.stdin).get("assets",[])))'); do
      curl -s -X DELETE -H "Authorization: Bearer $GHT" https://api.github.com/repos/$R/releases/assets/$a
    done
    curl -sS -X POST -H "Authorization: Bearer $GHT" -H "Content-Type: application/octet-stream" --data-binary "@$O/$f" "$UP?name=$f" > $O/up.json
    grep -q '"state": *"uploaded"' $O/up.json || say "UPLOAD_ERR $f $(head -c 160 $O/up.json)"
  done
  say "publicado $TG"
fi

echo "OK version=$VER size=$SIZE sha256=$SHA" | tee $O/STATUS
say "FIN"
