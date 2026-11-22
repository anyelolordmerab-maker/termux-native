# PLAN: build embebido rápido + prueba en Colab tipo teléfono

Fuente: repo `Hope2333/opencode-termux` rama `native-android` (322★, clonado `/content/hope`). Pipeline de producción real, probado.

## LOS 3 REQUISITOS DEL USUARIO Y CÓMO SE CUMPLEN

### 1) EMBEBIDO (no separado)
- El 2.0.31 embebe la `.so` en bunfs (281 MB). Mecanismo: `node-assets.ts` → `getNodeAssets({platform:"linux",arch:"arm64",libc:"glibc"})` → empaqueta `@opentui/core-linux-arm64` con la `.so` dentro → `bun --compile` la mete en el ELF.
- Nuestro build anterior plantó la `.so` en paquetes `-android`/`-musl` → `getNodeAssets` pide `@opentui/core-linux-arm64` (sin sufijo) → por eso NO se embebió (242 MB).
- **Fix**: plantar la `.so` bionic (SHA 50f8e358) en TODAS las raíces de `@opentui/core-linux-arm64` (y sus 5 raíces node_modules/.bun), más pty/watcher/fff/ffi. Luego `bun --compile` → 281 MB, embebido.

### 2) RÁPIDO
- NO recompilar la `.so` con zig (28-30 min). Ya está compilada (SHA 50f8e358). Reutilizar.
- El repo evita `bun install` lento con `npm-fetch.sh` (tarballs directos del registry) y `BUN_REGISTRY` mirror (~5 min el resolve).
- Compilar con **android-bun 1.4.0** (pin; 1.4.2 segfaulta en bionic). `bun script/build.ts --target=opencode-linux-arm64`.
- Tiempo estimado build embebido: ~6-10 min (vs 28-30 min de zig).
- Alternativa aún más rápida (`transplant.py all`): descargar binario oficial `opencode-linux-arm64@VER` de npm y **inyectar** la `.so` bionic por swap de igual longitud (~1-2 min, sin compilar). Es la ruta A-line del repo, probada.

### 3) PRUEBA EN COLAB TIPO TELÉFONO
- El repo usa `qemu-aarch64` + rootfs bionic para `tui_probe` (pty, timeout 15s, detecta "Failed to initialize OpenTUI").
- nosotros ya validamos qemu-aarch64 -L /content/android (linker64 + libs de /apex/com.android.runtime). Reutilizar ese rootfs.
- El FFI fix se prueba con el mismo `tui_probe`: si la TUI sobrevive 15s sin el mensaje de error → pass.
- Todo en Colab, sin tocar el teléfono ni su opencode 2.0.31.

## FIX FFI (causa raíz del error que vimos) — DEFINITIVO
- Causa: Android 11+ (Scudo) etiqueta punteros heap en el byte alto (0xb4xx…), valor > 2^53. `toSafeNumberPointer()` de opentui lanza "Pointer exceeds safe integer range" en `createContext` → TUI muere.
- Fix exacto (repo, issues #43/#45/#46): `tools/build-bionic/patch-ffi-pointer.py` → cambia el `throw new Error(POINTER_UNSAFE)` por `return pointer; /* OT_PTR_BIGINT */` (Bun FFI acepta BigInt). 2 chunks: `chunk-bun-dsfc571f.js` y `chunk-node-5nvhjp1a.js`.
- **Verificado en nuestro @opentui/core@0.8.4**: ambos chunks tienen exactamente 1 ancla → aplica limpio.
- En 0.8.x NO hace falta el platform patch (upstream ya fija `platform:"linux"`); SOLO el FFI pointer fix.

## SECUENCIA SEGURA (sin ejecutar aún)
1. Preparar source opencode 2.3.2 + bun 1.4.0 + android libs (todo cacheable).
2. Plantar .so bionic en `@opentui/core-linux-arm64` (5 raíces) + helpers.
3. Aplicar `patch-ffi-pointer.py` a los 2 chunks de @opentui/core.
4. `bun --compile` (o `transplant.py` = más rápido) → binario 281 MB embebido.
5. Verificación gates: ELF aarch64, NEEDED bionic, 270 símbolos, `strings | grep 50f8e358` (asset embebido), sha256.
6. Prueba `tui_probe` en Colab con qemu/rootfs bionic (pty 15s) → PASS.
7. Solo si pasa: publicar + empaquetar. Instalación en teléfono SIEMPRE con backup/rollback y prueba aislada previa.

## RIESGOS RESIDUALES (honesto)
- El FFI fix está probado por la comunidad en Android 11+; en nuestro Android 14 (SDK34) debería aplicar igual.
- La .so nuestra es zig 0.17; la del repo es zig 0.16+TLSDESC shim. Android 14 no necesita el shim, pero es una diferencia no validada en runtime (el `tui_probe` la validará).
- La ruta `transplant` (más rápida) requiere el binario oficial de npm; verificar disponibilidad de `opencode-linux-arm64@2.3.2`.
