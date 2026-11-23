# Prueba definitiva aislada de opencode 2.3.2 en Termux

Objetivo: comprobar el binario 2.3.2 en el teléfono **sin tocar** el opencode 2.0.31 funcional ni sus sesiones.

## 1. Backup (solo lectura + copia)
```bash
mkdir -p ~/oc-2.3.2-test/{bin,home,cache,data,state,tmp,logs,backup}
cp -a "$PREFIX/bin/opencode" ~/oc-2.3.2-test/backup/opencode-2.0.31
cp -a ~/.config/opencode ~/oc-2.3.2-test/backup/config-opencode 2>/dev/null || true
```

## 2. Extraer binario nuevo en ruta separada
```bash
cd ~/oc-2.3.2-test
tar --zstd -xf opencode-embedded-2.3.2.tar.zst
cp opencode-embedded bin/opencode-2.3.2-test
chmod +x bin/opencode-2.3.2-test
sha256sum -c opencode-embedded-2.3.2.tar.zst.sha256
```

## 3. Entorno 100% aislado
Cada comando se ejecuta con prefijos propios (nada toca los del 2.0.31):
```bash
export OC=~/oc-2.3.2-test
export HOME=$OC/home
export XDG_CONFIG_HOME=$OC/home/.config
export XDG_DATA_HOME=$OC/data
export XDG_CACHE_HOME=$OC/cache
export XDG_STATE_HOME=$OC/state
export TMPDIR=$OC/tmp
export TERM=xterm-256color
unset LD_LIBRARY_PATH   # no heredar libs del 2.0.31
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$XDG_STATE_HOME" "$TMPDIR"
```

## 4. Pruebas (en orden)
```bash
B=$OC/bin/opencode-2.3.2-test
$B --version | tee $OC/logs/version.log        # debe decir 2.3.2
$B --help | tee $OC/logs/help.log              # debe listar serve
timeout 60 script -q -e -c "$B" /dev/null > $OC/logs/tui.log 2>&1
$B serve --hostname 127.0.0.1 --port 4518 > $OC/logs/serve.log 2>&1 &
echo $! > $OC/logs/serve.pid
# esperar HTTP 200 en http://127.0.0.1:4518/app
PW=$(grep 'server password ' $OC/logs/serve.log | tail -1 | sed 's/.*server password //')
export OPENCODE_PASSWORD="$PW"
export OPENCODE_SERVER_PASSWORD="$PW"
timeout 40 script -q -e -c "$B --server http://127.0.0.1:4518" /dev/null > $OC/logs/tui-server.log 2>&1
```

## 5. Criterios de éxito
- `version.log` contiene `2.3.2`; `help.log` contiene `serve`.
- `tui.log` y `tui-server.log` tienen escapes ANSI (`\x1b[`) y >800 bytes.
- **No** aparecen: `Unsupported OpenTUI`, `Failed to initialize`, `Pointer exceeds`, `dlopen failed`, `Cannot find module`, `EACCES`.
- `serve` responde HTTP 200 y el TUI por servidor renderiza.
- Existen archivos extraídos `libopentui*.so` bajo `$TMPDIR`/`$XDG_CACHE_HOME`.

## 6. Rollback
- No mover nada del 2.0.31 durante la prueba.
- Si todo pasa y se decide instalar: copiar backup antes, reemplazar `$PREFIX/bin/opencode`, guardar el binario viejo.
- Nunca `pkill` por patrón: usar `kill $(cat $OC/logs/serve.pid)` (PID exacto).
- Si algo falla: borrar `$OC` y seguir usando el 2.0.31 intacto.
