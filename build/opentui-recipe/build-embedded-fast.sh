#!/bin/bash
# Build embebido rápido de opencode 2.3.2 nativo (aarch64-bionic) con libopentui.so DENTRO.
# Basado en pipeline probado de Hope2333/opencode-termux + nuestros hallazgos.
# Fases con ficheros de estado: reanudable tras desconexión de Colab.
set -uo pipefail
VER="2.3.2"
OC=/content/oc
O=/content/out
L=$O/emb.log
mkdir -p $O /content/bin
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a $L; }
: > $L

# 0) bun 1.4.5
if [ ! -x /content/bin/bun ]; then
  say "0 bun 1.4.5"
  curl -fsSL -o /tmp/b.zip https://github.com/oven-sh/bun/releases/download/bun-v1.4.5/bun-linux-x64.zip
  (cd /tmp && unzip -oq b.zip && cp bun-linux-x64/bun /content/bin/bun && chmod +x /content/bin/bun)
fi
export PATH=/content/bin:$PATH
bun -v >/dev/null || { say "FATAL bun"; exit 1; }

# 0b) .so bionic (SHA 50f8e358) desde release
SO=/content/libopentui.bionic.so
if [ ! -f "$SO" ] || [ "$(sha256sum $SO|cut -d' ' -f1)" != "50f8e358cd42dd0ec928be256ac2a217cc9a26c5547d7d30f9becf8b8d2f8b97" ]; then
  say "0b .so bionic desde release"
  curl -fsSL -o "$SO" https://github.com/anyelolordmerab-maker/termux-native/releases/download/opencode-v2.3.2/libopentui.android-arm64.so
fi
[ "$(sha256sum $SO|cut -d' ' -f1)" = "50f8e358cd42dd0ec928be256ac2a217cc9a26c5547d7d30f9becf8b8d2f8b97" ] || { say "FATAL so sha"; exit 1; }

# 1) source 2.3.2
if [ ! -f $OC/packages/cli/script/build.ts ]; then
  say "1 source"
  curl -fsSL -o /tmp/oc.tgz https://codeload.github.com/anomalyco/opencode/tar.gz/refs/tags/v$VER
  mkdir -p $OC && tar xzf /tmp/oc.tgz -C $OC --strip-components=1
fi

# 2) bun install
if [ ! -d $OC/node_modules/@opentui/solid ]; then
  say "2 bun install"
  (cd $OC && bun install > $O/install.log 2>&1) || { say "FATAL install"; exit 1; }
fi

# 3) parche build.ts: anadir target abi android
python3 - <<'PY'
p='/content/oc/packages/cli/script/build.ts'
s=open(p).read()
if 'abi: "android"' not in s:
    s=s.replace('abi?: "musl"','abi?: "musl" | "android"')
    s=s.replace('{ os: "linux", arch: "arm64", abi: "musl" },',
                '{ os: "linux", arch: "arm64", abi: "musl" },\n  { os: "linux", arch: "arm64", abi: "android" },')
    open(p,'w').write(s)
print('PATCH build.ts', 'abi: "android"' in s)
PY

# 4) plantar .so bionic en @opentui/core-linux-arm64 (5 raices) + helpers
say "4 plant"
python3 /content/plant-embedded.py || { say "FATAL plant"; exit 1; }

# 4b) plantar pty (binario estatico de npm) - FALTABA en el intento anterior
say "4b plant pty"
python3 /content/plant-pty.py || { say "FATAL pty"; exit 1; }

# 5) fix FFI (patch-ffi-pointer) en los 2 chunks
say "5 fix FFI"
python3 - <<'PYF' || { say "FATAL ffi"; exit 1; }
import glob, subprocess
base='/content/oc/node_modules/.bun/@opentui+core@0.8.4+eff4d38d6a4a2cd9/node_modules/@opentui/core'
chunks=glob.glob(base+'/chunk-bun-*.js')+glob.glob(base+'/chunk-node-*.js')
n=0
for c in chunks:
    if 'POINTER_UNSAFE' not in open(c,encoding='utf-8',errors='replace').read(): continue
    r=subprocess.run(['python3','/content/patch-ffi.py',c],capture_output=True,text=True,timeout=30)
    if r.returncode!=0: raise SystemExit('ffi patch failed: '+c)
    n+=1
print('FFI chunks patched',n)
PYF

# 6) build embebido
say "6 bun --compile embebido (~6-8 min)"
cd $OC/packages/cli || exit 1
OPENCODE_CHANNEL=latest OPENCODE_VERSION=$VER OPENCODE_TARGET=linux-arm64-android \
  BUN_COMPILE_RELEASE=bun-v1.4.5 bun run build --single --skip-install >> $L 2>&1
rc=$?
[ $rc -eq 0 ] || { say "FATAL build rc=$rc"; exit 1; }
B=$(find $OC/packages/cli/dist -type f -name opencode | head -1)
cp -f "$B" $O/opencode-embedded
say "OK size=$(stat -c%s $O/opencode-embedded) sha=$(sha256sum $O/opencode-embedded|cut -d' ' -f1)"
echo "OK $(stat -c%s $O/opencode-embedded)" > $O/STATUS
