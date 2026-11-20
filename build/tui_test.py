#!/usr/bin/env python3
"""Prueba de render de la TUI dentro del entorno bionic (qemu).
Requiere: /content/test/bin/opencode, /content/android, servidor en :4100 y
OPENTUI_LIB_PATH apuntando al .so musl. Imprime BYTES / OTUI_ERR / muestra.
"""
import os, pty, select, time, signal, re, fcntl, termios, struct, sys

PORT = os.environ.get("TUI_PORT", "4100")
LIB = os.environ.get("OPENTUI_LIB_PATH", "/content/test/lib/libopentui.so")
PW = os.environ.get("OPENCODE_SERVER_PASSWORD", "")

pid, fd = pty.fork()
if pid == 0:
    os.environ.update({
        "TERM": "xterm-256color",
        "COLUMNS": "120", "LINES": "40",
        "OPENTUI_LIB_PATH": LIB,
        "OPENCODE_SERVER_PASSWORD": PW,
    })
    os.chdir("/content/test")
    os.execv("/usr/bin/qemu-aarch64-static",
             ["qemu-aarch64-static", "-L", "/content/android", "./bin/opencode",
              "--server", f"http://127.0.0.1:{PORT}"])

fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
buf = b""
t0 = time.time()
while time.time() - t0 < 30:
    r, _, _ = select.select([fd], [], [], 0.5)
    if r:
        try:
            d = os.read(fd, 65536)
        except OSError:
            break
        if not d:
            break
        buf += d
try:
    os.kill(pid, signal.SIGKILL)
except Exception:
    pass
os.waitpid(pid, 0)

txt = buf.decode("utf-8", "replace")
plain = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b[()][A-B]|\x1b[=>]", "", txt)
plain = re.sub(r"\x1b\][^\x07]*\x07", "", plain)
lines = [l.rstrip() for l in plain.splitlines() if l.strip()]
print("TUI_BYTES", len(buf))
print("OTUI_ERR", ("Unsupported OpenTUI" in txt) or ("OpenTUI is not supported" in txt)
      or ("Failed to initialize" in txt))
print("TUI_LINES", len(lines))
print("---TUI---")
print("\n".join(lines[:24])[:1200])
