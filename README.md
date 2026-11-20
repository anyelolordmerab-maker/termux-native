# termux-native

Native aarch64-bionic builds of AI agent CLIs for Termux/Android.

## Releases
- `opencode-vX.Y.Z` — native opencode binary (+ `libopencode-crhandler.so`)
- `toolchain` — shared build inputs (bionic shim, scripts)

## Install (phone)
```
curl -fL -o /tmp/opencode https://github.com/anyelolordmerab-maker/termux-native/releases/download/opencode-vX.Y.Z/opencode
chmod +x /tmp/opencode && mv /tmp/opencode $PREFIX/bin/opencode
```

Builds are compiled in Colab with Bun's `--compile` targeting `bun-linux-arm64-android`.
