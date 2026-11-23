#!/usr/bin/env python3
"""Transformacion semantica de @deepseek-ai/dsh -> Termux/Android.

Los parches del repo de referencia son contra rc.1; esta version (rc.5) cambio
el código, así que se aplican transformaciones por patron con asercion: si el
patron no existe, el build falla (nunca silenciosamente "0 parches").
"""
import glob
import os
import re
import sys

ROOT = os.environ["STAGE"]  # .../package/node_modules
TERMUX_PREFIX = "/data/data/com.termux/files/usr"

def find_one(pattern):
    hits = glob.glob(os.path.join(ROOT, pattern), recursive=True)
    if len(hits) != 1:
        raise SystemExit(f"FATAL: expected exactly one file for {pattern}, found {len(hits)}")
    return hits[0]

def edit(path, fn, label):
    s = open(path, encoding="utf-8").read()
    o = s
    s = fn(s)
    if s == o:
        raise SystemExit(f"FATAL: transformation did not apply: {label} ({path})")
    open(path, "w", encoding="utf-8").write(s)
    print("TRANSFORM", label)

def sub(s, old, new, count=1):
    if old not in s:
        raise SystemExit(f"FATAL: anchor missing: {old[:90]!r}")
    return s.replace(old, new, count)

# ---------------------------------------------------------------- terminal bash
p = find_one("**/@deepseek-ai/dsh-terminal-bash/lib/index.js")
def f(s):
    s = sub(s, 'import { Buffer } from "node:buffer";',
            'import { Buffer } from "node:buffer";\nimport { existsSync } from "node:fs";')
    s = sub(s, 'const DEFAULT_BASH_SHELL = "/bin/bash";',
            'const DEFAULT_BASH_SHELL = process.platform === "android"\n'
            f'\t? (existsSync("{TERMUX_PREFIX}/bin/bash") ? "{TERMUX_PREFIX}/bin/bash" : "/system/bin/sh")\n'
            '\t: "/bin/bash";')
    return s
edit(p, f, "terminal-bash android shell")

# ------------------------------------------------------------------- persistence
p = find_one("**/@deepseek-ai/dsh-session-persistence-jsonl/lib/index.js")
def f(s):
    m = re.search(r'import \{([^}]+)\} from "node:fs/promises";', s)
    if not m or "rename" not in m.group(1):
        if not m:
            raise SystemExit("FATAL: fs/promises import not found")
        s = s.replace(m.group(0), 'import {' + m.group(1).rstrip() + ', rename } from "node:fs/promises";', 1)
    s = sub(s, '\t\t\tawait link(tmp, finalPath);\n\t\t\tlinked = true;',
            '\t\t\ttry {\n'
            '\t\t\t\tawait link(tmp, finalPath);\n'
            '\t\t\t\tlinked = true;\n'
            '\t\t\t} catch (error) {\n'
            '\t\t\t\tif (error?.code === "EACCES" || error?.code === "EPERM") await rename(tmp, finalPath);\n'
            '\t\t\t\telse throw error;\n'
            '\t\t\t}')
    return s
edit(p, f, "session-persistence link->rename fallback")

# --------------------------------------------------------------- subprocess local
p = find_one("**/@deepseek-ai/dsh-subprocess-local/lib/runner-launch-*.js")
def f(s):
    s = sub(s, 'if (platform === "linux") return new LinuxProcessInspector(arch, internals);',
            'if (platform === "linux" || platform === "android") return new LinuxProcessInspector(arch, internals);')
    s = sub(s, 'if (directSettled && platform === "linux") {',
            'if (directSettled && (platform === "linux" || platform === "android")) {')
    return s
edit(p, f, "subprocess android inspector")

p = find_one("**/@deepseek-ai/dsh-subprocess-local/lib/index.js")
def f(s):
    s = sub(s, '\t\tif (platform === "linux") {\n\t\t\tconst decision = this.linuxScope.select();',
            '\t\tif (platform === "linux" || platform === "android") {\n\t\t\tconst decision = this.linuxScope.select();')
    return s
edit(p, f, "subprocess android containment")

# ------------------------------------------------------------- directory picker
p = find_one("**/@deepseek-ai/dsh-host-directory-picker-native/lib/index.js")
def f(s):
    return sub(s, '\tif (platform === "linux") {\n\t\ttry {\n\t\t\treturn outputPath((await run("zenity", [',
                '\tif (platform === "linux" || platform === "android") {\n\t\ttry {\n\t\t\treturn outputPath((await run("zenity", [')
edit(p, f, "directory-picker android")

# ---------------------------------------------------------------------- workspace
p = find_one("**/@deepseek-ai/dsh-workspace/lib/index.js")
def f(s):
    return sub(s, '\t\t\tif (!await this.sessionKnown(sessionId)) throw new WorkspaceUnknownSessionError(sessionId, "archive");',
               '\t\t\t// Termux: archiving must not require the session to exist on disk')
edit(p, f, "workspace archive without sessionKnown")

# ------------------------------------------------------------------- sandbox local
p = find_one("**/@deepseek-ai/dsh-sandbox-local/lib/index.js")
def f(s):
    s = sub(s, 'const PLATFORM_CHAINS = {\n\tlinux: ["bwrap", "landlock"],',
            'const PLATFORM_CHAINS = {\n\tlinux: ["bwrap", "landlock"],\n\tandroid: ["bwrap", "landlock"],')
    return s
edit(p, f, "sandbox-local native abwrap chain")

# -------------------------------------------------------------------- ripgrep util
p = find_one("**/@deepseek-ai/dsh-util-ripgrep/lib/index.js")
def f(s):
    s = sub(s, 'import { join, parse } from "node:path";',
            'import { join, parse } from "node:path";\nimport { createRequire } from "node:module";')
    s = sub(s, '\t\tconst dependency = (await import("@vscode/ripgrep")).rgPath;',
            '\t\tlet dependency;\n'
            '\t\tif (process.platform === "android") {\n'
            '\t\t\tconst require = createRequire(import.meta.url);\n'
            '\t\t\ttry {\n'
            '\t\t\t\tdependency = require.resolve(`@vscode/ripgrep-${process.platform}-${process.arch}/bin/rg`);\n'
            '\t\t\t} catch {\n'
            f'\t\t\t\tconst candidates = [process.env.RIPGREP_BIN, "{TERMUX_PREFIX}/bin/rg", "/system/bin/rg"];\n'
            '\t\t\t\tfor (const candidate of candidates) if (candidate && existsSync(candidate)) { dependency = candidate; break; }\n'
            '\t\t\t\tif (!dependency) throw new Error(`No ripgrep for ${process.platform}-${process.arch}`);\n'
            '\t\t\t}\n'
            '\t\t} else {\n'
            '\t\t\tdependency = (await import("@vscode/ripgrep")).rgPath;\n'
            '\t\t}')
    return s
edit(p, f, "util-ripgrep android shim")

# ---------------------------------------------------- sandbox por defecto FULL
# El usuario quiere acceso completo nativo (no proot, no jaulas de directorios).
# danger-full-access hace que el backend NO confine y lance el argv original.
_pol = glob.glob(os.path.join(ROOT, "**/@deepseek-ai/dsh-sandbox-policy/lib/index.js"), recursive=True)
if not _pol:
    raise SystemExit("FATAL: dsh-sandbox-policy not found")
for _p in _pol:
    _t = open(_p, encoding="utf-8").read()
    if '.default("read-only")' in _t:
        _t = _t.replace('.default("read-only")', '.default("danger-full-access")')
        open(_p, "w", encoding="utf-8").write(_t)
        print("TRANSFORM sandbox default full access", _p.replace(ROOT, ""))
    elif '.default("danger-full-access")' not in _t:
        raise SystemExit(f"FATAL: sandbox default anchor missing in {_p}")

print("TRANSFORM_ALL_OK")
