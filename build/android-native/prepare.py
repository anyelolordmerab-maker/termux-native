#!/usr/bin/env python3
"""Prepara opencode 2.3.2 para un build Bun nativo Android (bionic, aarch64).

Parchea los loaders JS/TS para aceptar process.platform === "android" y planta
los paquetes nativos Android reales:
  - @opentui/core-android-arm64      (libopentui.so bionic)
  - @parcel/watcher-android-arm64    (watcher.node de npm)
  - @ff-labs/fff-bin-android-arm64   (libfff_c.so de npm)
  - @opencode/pty-android-arm64      (opencode-pty estatico musl)
  - bun-pty                           (librust_pty_arm64.so compilado con NDK)

Cada parche comprueba que aplicó; un no-op se trata como error.
"""
import glob
import json
import os
import re
import shutil
import sys

OC = os.environ.get("OC", os.getcwd())
OPENTUI_SO = os.environ["OPENTUI_SO"]
BUNPTY_SO = os.environ["BUNPTY_SO"]
WATCHER_DIR = os.environ["WATCHER_DIR"]
FFF_DIR = os.environ["FFF_DIR"]
IROH_DIR = os.environ.get("IROH_DIR", "")
OPENTUI_VERSION = os.environ.get("OPENTUI_VERSION", "0.8.4")
PTY_BIN = os.environ["PTY_BIN"]


def die(msg):
    print("FATAL:", msg, flush=True)
    sys.exit(1)


def rm(d):
    if os.path.islink(d) or os.path.isfile(d):
        os.unlink(d)
    elif os.path.isdir(d):
        shutil.rmtree(d)


def read(p):
    return open(p, encoding="utf-8").read()


def write(p, s):
    open(p, "w", encoding="utf-8").write(s)


def patch(path, fn, label):
    s = read(path)
    out = fn(s)
    if out == s:
        die(f"patch did not apply: {label} ({path})")
    write(path, out)
    print("PATCH", label, flush=True)


# ---------------------------------------------------------------- build.ts
bt = os.path.join(OC, "packages/cli/script/build.ts")


def patch_build(s):
    if '{ os: "android", arch: "arm64" }' not in s:
        anchor = '  { os: "linux", arch: "arm64" },\n'
        if anchor not in s:
            die("allTargets anchor")
        s = s.replace(anchor, anchor + '  { os: "android", arch: "arm64" },\n', 1)

    if "function compileTarget(" not in s:
        anchor = "function targetName(item: (typeof allTargets)[number]) {"
        if anchor not in s:
            die("targetName anchor")
        fn = (
            "function compileTarget(item: (typeof allTargets)[number]) {\n"
            '  if (item.os === "android") return `bun-linux-${item.arch}-android`\n'
            '  return targetName(item).replace(binary, "bun")\n'
            "}\n\n"
        )
        s = s.replace(anchor, fn + anchor, 1)

    old = 'target: target.replace(binary, "bun") as Bun.Build.CompileTarget,'
    if old not in s:
        die("compile.target anchor")
    s = s.replace(old, 'target: compileTarget(item) as Bun.Build.CompileTarget,', 1)

    old = 'const platform = item.os === "win32" ? "windows" : item.os'
    if old not in s:
        die("compileExecutable platform anchor")
    s = s.replace(
        old,
        'const platform = item.os === "android" ? "linux" : item.os === "win32" ? "windows" : item.os',
        1,
    )

    old = '    item.abi,\n    item.avx2 === false ? "baseline" : undefined,'
    if old not in s:
        die("compileExecutable abi anchor")
    s = s.replace(
        old,
        '    item.os === "android" ? "android" : item.abi,\n    item.avx2 === false ? "baseline" : undefined,',
        1,
    )

    # Android: Bun no embute de forma fiable un paquete cuyo "main" ES el .node.
    # Lo importamos como archivo (type: "file") y el binding lo carga por ruta.
    iroh_anchor = '  const irohBindingPlugin: BunPlugin = {'
    if iroh_anchor not in s:
        die("irohBindingPlugin anchor")
    if 'const irohAsset =' not in s:
        iroh_decl = (
            '  // Android: el .node se embute como archivo y se carga por ruta.\n'
            '  const irohAsset = item.os === "android" ? "@number0/iroh-android-arm64/iroh.android-arm64.node" : null\n'
        )
        s = s.replace(iroh_anchor, iroh_decl + iroh_anchor, 1)
    iroh_old = '        contents: `export default async () => ${irohPackage ? `require(${JSON.stringify(irohPackage)})` : "undefined"}`;'
    iroh_new = '        contents: irohAsset ? `import irohPath from ${JSON.stringify(irohAsset)} with { type: "file" }; export default async () => require(irohPath)` : `export default async () => ${irohPackage ? `require(${JSON.stringify(irohPackage)})` : "undefined"}`;'
    if iroh_old not in s:
        iroh_old = iroh_old[:-1] + ','
        iroh_new = iroh_new[:-1] + ','
    if iroh_old not in s:
        die("irohBinding contents anchor")
    s = s.replace(iroh_old, iroh_new, 1)
    return s


patch(bt, patch_build, "build.ts android target")

# ------------------------------------------------------------- opencode-pty
op = os.path.join(OC, "packages/cli/script/opencode-pty.ts")


def patch_pty_ts(s):
    old = 'if (target.platform !== "darwin" && target.platform !== "linux" && target.platform !== "win32") return undefined'
    if old not in s:
        if 'target.platform !== "android"' in s:
            return s
        die("opencode-pty platform anchor")
    return s.replace(
        old,
        'if (target.platform !== "darwin" && target.platform !== "linux" && target.platform !== "win32" && target.platform !== "android") return undefined',
        1,
    )


patch(op, patch_pty_ts, "opencode-pty android")

# --------------------------------------------------------------- opentui
cores = glob.glob(os.path.join(OC, "node_modules/.bun/@opentui+core@*/node_modules/@opentui/core"))
cores += [p for p in [os.path.join(OC, "node_modules/@opentui/core")] if os.path.isdir(p)]
cores = list(dict.fromkeys(cores))
if not cores:
    die("opentui core not found")

WIN32_LOADER = re.compile(
    r'(?P<i>[ \t]*)if\s*\(\s*process\.platform\s*===\s*"win32"\s*\)\s*\{\s*'
    r'if\s*\(\s*process\.arch\s*===\s*"x64"\s*\)\s*\{'
)

FFI_ANCHOR = re.compile(
    r"if \(pointer > BigInt\(Number\.MAX_SAFE_INTEGER\)\) \{\s*"
    r"throw new Error\(POINTER_UNSAFE\);\s*\}",
    re.S,
)
FFI_REPL = (
    "if (pointer > BigInt(Number.MAX_SAFE_INTEGER)) { "
    "return pointer; /* OT_PTR_BIGINT: bionic tagged pointer, bun FFI takes BigInt */ }"
)

loader_patched = 0
ffi_patched = 0
for core in cores:
    for chunk in glob.glob(os.path.join(core, "chunk-*.js")):
        s = read(chunk)
        o = s

        # 1) NATIVE_FILE_NAMES.android (so the descriptor accepts android-arm64)
        if 'android: "libopentui.so"' not in s and re.search(r'win32\s*:\s*"opentui\.dll"', s):
            s2 = re.sub(r'(win32\s*:\s*"opentui\.dll")', r'\1, android: "libopentui.so"', s, count=1)
            if s2 == s:
                die(f"NATIVE_FILE_NAMES anchor in {chunk}")
            s = s2

        # 2) FFI: bionic tagged pointers are > 2^53, hand the BigInt through.
        if "OT_PTR_BIGINT" not in s:
            hits = FFI_ANCHOR.findall(s)
            if hits:
                if len(hits) != 1:
                    die(f"FFI pointer anchor expected 1, found {len(hits)} in {chunk}")
                s = FFI_ANCHOR.sub(FFI_REPL, s, count=1)
                ffi_patched += 1

        # 3) Bun native-library resolver: add the android arm.
        if os.path.basename(chunk).startswith("chunk-bun-") and 'import("@opentui/core-android-arm64")' not in s:
            m = WIN32_LOADER.search(s)
            if m:
                i = m.group("i")
                arm = (
                    f'{i}if (process.platform === "android") {{\n'
                    f'{i}  if (process.arch === "arm64") {{\n'
                    f'{i}    return (await import("@opentui/core-android-arm64")).default;\n'
                    f'{i}  }}\n'
                    f'{i}}}\n'
                    f'{i}'
                )
                s = s[: m.start()] + arm + s[m.start():]
                loader_patched += 1

        if s != o:
            write(chunk, s)
            print("PATCH opentui", chunk, flush=True)

if loader_patched == 0:
    die("no opentui bun loader patched")
if ffi_patched == 0:
    die("no opentui FFI chunk patched")

# ---------------------------------------------------------------- fff-bun
ffbs = glob.glob(os.path.join(OC, "node_modules/.bun/@ff-labs+fff-bun@*/node_modules/@ff-labs/fff-bun"))
ffbs += [p for p in [os.path.join(OC, "node_modules/@ff-labs/fff-bun")] if os.path.isdir(p)]
ffbs = list(dict.fromkeys(ffbs))
if not ffbs:
    die("fff-bun not found")

fff_patched = 0
for d in ffbs:
    emb = os.path.join(d, "src/embedded.ts")
    if not os.path.isfile(emb):
        continue
    s = read(emb)
    if 'process.platform === "android"' in s:
        continue
    anchor = '  if (process.platform === "linux") {'
    if anchor not in s:
        die(f"fff embedded anchor in {emb}")
    arm = (
        '  if (process.platform === "android") {\n'
        "    return importFile(\n"
        '      import(`@ff-labs/fff-bin-android-${process.arch}/libfff_c.so`, { with: { type: "file" } }),\n'
        "    );\n"
        "  }\n\n"
    )
    write(emb, s.replace(anchor, arm + anchor, 1))
    fff_patched += 1
    print("PATCH fff-bun android", emb, flush=True)

if fff_patched == 0:
    die("no fff-bun embedded.ts patched")

# ------------------------------------------------------------ pty socket dir
idx = os.path.join(OC, "packages/cli/src/index.ts")


def patch_index(s):
    shebang = "#!/usr/bin/env bun\n"
    if "OPENCODE_PTY_SOCKET_DIR" not in s:
        line = (
            "\n// Android: the pty daemon is a linux binary; /tmp does not exist.\n"
            "if (process.platform === \"android\" && !process.env.OPENCODE_PTY_SOCKET_DIR)\n"
            "  process.env.OPENCODE_PTY_SOCKET_DIR = process.env.TMPDIR\n"
        )
        s = shebang + line + s[len(shebang):] if s.startswith(shebang) else line + s
    return s


patch(idx, patch_index, "pty socket dir")

# ------------------------------------------------------------------ plant
def rm(d):
    if os.path.islink(d) or os.path.isfile(d):
        os.unlink(d)
    elif os.path.isdir(d):
        shutil.rmtree(d)


def roots():
    r = [
        os.path.join(OC, "node_modules"),
        os.path.join(OC, "node_modules/.bun/node_modules"),
        os.path.join(OC, "packages/cli/node_modules"),
        os.path.join(OC, "packages/core/node_modules"),
    ]
    r += glob.glob(os.path.join(OC, "node_modules/.bun/@opentui+core@*/node_modules"))
    r += glob.glob(os.path.join(OC, "node_modules/.bun/@ff-labs+fff-bun@*/node_modules"))
    r += glob.glob(os.path.join(OC, "node_modules/.bun/@opencode+pty@*/node_modules"))
    r += glob.glob(os.path.join(OC, "node_modules/.bun/@parcel+watcher@*/node_modules"))
    r += glob.glob(os.path.join(OC, "node_modules/.bun/bun-pty@*/node_modules"))
    return list(dict.fromkeys([x for x in r if os.path.isdir(x)]))


def plant_core():
    n = 0
    for r in roots():
        d = os.path.join(r, "@opentui/core-android-arm64")
        os.makedirs(d, exist_ok=True)
        shutil.copy2(OPENTUI_SO, os.path.join(d, "libopentui.so"))
        write(
            os.path.join(d, "index.bun.js"),
            'const module = await import("./libopentui.so", { with: { type: "file" } })\n\n'
            "export default module.default\n",
        )
        write(
            os.path.join(d, "index.js"),
            'import { fileURLToPath } from "node:url"\n'
            'export default fileURLToPath(new URL("./libopentui.so", import.meta.url))\n',
        )
        json.dump(
            {
                "name": "@opentui/core-android-arm64",
                "version": OPENTUI_VERSION,
                "type": "module",
                "main": "index.js",
                "module": "index.js",
                "exports": {".": {"bun": "./index.bun.js", "import": "./index.js"}},
                "os": ["linux"],
                "cpu": ["arm64"],
            },
            open(os.path.join(d, "package.json"), "w"),
        )
        n += 1
    return n


def plant_dir(name, src):
    if not os.path.isdir(src):
        die(f"missing vendor dir for {name}: {src}")
    n = 0
    for r in roots():
        d = os.path.join(r, name)
        rm(d)
        shutil.copytree(src, d)
        pkgp = os.path.join(d, "package.json")
        pkg = json.load(open(pkgp))
        pkg["os"] = ["linux"]
        pkg["cpu"] = ["arm64"]
        json.dump(pkg, open(pkgp, "w"))
        n += 1
    return n


def plant_pty():
    n = 0
    for r in roots():
        d = os.path.join(r, "@opencode/pty-android-arm64")
        os.makedirs(os.path.join(d, "bin"), exist_ok=True)
        shutil.copy2(PTY_BIN, os.path.join(d, "bin/opencode-pty"))
        os.chmod(os.path.join(d, "bin/opencode-pty"), 0o755)
        json.dump(
            {
                "name": "@opencode/pty-android-arm64",
                "version": "0.6.0",
                "os": ["linux"],
                "cpu": ["arm64"],
                "bin": {"opencode-pty": "./bin/opencode-pty"},
            },
            open(os.path.join(d, "package.json"), "w"),
        )
        n += 1
    return n


def plant_bunpty():
    pat = os.path.join(OC, "node_modules/**/rust-pty/target/release/librust_pty_arm64.so")
    try:
        found = glob.glob(pat, recursive=True, include_hidden=True)
    except TypeError:
        found = glob.glob(pat, recursive=True) + glob.glob(os.path.join(OC, "node_modules/.bun/*/node_modules/bun-pty/rust-pty/target/release/librust_pty_arm64.so"))
    n = 0
    for p in found:
        shutil.copy2(BUNPTY_SO, p)
        n += 1
    if n == 0:
        die("bun-pty librust_pty_arm64.so not found")
    return n


print("PLANT core", plant_core(), flush=True)
print("PLANT watcher", plant_dir("@parcel/watcher-android-arm64", WATCHER_DIR), flush=True)
print("PLANT fff", plant_dir("@ff-labs/fff-bin-android-arm64", FFF_DIR), flush=True)
print("PLANT pty", plant_pty(), flush=True)
if IROH_DIR:
    print("PLANT iroh", plant_dir("@number0/iroh-android-arm64", IROH_DIR), flush=True)
print("PLANT bun-pty", plant_bunpty(), flush=True)

print("PREPARE OK", flush=True)
