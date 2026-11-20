# INVENTARIO REAL del build de libopentui.so para Android/bionic

Fuentes (investigadas en web, no inventado):
- build.zig oficial de opentui v0.8.4: https://raw.githubusercontent.com/anomalyco/opentui/v0.8.4/packages/native/build.zig
- Release notes Zig 0.17: https://ziglang.org/download/0.17.0/release-notes.html
- Receta validada (opentui 0.5.9): https://github.com/Leonisaurov/bravecode-termux
  - ci/build-opentui-android.sh
  - ci/patch-opentui-android-translate-c.py
  - ci/bionic-compat.c
  - ci/verify-libopentui.sh
- Repo de referencia (tu 2.0.31 probable): https://github.com/bd-loser/opencode-bionic

## 1. POR QUÉ fallaron todos mis intentos anteriores
- Zig 0.17 NO provee libc para `aarch64-linux-android` (tabla de targets 0.17 no incluye
  Android en ningún tier). `zig build --sysroot` no lo arregla: "unable to provide libc".
- La receta que SÍ funciona usa **Zig 0.16.x** + un archivo **`--libc android-libc.txt`**
  generado del NDK. Ese `--libc` es LA pieza clave que yo no usé: le dice a Zig dónde
  están includes/CRT/libs de bionic. Yo intenté `zig build` sin `--libc` → siempre falló.

## 2. Toolchain exacto (inventario)
| Pieza | Versión / valor | Estado |
|---|---|---|
| Zig | 0.16.x (0.16.0 probado; 0.17 NO sirve) | a descargar (o ya en Drive zig016.tar.xz) |
| NDK | r27c (634M, sysroot aarch64-linux-android/24) | YA en /content/android-ndk-r27c |
| Opentui | v0.8.4 (el que pide opencode 2.3.2) | YA en /content/otsrc |
| Target Zig | `aarch64-linux-android.24` | - |
| Optimize | `ReleaseSafe` | - |
| API Android | 24 | - |

## 3. Archivos que el NDK debe aportar (preflight)
- `$SYSROOT/usr/include/stdlib.h`
- `$SYSROOT/usr/include/sys/errno.h`
- `$CRT_DIR/crtbegin_dynamic.o`, `crtend_android.o`, `libc.so`
- `CRT_DIR = $SYSROOT/usr/lib/aarch64-linux-android/24`

## 4. android-libc.txt (se genera, no se versiona)
```
include_dir=<SYSROOT>/usr/include
sys_include_dir=<SYSROOT>/usr/include/aarch64-linux-android
crt_dir=<CRT_DIR>
msvc_lib_dir=
kernel32_lib_dir=
gcc_dir=
```
Se pasa a zig con `--libc <archivo>`.

## 5. Dependencias Zig (vendor del repo, se preparan con scripts)
- uucode, yoga, ghostty_vt — vía `src/vendor/update-zig-deps.sh` + `scripts/prepare-zig-deps.sh`
- Fuentes C vendorizadas: lcms2, libwebp, miniaudio, stb (ya en el repo, no descargar)
- FFmpeg: opcional; sin él se compila con `OTV_NO_FFMPEG` (video deshabilitado)

## 6. Parche del build.zig (3 problemas, todos resueltos por el script validado)
1. `addTranslateC` (miniaudio, yoga) NO hereda `--libc` → necesita los include dirs del NDK
   y anular `_Nullable`/`_Nonnull`/`_Null_unspecified` (bionic headers vs translate-c).
2. Link de Linux pide `dl` y `pthread` (inexistentes en bionic) y no encuentra `m`:
   en Android solo linkear `m` + `addLibraryPath(<NDK lib dir>)`.
3. Zig 0.16 emite `pthread_tryjoin_np` (glibc) para linux-android → se incluye
   `bionic-compat.c` que lo define usando `pthread_join`.
Usar `ci/patch-opentui-android-translate-c.py` (idempotente, falla si no encuentra anclas).

## 7. Verificación del artefacto (verify-libopentui.sh)
- ELF64 AArch64 DYN ✅
- NEEDED libc.so (Bionic, NO libc.so.6/glibc) ✅
- Exporta los símbolos FFI que pide @opentui/core (para 0.8.4: ~270 `ot_*`)
- Todos los símbolos UND existen en libc/libm/libdl/liblog/libandroid/libz del NDK
  (detecta `pthread_tryjoin_np`, `sinh`, `__errno_location`, etc. antes del device)

## 8. Validación final (sin tocar el opencode del teléfono)
1. qemu-aarch64 bionic + binario 2.3.2 con la .so nueva → TUI sin dlopen fail
2. Empaquetar + prueba aislada en teléfono (XDG_DATA_HOME/CONFIG aparte)
3. Solo si pasa: backup → instalar → rollback disponible

## ADAPTACIÓN 0.5.9 → 0.8.4 (pendiente de validar anclas)
El script validado es para 0.5.9. El build.zig de 0.8.4 (leído arriba) tiene las mismas
estructuras: `addTranslateC`, `.linux => { linkSystemLibrary("dl"/"pthread"/"m") }`,
`applyDependencies` + `b.addLibrary`. Los anclas del parche parecen compatibles; verificar
con `grep` antes de aplicar. Diferencia: 0.8.4 usa `std.lang.Optimize` (0.17) → al usar
Zig 0.16 hay que cambiar a `std.builtin.OptimizeMode` y `.fast`→`.ReleaseFast` (ya sabido).
