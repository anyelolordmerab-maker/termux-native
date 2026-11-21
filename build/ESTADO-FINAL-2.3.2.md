# ESTADO FINAL — opencode 2.3.2 nativo (para retomar)

Fecha: 2026-11-20. TU 2.0.31 SIGUE INTACTO Y FUNCIONANDO (`$PREFIX/bin/opencode`, v2.0.31).

## LO QUE SE LOGRÓ (hito real)
Se **compiló con éxito una `libopentui.so` bionic de la API correcta (0.8.4)**:
- Artefacto en Colab: `/content/oc-recipe/build/opentui-src/packages/native/lib/aarch64-linux-android.24/libopentui.so`
- SHA256: `50f8e358cd42dd0ec928be256ac2a217cc9a26c5547d7d30f9becf8b8d2f8b97`
- Tamaño: 25.098.896 B (~24 MB, incluye debug info; se puede strip para bajar a ~7 MB)
- Verificado: ELF64 AArch64, NEEDED `libm.so / libc.so / libdl.so` (bionic, IGUAL que tu 2.0.31), 270 símbolos `ot_` (exactamente los que pide el JS de 2.3.2). `accept4@LIBC` es bionic válido.
- Publicada en GitHub release `opencode-v2.3.2` como `libopentui.android-arm64.so`.
- Descargada al teléfono en `~/opencode-2.3.2-termux-aarch64/lib/libopentui.so` (SHA coincide).

## RECETA QUE FUNCIONÓ (la definitiva, NO repetir errores anteriores)
- **Zig 0.17.0 + `--libc android-libc017.txt`** (externo, generado del NDK). Es LA clave: Zig 0.17 "no provee" libc bionic, pero con `--libc` apuntando a un archivo de rutas del NDK **sí linkea**. (Zig 0.16 + su propio android-libc.txt NO funcionó por API; 0.17 sin --libc NO funciona.)
- `android-libc017.txt` (formato 0.17, OBLIGATORIO incluir `cc_dir` y `gcc_dir` apuntando al `bin` del NDK, y `darwin_sdk_dir=` vacío):
  ```
  include_dir=<SYSROOT>/usr/include
  sys_include_dir=<SYSROOT>/usr/include/aarch64-linux-android
  crt_dir=<SYSROOT>/usr/lib/aarch64-linux-android/24
  msvc_lib_dir=
  kernel32_lib_dir=
  gcc_dir=<NDK>/toolchains/llvm/prebuilt/linux-x86_64/bin
  darwin_sdk_dir=
  cc_dir=<NDK>/toolchains/llvm/prebuilt/linux-x86_64/bin
  ```
  NOTA: copiar `crtbegin_so.o` y `crtend_so.o` de `.../aarch64-linux-android/24/` al `bin` del NDK (Zig 0.17 los busca en `cc_dir`, si no los hay falla el linker con "unable to find crtbegin_so.o").
- Comando de build:
  ```
  cd /content/oc-recipe/build/opentui-src/packages/native
  zig build -Doptimize=ReleaseSafe -Dlibrary-target=aarch64-linux-android.24 \
    --libc /content/android-libc017.txt \
    -Dndk-include=<SYSROOT>/usr/include \
    -Dndk-arch-include=<SYSROOT>/usr/include/aarch64-linux-android \
    -Dndk-lib=<SYSROOT>/usr/lib/aarch64-linux-android/24 \
    -Dbionic-compat-c=/content/oc-recipe/ci/bionic-compat.c
  ```
- Parche `build.zig` = `build/opentui-recipe/patch-084-v2.py` del repo (opciones globales, 3 anclas, SIN defineMacro, con `_ = b;`). Aplicar sobre build.zig original de 0.8.4 (backup en `/content/otsrc/packages/native/build.zig.bak`).
- Tiempo REAL de build: ~28-30 min en Colab la primera vez (compila ~100 archivos C lcms2/webp/miniaudio + ~190 módulos Zig). Con caché, menos. NO es 7-13 min (estimación inicial fue baja).
- Fuentes: receta base de `Leonisaurov/bravecode-termux` (opentui 0.5.9) adaptada a 0.8.4.

## PRUEBA AISLADA (controlada, sin tocar el 2.0.31)
Carpeta: `/data/data/com.termux/files/usr/tmp/opencode/aislado/` con binario+libs copiados, HOME/XDG_DATA_HOME/XDG_CONFIG_HOME/LD_LIBRARY_PATH/OPENTUI_LIB_PATH propios. Scripts: `test_tui.py`, `test_full.py`.
- Antes/después de cada prueba: `$PREFIX/bin/opencode --version` = v2.0.31 (verificado, intacto).
- Sin `pkill` global; solo se matan PIDs hijos propios.
- Resultado `test_full.py`: servidor aislado arranca HTTP 200 en puerto 4199, password obtenido, la `.so` carga (OTUI_ERR False, sin dlopen fail)...

## BLOQUEO ACTUAL (el siguiente a resolver)
Nuevo error FFI al renderizar TUI:
```
Error: Pointer exceeds safe integer range
  at Sn (/$bunfs/root/chunk-8j22f69k.js:2:86411)
  at createContext (/$bunfs/root/chunk-8j22f69k.js:172:2391)
  ...
  at Tui.run (chunk-k70c4tr9.js:99:644)
```
- Causa probable: `bun:ffi` declaró una función con retorno entero donde la `.so` bionic devuelve un **puntero de 64 bits** → Bun no lo representa como Number. El 2.0.31 no lo tiene (su .so embebida se carga por otro path).
- NO es problema de la .so (símbolos/NEEDED correctos). Es un issue de declaración de tipos FFI / del runtime Bun con esta .so.
- Investigar: en `chunk-8j22f69k.js` la función `Sn` y el símbolo que crea `createContext`. Posibles fixes:
  a) Parchear la declaración FFI para usar tipo `ptr` en el retorno.
  b) Usar `bun:ffi` pointer handling / `OPENCODE_LIBC` o flag de Bun.
  c) En su defecto, recompilar el binario 2.3.2 con la .so **embebida** (como 2.0.31) — requiere `bun install` + `bun --compile`, ~5-8 min, y es la paridad total que el usuario quiere.
- Colab se desconectó justo cuando se iba a investigar `Sn` en el chunk.

## PROCESOS SUELTOS (identificar, NO pkill global)
- PID 23471: `~/opencode-2.3.2-termux-aarch64/opencode serve --service` (de prueba anterior). Matar por PID exacto si hace falta, nunca con pkill -f.
- Servidor 2.0.31 legítimo: PIDs 12204/12222 (NO tocar).

## GUARDADO
- GitHub: release `opencode-v2.3.2` tiene `libopentui.android-arm64.so` (la nueva) + el paquete viejo.
- Repo `anyelolordmerab-maker/termux-native` rama main: `build/opentui-recipe/` (receta), `build/INVENTARIO-BUILD-OPENTUI-ANDROID.md`, `build/RECETA-OPENTUI-ANDROID.md`, `build/ESTADO-FINAL-2.3.2.md` (este archivo).
- Drive: `gdrive:ia-colab/termux-native/cache/oc/` (receta, inventario, parche), `cache/ndk/` (NDK r27c), `cache/bin/` (zig016, zig017, bun). Subida en background (PID 16288) — verificar al retomar.

## REGLAS DURAS (aprendidas a golpes)
- NUNCA `colab_open()` sin URL → abre notebook nueva y borra /content. URL: https://colab.research.google.com/drive/1ELGdeNQwABNMsUbA9UF6qBmo2GMyeLqp (GptAflyx.ipynb).
- NUNCA instalar ni re-descargar binario grande en el teléfono sin permiso.
- NUNCA tocar el 2.0.31 ni usar pkill global. Pruebas SIEMPRE aisladas (HOME/XDG propios).
- Zig 0.17 SIN --libc no sirve; con --libc (formato 0.17 con cc_dir) SÍ. No repetir Zig 0.16.
- Guardar TODO en Drive/repo antes de cerrar.
