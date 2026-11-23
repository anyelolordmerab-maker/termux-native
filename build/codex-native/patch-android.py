#!/usr/bin/env python3
"""Parches Android/Termux para Codex rust-v0.171.0. Idempotente y con aserciones."""
import os
import re
import sys

SRC = os.environ.get("CODEX_SRC", sys.argv[1] if len(sys.argv) > 1 else "/content/codex")
RS = os.path.join(SRC, "codex-rs")


def edit(rel, fn, label, required=True):
    p = os.path.join(RS, rel)
    if not os.path.isfile(p):
        if required:
            raise SystemExit(f"FATAL: missing {rel}")
        print("SKIP", label, "(file missing)")
        return
    s = open(p, encoding="utf-8").read()
    o = s
    s = fn(s)
    if s == o:
        if required:
            raise SystemExit(f"FATAL: patch did not apply: {label} ({rel})")
        print("SKIP", label, "(already applied?)")
        return
    open(p, "w", encoding="utf-8").write(s)
    print("PATCH", label)


# 1) sandbox por defecto: acceso completo (sin seccomp/bwrap en Android)
edit("protocol/src/config_types.rs", lambda s: s.replace(
    '''#[serde(rename = "read-only")]
    #[default]
    ReadOnly,''',
    '''#[serde(rename = "read-only")]
    ReadOnly,''', 1).replace(
    '''#[serde(rename = "danger-full-access")]
    DangerFullAccess,''',
    '''#[serde(rename = "danger-full-access")]
    #[default]
    DangerFullAccess,''', 1), "default sandbox danger-full-access")

# 2) DNS: usar bionic getaddrinfo en vez de /etc/resolv.conf
edit("network-proxy/src/lib.rs", lambda s: s.replace(
    '#[cfg(target_os = "macos")]', '#[cfg(any(target_os = "macos", target_os = "android"))]'),
    "system_dns on android")
edit("network-proxy/src/connect_policy.rs", lambda s: s.replace(
    '#[cfg(target_os = "macos")]', '#[cfg(any(target_os = "macos", target_os = "android"))]'),
    "connect_policy system dns on android")

# 3) OpenSSL vendored para el target Android
edit("core/Cargo.toml", lambda s: s if '[target.aarch64-linux-android.dependencies]' in s else s + '''
[target.aarch64-linux-android.dependencies]
openssl-sys = { workspace = true, features = ["vendored"] }
''', "openssl vendored for android")

# 4) file locking: Android/bionic no implementa flock -> Unsupported.
#    Tratarlo como "lock adquirido" para no romper auth/history.
edit("login/src/auth/storage_commit.rs", lambda s: s.replace(
    "                Err(error) => return Err(error.into()),",
    "                Err(TryLockError::Error(error))\n"
    "                    if error.kind() == std::io::ErrorKind::Unsupported =>\n"
    "                {\n                    return Ok(file)\n                }\n"
    "                Err(error) => return Err(error.into()),", 1),
    "auth storage lock compat")

edit("rollout/src/writer_lock.rs", lambda s: s.replace(
    "                Err(fs::TryLockError::Error(err)) => return Err(err),",
    "                Err(fs::TryLockError::Error(err))\n"
    "                    if err.kind() == std::io::ErrorKind::Unsupported =>\n"
    "                {\n                    true\n                }\n"
    "                Err(fs::TryLockError::Error(err)) => return Err(err),", 1),
    "writer lock compat")

edit("rollout/src/maintenance.rs", lambda s: s.replace(
    "        Err(std::fs::TryLockError::Error(error)) => Err(error),",
    "        Err(std::fs::TryLockError::Error(error))\n"
    "            if error.kind() == std::io::ErrorKind::Unsupported =>\n"
    "        {\n            Ok(Some(RolloutMaintenanceGuard { file }))\n"
    "        }\n"
    "        Err(std::fs::TryLockError::Error(error)) => Err(error),", 1),
    "maintenance lock compat")

edit("message-history/src/lib.rs", lambda s: s.replace(
    "                Err(e) => return Err(e.into()),",
    "                Err(e) if matches!(&e, std::fs::TryLockError::Error(ref x)\n"
    "                    if x.kind() == std::io::ErrorKind::Unsupported) =>\n"
    "                {\n                    return Ok(())\n"
    "                }\n"
    "                Err(e) => return Err(e.into()),", 1),
    "history lock compat")

# 5) network-proxy certs: solo warning, ya tolera error; nada que hacer.

# segundo bloque de writer_lock (thread writer lock)
edit("rollout/src/writer_lock.rs", lambda s: s.replace(
    "            Err(std::fs::TryLockError::Error(err)) => {\n"
    "                return Err(io::Error::other(format!(",
    "            Err(std::fs::TryLockError::Error(err))\n"
    "                if err.kind() == std::io::ErrorKind::Unsupported => {}\n"
    "            Err(std::fs::TryLockError::Error(err)) => {\n"
    "                return Err(io::Error::other(format!(", 1),
    "thread writer lock compat")

print("PATCH_ANDROID_OK")
