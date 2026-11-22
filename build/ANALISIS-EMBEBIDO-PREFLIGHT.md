# ANÁLISIS PRE-FLIGHT: embeber la .so bionic en el binario 2.3.2

Fuente de verdad: repo `Hope2333/opencode-termux` rama `native-android` (322★, builds nativos bionic funcionando, clonado en Colab `/content/hope`).

## Cómo el 2.0.31 embebe la .so (confirmado)
- NO hay target "android" en el build.ts de opencode (ni 2.0.31 ni 2.3.2). El binario se compila con un target linux-arm64 parcheado.
- El mecanismo: `node-assets.ts` → `getNodeAssets({platform:"linux", arch:"arm64", libc})` → pide paquetes `@opentui/core-linux-arm64*`, `@lydell/node-pty-linux-arm64*`, etc → esos paquetes contienen la `.so` y Bun la **embebe en bunfs** al hacer `bun --compile` (por eso 2.0.31 = 281 MB vs 242 MB del 2.3.2).
- En nuestro build anterior del 2.3.2 plantamos la .so musl en `@opentui/core-linux-arm64-android`/`-musl`, pero `getNodeAssets` con `target.platform="linux"` pide **`@opentui/core-linux-arm64`** (sin sufijo) → ahí no estaba → por eso NO se embebió (242 MB).

## El error FFI `Pointer exceeds safe integer range` (CAUSA Y FIX CONOCIDAS)
- Reportado en `Hope2333/opencode-termux` issue #47, fix en **PR #48** "fix: android termux - cherry-pick".
- Causa: `@opentui/core` 0.8.4 en Android devuelve punteros 64-bit que Bun convierte a Number JS → `POINTER_UNSAFE`.
- Fix (en `@opentui/core` chunk-bun-dsfc571f.js, verificado en nuestra copia 0.8.4 en `/content/otcore/package/`):
  1. `function toSafeNumberPointer(ptr) { if (!Android) throw POINTER_UNSAFE; return Number(Bun.ptr(ptr)); }` (áncora `function toSafeNumberPointer(ptr) {` presente, 1x).
  2. Primera `throw POINTER_UNSAFE;` → `return Number(Bun.ptr(ptr));` (hay 2; la 2da es `toSafeBigIntPointer`, NO tocar).
  3. `platform: process.platform,` → `platform: process.platform === "android" ? "linux" : process.platform,` (1x).
  4. Después de `if (process.platform === "linux") {` añadir rama `else if (process.platform === "android") { arch = "arm64"; }` (1x).
- Verificado: los 4 anclas existen en 0.8.4. `npx patch-package` aplica el parche post-install.

## La ruta CORRECTA (pipeline probado de la comunidad)
El repo usa **`transplant`**, no rebuild desde cero:
1. Descargar el binario oficial: `npm pack opencode-linux-arm64@VER` (o codeload github).
2. `make libopentui`: compila la `.so` bionic con **zig 0.16.0** + `--libc` (el `build-libopentui.sh` propio, con guard pattern checks). O reutilizar la nuestra (SHA 50f8e358, ya compilada y verificada con los 270 símbolos).
3. `python3 tools/transplant/transplant.py all --ver VER --tgz <tgz>` → inyecta la `.so`, hace swap_tui + tui_probe gate, y el shim seccomp (DT_NEEDED libopencode-crhandler.so).
4. Verificación con gates: `ffi_guard_harness` (coordenadas hostiles), `tui_probe`, `verify-artifact`.

## Riesgos / TODO lo que falta (pre-flight honesto)
- **La fix del PR #48 es para 0.6.8; verifiqué que las 4 anclas están en 0.8.4** (1x c/u) → aplicable, pero DEBE validarse en la TUI real (no solo en el build).
- La `.so` que compilamos (zig 0.17 + --libc) es funcional en símbolos, pero el repo de la comunidad usa **zig 0.16.0** y añade un **TLSDESC shim** (`tlsdesc_shim_init`) para hosts bionic < 11. Nuestro Android 14 (SDK34) no necesita el shim, pero hay que confirmar que nuestra .so no use TLS desc que bionic 14 no soporte (launch apparent risk).
- El build.ts actual NO tiene target android (0 ocurrencias de `abi:"android"`) → hay que re-añadir el target falso (patch de build.ts: `{ os:"linux", arch:"arm64", abi:"android" }` + el type union), como se hizo en el primer intento.
- El `plant.py` debe poner la `.so` bionic en **todas las raíces** de `@opentui/core-linux-arm64` (no solo `-android`/`-musl`), y además `@lydell/node-pty-linux-arm64`, `@parcel/watcher-linux-arm64-glibc`, `@ff-labs/fff-bin-linux-arm64-gnu`, `@yuuang/ffi-rs-linux-arm64-gnu`.

## Conclusión del análisis
SÍ es el camino correcto, PERO el riesgo real no es el build (ya sabemos compilar la .so), es el **runtime FFI**. La comunidad ya resolvió ese runtime (PR #48). La secuencia segura es:
1. Aplicar la fix FFI (#48) al bundle del 2.3.2 (patch-package o directo en el chunk).
2. Plantar la .so bionic en las rutas correctas (linux-arm64, no android).
3. Recompilar el binario 2.3.2 con `bun --compile` (o trasplantar al binario oficial con `transplant.py`).
4. Validar TUI en entorno aislado.
5. Solo entonces publicar e instalar (con backup).

NO ejecutar nada hasta que el usuario confirme. Todo en Drive/repo al cerrar.
