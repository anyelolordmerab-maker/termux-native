#!/usr/bin/env python3
"""Planta los paquetes de plataforma android que opencode pide al bundlear.
Idempotente. Requiere /content/pty/package/bin/opencode-pty o lo descarga de npm.
"""
import os, json, shutil, glob, subprocess, sys

OC = "/content/oc"
PTY_SRC = "/content/pty/package/bin/opencode-pty"
OT_VER = "0.8.4"
CACHE = "/content/ot/pkg"


def sh(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True, timeout=300)
    return r.stdout + r.stderr


def ensure_pty():
    if os.path.isfile(PTY_SRC):
        return
    os.makedirs("/content/pty", exist_ok=True)
    sh("curl -fsSL -o /content/pty/pty.tgz https://registry.npmjs.org/@opencode/pty-linux-arm64-musl/-/pty-linux-arm64-musl-0.6.0.tgz"
       " && mkdir -p /content/pty && tar xzf /content/pty/pty.tgz -C /content/pty")
    if not os.path.isfile(PTY_SRC):
        print("FATAL: no pty"); sys.exit(3)


def ensure_otui():
    if os.path.isfile(CACHE + "/package.json"):
        return
    os.makedirs("/content/ot", exist_ok=True)
    r = sh(f"curl -fsSL -o /content/ot/ot.tgz https://registry.npmjs.org/@opentui/core-linux-arm64-musl/-/core-linux-arm64-musl-{OT_VER}.tgz"
           " && rm -rf /content/ot/x && mkdir -p /content/ot/x && tar xzf /content/ot/ot.tgz -C /content/ot/x"
           f" && rm -rf {CACHE} && cp -r /content/ot/x/package {CACHE}")
    if not os.path.isfile(CACHE + "/package.json"):
        print("FATAL: no opentui", r[:300]); sys.exit(4)


ensure_pty(); ensure_otui()

roots = [OC + "/node_modules", OC + "/node_modules/.bun/node_modules", OC + "/packages/cli/node_modules"]
for pat in ["@opencode+pty@*", "@opentui+core@*"]:
    roots += glob.glob(f"{OC}/node_modules/.bun/{pat}/node_modules")
roots = [r for r in roots if os.path.isdir(r)]


def mk_pty(name):
    for r in roots:
        d = os.path.join(r, "@opencode", name)
        os.makedirs(d + "/bin", exist_ok=True)
        shutil.copy2(PTY_SRC, d + "/bin/opencode-pty")
        os.chmod(d + "/bin/opencode-pty", 0o755)
        json.dump({"name": "@opencode/" + name, "version": "0.6.0", "os": ["android", "linux"],
                   "cpu": ["arm64"], "bin": {"opencode-pty": "./bin/opencode-pty"}},
                  open(d + "/package.json", "w"))


def mk_ot(name):
    for r in roots:
        d = os.path.join(r, "@opentui", name)
        if os.path.isdir(d):
            shutil.rmtree(d)
        shutil.copytree(CACHE, d)
        p = d + "/package.json"
        j = json.load(open(p)); j["name"] = "@opentui/" + name; j["os"] = ["android", "linux"]
        json.dump(j, open(p, "w"))


STUBS = {
    "@parcel/watcher-linux-arm64-android": "watcher.node",
    "@lydell/node-pty-linux-arm64-android": "pty.node",
    "@ff-labs/fff-bin-linux-arm64-android": "fff",
    "@yuuang/ffi-rs-linux-arm64-android": "ffi.node",
    "@lydell/node-pty-linux-arm64": "pty.node",
    "@parcel/watcher-linux-arm64": "watcher.node",
}


def mk_stubs():
    for r in roots:
        for name, f in STUBS.items():
            d = os.path.join(r, name)
            os.makedirs(d, exist_ok=True)
            json.dump({"name": name, "version": "1.0.0", "os": ["android", "linux"], "cpu": ["arm64"],
                       "main": "index.js"}, open(d + "/package.json", "w"))
            open(d + "/index.js", "w").write("module.exports=null\n")
            open(d + "/" + f, "wb").write(b"")


mk_pty("pty-linux-arm64-android"); mk_pty("pty-linux-arm64-musl")
mk_ot("core-linux-arm64-android"); mk_ot("core-linux-arm64-musl")
mk_stubs()

# parche opentui: android -> linux + musl
OLD = 'function getCurrentNodeAssetTarget() {\n  const libc = process.env.OPENTUI_LIBC;'
NEW = ('function getCurrentNodeAssetTarget() {\n'
       '  if (process.platform === "android") {\n'
       '    return { platform: "linux", arch: process.arch, libc: "musl" };\n'
       '  }\n'
       '  const libc = process.env.OPENTUI_LIBC;')
MARK = 'return { platform: "linux", arch: process.arch, libc: "musl" };'
patched = 0
for p in glob.glob("/content/oc/**/chunk-bun-*.js", recursive=True):
    s = open(p, encoding="utf-8", errors="replace").read()
    if MARK in s:
        continue
    if OLD in s:
        open(p, "w", encoding="utf-8").write(s.replace(OLD, NEW, 1))
        patched += 1

need = ["@opencode/pty-linux-arm64-android", "@opentui/core-linux-arm64-android",
        "@parcel/watcher-linux-arm64-android", "@lydell/node-pty-linux-arm64-android",
        "@ff-labs/fff-bin-linux-arm64-android", "@yuuang/ffi-rs-linux-arm64-android",
        "@opentui/solid"]
bad = [n for n in need if not any(os.path.isdir(r + "/" + n) for r in roots)]
print(f"ROOTS={len(roots)} PATCHED={patched} MISSING={bad}")
sys.exit(2 if bad else 0)
