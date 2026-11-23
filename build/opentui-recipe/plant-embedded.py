#!/usr/bin/env python3
"""Planta la .so bionic en @opentui/core-linux-arm64 (la clave que getNodeAssets pide
para target linux/arm64 sin libc) en TODAS las raices node_modules/.bun, mas helpers."""
import os, json, shutil, glob

OC = '/content/oc'
SO = '/content/libopentui.bionic.so'

# todas las raices donde bun isolated linker puede resolver @opentui/*
roots = [
    OC + '/node_modules',
    OC + '/node_modules/.bun/node_modules',
    OC + '/packages/cli/node_modules',
]
for pat in ['@opentui+core@*', '@opentui+core-linux-arm64@*', '@opentui+solid@*']:
    roots += glob.glob(OC + '/node_modules/.bun/' + pat + '/node_modules')
roots = list(dict.fromkeys([r for r in roots if os.path.isdir(r)]))

def plant_core_so():
    n = 0
    for r in roots:
        d = os.path.join(r, '@opentui', 'core-linux-arm64')
        os.makedirs(d, exist_ok=True)
        shutil.copy2(SO, d + '/libopentui.so')
        pkg = d + '/package.json'
        obj = {"name": "@opentui/core-linux-arm64", "version": "0.8.4",
               "os": ["linux"], "cpu": ["arm64"], "main": "index.js"}
        if os.path.exists(pkg):
            try:
                old = json.load(open(pkg)); obj.update({k: v for k, v in old.items() if k in ('version',)})
            except Exception:
                pass
        json.dump(obj, open(pkg, 'w'))
        open(d + '/index.js', 'w').write('module.exports = {};\n')
        n += 1
    return n

def plant_helper(name, files):
    n = 0
    for r in roots:
        d = os.path.join(r, name)
        os.makedirs(d, exist_ok=True)
        json.dump({"name": name, "version": "1.0.0", "os": ["linux"], "cpu": ["arm64"],
                   "main": "index.js"}, open(d + '/package.json', 'w'))
        open(d + '/index.js', 'w').write('module.exports = null;\n')
        for f in files:
            open(d + '/' + f, 'wb').write(b'')
        n += 1
    return n

n = plant_core_so()
h1 = plant_helper('@lydell/node-pty-linux-arm64', ['pty.node'])
h2 = plant_helper('@parcel/watcher-linux-arm64-glibc', ['watcher.node'])
h3 = plant_helper('@ff-labs/fff-bin-linux-arm64-gnu', ['fff'])
h4 = plant_helper('@yuuang/ffi-rs-linux-arm64-gnu', ['ffi.node'])
# stubs -android (el target linux-arm64-android los pide con sufijo android)
h5 = plant_helper('@parcel/watcher-linux-arm64-android', ['watcher.node'])
h6 = plant_helper('@lydell/node-pty-linux-arm64-android', ['pty.node'])
h7 = plant_helper('@ff-labs/fff-bin-linux-arm64-android', ['fff'])
h8 = plant_helper('@yuuang/ffi-rs-linux-arm64-android', ['ffi.node'])
h9 = plant_helper('@parcel/watcher-linux-arm64', ['watcher.node'])

# verificar que la .so este en la raiz principal
primary = OC + '/node_modules/@opentui/core-linux-arm64/libopentui.so'
print('ROOTS', len(roots), 'CORE_PLANTED', n,
      'PRIMARY_EXISTS', os.path.exists(primary),
      'PRIMARY_SHA', __import__('hashlib').sha256(open(primary,'rb').read()).hexdigest()[:16] if os.path.exists(primary) else 'NONE')
