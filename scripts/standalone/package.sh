#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
#
# Build a ready-to-run standalone Job Attune distribution for the CURRENT
# operating system. Used by .github/workflows/release.yml on all three
# runner platforms; reproducible locally:
#
#     bun install && bun run build
#     bash scripts/standalone/package.sh
#
# Output: dist/job-attune-standalone-<platform>.<tar.gz|zip> (+ .sha256)
#
# The archive bundles everything the app needs at runtime:
#   - the compiled omnidecide-c C11 kernel for this platform
#   - the Next.js standalone server (type-checked production build)
#   - the attune Python engine + demo corpus + profile templates
#   - a Node.js 22 LTS runtime (official nodejs.org binaries)
#   - a CPython 3.12 runtime with reportlab/pypdf preinstalled
#     (astral-sh/python-build-standalone build)
# so an unpacked archive runs with no prerequisites beyond the OS itself.
#
# Pinned versions: bump deliberately. The kernel build flags must stay in
# sync with SETUP.md (bit-identical results), and the runtime versions must
# match the compatibility notes in scripts/standalone/START-HERE.txt.

set -euo pipefail

NODE_VERSION="22.14.0"   # Node 22 LTS, same major as the Dockerfile runtime
PYTHON_TAG="20241016"    # astral-sh/python-build-standalone release tag
PYTHON_VERSION="3.12.7"  # CPython the engine is tested on (3.10+ supported)

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [ ! -f .next/standalone/server.js ]; then
  echo "ERROR: .next/standalone/server.js missing - run 'bun run build' first" >&2
  exit 1
fi

# ------------------------------------------------------------------ platform
case "$(uname -s)" in
  Linux*)
    PLATFORM="linux-x64"
    KERNEL_CC="cc"; KERNEL_LIB="libomnidecide.so"; KERNEL_ARCH_FLAGS=""
    NODE_ASSET="node-v${NODE_VERSION}-linux-x64.tar.xz"
    PY_ASSET="cpython-${PYTHON_VERSION}+${PYTHON_TAG}-x86_64-unknown-linux-gnu-install_only.tar.gz"
    ARCHIVE_EXT="tar.gz"; PY_BIN="bin/python3"; ZIP=0
    ;;
  Darwin*)
    # Universal kernel (arm64 + x86_64 slices) costs ~400 KB extra and keeps
    # the archive usable if the runtimes are ever swapped for Intel ones;
    # the bundled Node/Python are arm64 (see START-HERE.txt).
    PLATFORM="macos-arm64"
    KERNEL_CC="cc"; KERNEL_LIB="libomnidecide.dylib"; KERNEL_ARCH_FLAGS="-arch arm64 -arch x86_64"
    NODE_ASSET="node-v${NODE_VERSION}-darwin-arm64.tar.gz"
    PY_ASSET="cpython-${PYTHON_VERSION}+${PYTHON_TAG}-aarch64-apple-darwin-install_only.tar.gz"
    ARCHIVE_EXT="tar.gz"; PY_BIN="bin/python3"; ZIP=0
    ;;
  MINGW*|MSYS*|CYGWIN*)
    PLATFORM="windows-x64"
    KERNEL_CC="gcc"; KERNEL_LIB="omnidecide.dll"; KERNEL_ARCH_FLAGS="-static-libgcc"
    NODE_ASSET="node-v${NODE_VERSION}-win-x64.zip"
    PY_ASSET="cpython-${PYTHON_VERSION}+${PYTHON_TAG}-x86_64-pc-windows-msvc-shared-install_only.tar.gz"
    ARCHIVE_EXT="zip"; PY_BIN="python.exe"; ZIP=1
    ;;
  *)
    echo "ERROR: unsupported platform: $(uname -s)" >&2
    exit 1
    ;;
esac

DIST_NAME="job-attune-standalone-$PLATFORM"
DIST_ROOT="$ROOT/dist"
echo "==> platform: $PLATFORM (kernel: $KERNEL_LIB, archive: $ARCHIVE_EXT)"

TMP="$(mktemp -d)"
mkdir -p "$TMP/rt"
trap 'rm -rf "$TMP"' EXIT

# ------------------------------------------------------------------ kernel
echo "==> compiling the C11 kernel ($KERNEL_CC, -std=c11 -ffp-contract=off)"
mkdir -p vendor/omnidecide-c/build
"$KERNEL_CC" -std=c11 -ffp-contract=off -O2 -fPIC -shared $KERNEL_ARCH_FLAGS \
  -Ivendor/omnidecide-c/include -Ivendor/omnidecide-c/src \
  vendor/omnidecide-c/src/*.c -lm \
  -o "vendor/omnidecide-c/build/$KERNEL_LIB"
ls -la "vendor/omnidecide-c/build/$KERNEL_LIB"

# ------------------------------------------------------------------ runtimes
echo "==> downloading the bundled runtimes"
curl -fsSL --retry 3 -o "$TMP/node-archive" \
  "https://nodejs.org/dist/v${NODE_VERSION}/${NODE_ASSET}"
curl -fsSL --retry 3 -o "$TMP/python-archive" \
  "https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_TAG}/${PY_ASSET}"

# install_only archives unpack to ./python/ ; system tar exists on every
# runner, so use it to bootstrap the very first extraction.
tar -xzf "$TMP/python-archive" -C "$TMP/rt"
PY="$TMP/rt/python/$PY_BIN"
if [ ! -e "$PY" ]; then
  echo "ERROR: bundled python not found at $PY" >&2
  exit 1
fi

if [ "$ZIP" -eq 1 ]; then
  "$PY" -m zipfile -e "$TMP/node-archive" "$TMP/rt"
else
  "$PY" -m tarfile -e "$TMP/node-archive" "$TMP/rt"
fi
mv "$TMP/rt"/node-v*/ "$TMP/rt/node-dist"

if ! "$PY" -m pip --version >/dev/null 2>&1; then
  "$PY" -m ensurepip --upgrade
fi
"$PY" -m pip install --no-cache-dir --upgrade pip
"$PY" -m pip install --no-cache-dir -r requirements.txt
"$PY" -c "import reportlab, pypdf; print('bundled python: reportlab + pypdf OK')"
if [ "$ZIP" -eq 1 ] && [ ! -f "$TMP/rt/python/python3.exe" ]; then
  # the web app spawns `python3`; Windows portable builds ship python.exe only
  cp "$TMP/rt/python/python.exe" "$TMP/rt/python/python3.exe"
fi

# --------------------------------------------------------- engine smoke test
# Prove this platform's kernel + the bundled python run the real engine
# BEFORE packaging anything.
echo "==> engine smoke (bundled python + $KERNEL_LIB)"
export OMNIDECIDE_C_LIB="$ROOT/vendor/omnidecide-c/build/$KERNEL_LIB"
SMOKE="$TMP/smoke-run"
"$PY" attune-engine/engine.py \
  --folder attune-sample-data/candidates \
  --profile attune-data/templates/example-senior-data-engineer.json \
  --run-dir "$SMOKE"
"$PY" - "$SMOKE" <<'PYEOF'
import json, sys
run = sys.argv[1]
m = json.load(open(run + "/results.json"))
ver = m.get("omnidecide_version") or m.get("audit", {}).get("manifest", {}).get("omnidecide_version")
assert ver == "omnidecide-c 1.0.0", f"unexpected kernel id in manifest: {ver!r}"
print("engine smoke OK:", ver)
PYEOF

# ------------------------------------------------------------------ staging
echo "==> staging the distribution"
STAGE="$TMP/stage"
APP="$STAGE/$DIST_NAME/app"
mkdir -p "$APP" "$STAGE/$DIST_NAME/runtime"

# Node runtime: prune to the binary itself (the standalone server needs no
# npm/corepack) - keeps the archive ~40 MB smaller.
if [ "$ZIP" -eq 1 ]; then
  mkdir -p "$STAGE/$DIST_NAME/runtime/node"
  cp "$TMP/rt/node-dist/node.exe" "$STAGE/$DIST_NAME/runtime/node/"
else
  mkdir -p "$STAGE/$DIST_NAME/runtime/node/bin"
  cp "$TMP/rt/node-dist/bin/node" "$STAGE/$DIST_NAME/runtime/node/bin/"
fi

# Python runtime with the preinstalled PDF-export packages.
mv "$TMP/rt/python" "$STAGE/$DIST_NAME/runtime/python"
PY="$STAGE/$DIST_NAME/runtime/python/$PY_BIN"

# Next.js standalone bundle. Python copytree materializes symlinks as real
# files, which survives the Windows junctions inside node_modules where
# plain cp -r can trip.
"$PY" - <<PYEOF
import shutil
shutil.copytree("$ROOT/.next/standalone", "$APP", symlinks=False, dirs_exist_ok=True)
print("standalone bundle staged")
PYEOF

# Engine, templates, demo corpus and the compiled kernel + version header.
cp -r attune-engine "$APP/attune-engine"
mkdir -p "$APP/attune-data"
cp -r attune-data/templates "$APP/attune-data/templates"
cp -r attune-sample-data "$APP/attune-sample-data"
mkdir -p "$APP/vendor/omnidecide-c/build" "$APP/vendor/omnidecide-c/include"
cp "vendor/omnidecide-c/build/$KERNEL_LIB" "$APP/vendor/omnidecide-c/build/"
cp vendor/omnidecide-c/include/omnidecide.h "$APP/vendor/omnidecide-c/include/"

# Launchers + the user-facing quick guide.
cp scripts/standalone/START-HERE.txt "$STAGE/$DIST_NAME/"
cp scripts/standalone/start.sh "$STAGE/$DIST_NAME/"
if [ "$(uname -s)" = "Darwin" ]; then
  cp scripts/standalone/start.command "$STAGE/$DIST_NAME/"
fi
if [ "$ZIP" -eq 1 ]; then
  cp scripts/standalone/start.bat "$STAGE/$DIST_NAME/"
fi
chmod +x "$STAGE/$DIST_NAME/start.sh" 2>/dev/null || true
chmod +x "$STAGE/$DIST_NAME/start.command" 2>/dev/null || true

# Never ship bytecode, editor/OS junk or stray build products.
find "$STAGE" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$STAGE" -name "*.pyc" -delete 2>/dev/null || true
find "$STAGE" -name ".DS_Store" -delete 2>/dev/null || true

# ------------------------------------------------------------------ archive
echo "==> creating the archive"
mkdir -p "$DIST_ROOT"
ART="$DIST_ROOT/$DIST_NAME.$ARCHIVE_EXT"
rm -f "$ART" "$ART.sha256"
if [ "$ZIP" -eq 1 ]; then
  "$PY" - "$ART" "$STAGE/$DIST_NAME" <<'PYEOF'
import os, sys, zipfile
art, src = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(art, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for base, dirs, files in os.walk(src):
        for f in sorted(files):
            p = os.path.join(base, f)
            zf.write(p, os.path.relpath(p, os.path.dirname(src)))
print(f"zip: {os.path.getsize(art) / 1e6:.1f} MB")
PYEOF
else
  # tar preserves the executable bits on the launchers
  tar -czf "$ART" -C "$STAGE" "$DIST_NAME"
fi

"$PY" - "$ART" <<'PYEOF'
import hashlib, os, sys
p = sys.argv[1]
h = hashlib.sha256(open(p, "rb").read()).hexdigest()
with open(p + ".sha256", "w") as f:
    f.write(h + "  " + os.path.basename(p) + "\n")
print("sha256:", h)
PYEOF

echo "==> done: $ART (+ .sha256)"
du -sh "$ART" | cut -f1 | xargs -I{} echo "    size: {}"
