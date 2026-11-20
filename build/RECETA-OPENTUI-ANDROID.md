# Receta exacta: libopentui.so para Android/bionic (aarch64) — opencode 2.3.2

## Estado: receta en CONSTRUCCIÓN (ruta A). No marcar como funcional hasta validar.

## Hallazgos verifyados (no repetir investigacion)

### Por que 2.0.31 funciona y 2.3.2 no
- 2.0.31 ($PREFIX/bin/opencode, 281.736.864 B, sha 3aac028f...): lleva libopentui.so
  **embebida en bunfs**, compilada con **NDK r29 / clang 200433 / API 24 (bionic)**.
  Sus NEEDED: libm.so, libc.so, libdl.so. Solo ~40 simbolos ot_ (API antigua).
- 2.3.2 (nuestro build, 242.466.585 B, sha a818c200...): NO embebe la .so.
  Su JS (opentui core 0.8.4) pide **273 simbolos funcion** (tabla `ot_*: {args:` en
  chunk-bun-dsfc571f.js). De esos, 270 son functions reales + 3 son callbacks
  (ot_edit_event_callback, ot_output_write_callback, ot_scene_measure_callback —
  son typedefs de firma, no funciones a exportar). Incluye `ot_scene_set_hooks`
  (clave: la .so vieja del 2.0.31 NO lo tiene).

### Las dos .so y por que fallan
| .so | API | ABI | resultado |
|---|---|---|---|
| npm @opentui/core-linux-arm64-musl@0.8.4 (sha f0c510a7...) | OK (270/270 simbolos) | musl -> pide sinh, __errno_location, accept4, copy_file_range, dl_iterate_phdr... | dlopen falla en bionic |
| extraida del 2.0.31 (buscar \x7fELF tras "libopentui-kcckf2nc.so" en el binario, offset ~267365361) | NO (le faltan ot_scene_set_hooks y otros) | bionic/NDK r29 OK | falla por simbolos faltantes |

- patchelf --add-needed libm.so a la .so musl: resuelve sinh pero aparece
  __errno_location -> incompatibilidad ABI, NO es problema de NEEDED. Descartado.
- No existe @opentui/core-linux-arm64-android en npm.

### Por que Zig 0.17 fallo (NO repetir)
- zig 0.17.0 + `zig build -Dlibrary-target=aarch64-linux-android.24` -> translate-c
  usa headers glibc del host (gnu/stubs-32.h no encontrado).
- `zig translate-c -isysroot <NDK>/sysroot` -> "unrecognized parameter: -isysroot".
  Zig translate-c no acepta isysroot en 0.17. Ruta descartada.

## Ruta A (ELEGIDA): compilar con clang del NDK (no Zig)
El 2.0.31 se compilo con NDK/clang, no con Zig. Repetir eso:

1. Fuente: /content/otsrc (opentui v0.8.4, tag, .zig-version = verificar).
2. NDK: /content/android-ndk-r27c (634M zip descomprimido, 2.0G) — sysroot en
   toolchains/llvm/prebuilt/linux-x86_64/sysroot. NOTE: la .so del 2.0.31 dice
   NDK r29; si r27c no basta, usar r29.
3. Toolchain clang: /content/android-ndk-r27c/toolchains/llvm/prebuilt/linux-x86_64/bin/clang
   Target: aarch64-linux-android24, --sysroot=<sysroot>, -fPIC -shared.
4. Adaptar build.zig: reemplazar addTranslateC (que usa zig) por un paso que
   llame a clang con el sysroot; o compilar el C a objeto con clang y enlazar.
5. Vendor libs que probablemente hacen falta (verificar en build.zig/DEPS):
   lcms2, libwebp, yoga, miniaudio, SDL? (inventariar antes de compilar).
6. Simbolos requeridos: los 270 de la tabla; validar con `nm -D` que la .so
   resultante exporta todos los `ot_*: {args:` (excepto los 3 callbacks).
7. Validar ABI: `readelf -d` debe mostrar NEEDED libm/libc/libdl (bionic),
   y `readelf --dyn-syms` no debe tener UND de simbolos musl.

## Validacion ANTES de tocar el telefono
1. En Colab: qemu-aarch64-static -L /content/android + binario 2.3.2 con la .so
   nueva -> TUI sin "OpenTUI is not supported" / sin dlopen fail.
2. Empaquetar y probar en aislado en el telefono (install.sh modo test):
   XDG_DATA_HOME/CONFIG aparte, no toca la BD ni ~/.config reales.
3. Solo si pasa:
   - backup automatico (binario + share + config)
   - instalar
   - rollback disponible

## Cache en Drive (para no re-descargar)
rclone gdrive:ia-colab/termux-native/cache/
- bin/bun140, bin/bun145, bin/zig016.tar.xz, bin/zig017.tar.xz (en curso)
- ndk/android-ndk-r27c-linux.zip (634M, ya subido)
- oc/src.tar.zst, oc/comm.tar.zst
- oc/opentui-v0.8.4.tar.gz (en curso)
- RECETA-OPENTUI-ANDROID.md (esta receta)

## Regla dura
NUNCA compilar sin haber verificado: (a) version exacta de la herramienta,
(b) flags soportados, (c) sysroot/headers correctos, (d) inventario de simbolos
y vendor libs. Si un flag falla, investigar antes de probar el siguiente.
