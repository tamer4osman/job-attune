#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
#
# Build a ready-to-run standalone Job Attune distribution for the CURRENT
# operating system. Used by .github/workflows/release.yml on all three
# runner platforms; reproducible locally:
#
#     bash scripts/standalone/package.sh
#
# Output: dist/job-attune-standalone-<platform>.<tar.gz|zip> (+ .sha256)
#
# The archive bundles everything the app needs at runtime:
#   - the compiled omnidecide-c C11 kernel for this platform
#   - the vanilla web app (server.py + web/, no build step, no Node.js)
#   - the attune Python engine + demo corpus + profile templates
#   - a CPython 3.12 runtime with reportlab/pypdf preinstalled
#     (astral-sh/python-build-standalone build)
# so an unpacked archive runs with no prerequisites beyond the OS itself.
#
# Pinned versions: bump deliberately. The kernel build flags must stay in
# sync with SETUP.md (bit-identical results), and the runtime versions must
# match the compatibility notes in scripts/standalone/START-HERE.txt.

set -euo pipefail

PYTHON_TAG="20241016"    # astral-sh/python-build-standalone release tag
PYTHON_VERSION="3.12.7"  # CPython the engine is tested on (3.10+ supported)

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

# On Windows runners (shell: bash = Git Bash/MSYS), pwd yields POSIX-style
# paths like /d/a/repo/repo. Native Windows programs - above all the bundled
# CPython that loads the kernel via OMNIDECIDE_C_LIB and receives staging
# paths inside heredocs - cannot resolve MSYS-style paths, and env vars are
# NOT path-converted by the MSYS runtime. cygpath -m normalizes to the
# drive-letter form with forward slashes (d:/a/repo/repo), which BOTH the
# MSYS coreutils (cp, tar, find...) and Windows Python accept. cygpath only
# exists under MSYS, so Linux/macOS are untouched.
if command -v cygpath >/dev/null 2>&1; then
  ROOT_WIN="$(cygpath -m "$ROOT")"
else
  ROOT_WIN="$ROOT"
fi

if [ ! -f server.py ] || [ ! -d web ]; then
  echo "ERROR: server.py / web/ missing - run me from the repo root" >&2
  exit 1
fi

# ------------------------------------------------------------------ platform
case "$(uname -s)" in
  Linux*)
    PLATFORM="linux-x64"
    KERNEL_CC="cc"; KERNEL_LIB="libomnidecide.so"; KERNEL_ARCH_FLAGS=""
    KERNEL_MATH="-lm"; KERNEL_STATIC_FLAGS=""
    PY_ASSET="cpython-${PYTHON_VERSION}+${PYTHON_TAG}-x86_64-unknown-linux-gnu-install_only.tar.gz"
    ARCHIVE_EXT="tar.gz"; PY_BIN="bin/python3"; ZIP=0
    ;;
  Darwin*)
    # Universal kernel (arm64 + x86_64 slices) costs ~400 KB extra and keeps
    # the archive usable if the runtime is ever swapped for an Intel one;
    # the bundled Python is arm64 (see START-HERE.txt).
    PLATFORM="macos-arm64"
    KERNEL_CC="cc"; KERNEL_LIB="libomnidecide.dylib"; KERNEL_ARCH_FLAGS="-arch arm64 -arch x86_64"
    KERNEL_MATH="-lm"; KERNEL_STATIC_FLAGS=""
    PY_ASSET="cpython-${PYTHON_VERSION}+${PYTHON_TAG}-aarch64-apple-darwin-install_only.tar.gz"
    ARCHIVE_EXT="tar.gz"; PY_BIN="bin/python3"; ZIP=0
    ;;
  MINGW*|MSYS*|CYGWIN*)
    PLATFORM="windows-x64"
    # MinGW-w64 gcc (runner image default via Strawberry Perl). All runtime libraries
    # must be statically linked so MSVC CPython can load the DLL on clean Windows
    # machines. Without this, we get "Could not find module" for missing DLLs like
    # libgcc_s_seh-1.dll, libwinpthread-1.dll, libmingwex-1.dll, libmingw-1.dll.
    # GNU ld auto-exports symbols with --export-all-symbols.
    KERNEL_CC="gcc"; KERNEL_LIB="omnidecide.dll"
    # -static-libgcc handles libgcc_s_seh-1.dll, -static-libstdc++ handles
    # libstdc++-6.dll. MinGW's libmingw(-ex) and libwinpthread static archives
    # (-lmingw.a, -lmingwex.a, -lwinpthread.a) are NOT available on windows-latest
    # runners (it's an MSVC toolchain). We rely on -static-libgcc to eliminate
    # libgcc_s_seh-1.dll dependency. The MSVC C runtime (msvcrt.dll) is always
    # available on Windows and links automatically for C11 code.
    KERNEL_ARCH_FLAGS="-static-libgcc -static-libstdc++ -Wl,--export-all-symbols"
    KERNEL_MATH=""
    KERNEL_STATIC_FLAGS=""
    # MSVC build (python-build-standalone 20241016 lacks GNU builds for Windows).
    # Use full install_only variant: the shared variant (~38MB) is missing the
    # Python stdlib needed by the attune engine. Full build (~66MB) includes
    # all stdlib modules required for proper operation.
    PY_ASSET="cpython-${PYTHON_VERSION}+${PYTHON_TAG}-x86_64-pc-windows-msvc-install_only.tar.gz"
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

# On Windows runners (shell: bash = Git Bash/MSYS), pwd yields POSIX-style
# paths like /d/a/repo/repo. MSYS-core utilities (tar, cp, find, rm) work
# correctly with these paths, but native Windows programs need Windows-style
# paths (d:/a/repo/repo with forward slashes).
# 
# Strategy: Keep POSIX paths for MSYS utilities, convert to Windows style
# only when invoking native Windows programs (like the bundled CPython).
if command -v cygpath >/dev/null 2>&1; then
  ROOT_WIN="$(cygpath -m "$ROOT")"
else
  # Non-Windows: no conversion needed
  ROOT_WIN="$ROOT"
fi

# POSIX path for MSYS utilities (tar, cp, find, rm) - works for all platforms
TMP="$(mktemp -d)"
STAGE="$TMP/stage"
mkdir -p "$TMP/rt"
trap 'rm -rf "$TMP"' EXIT

# ------------------------------------------------------------------ kernel
# Same sources and flags as scripts/build-kernel.sh, the repo's canonical
# build line: odk-core + odk-brain + odk-spine with -std=c11
# -ffp-contract=off. -ffp-contract=off is what keeps decisions bit-identical
# across compilers and platforms (the engine's determinism contract).
echo "==> compiling the C11 kernel ($KERNEL_CC, -std=c11 -ffp-contract=off)"
mkdir -p vendor/omnidecide-c/build
# shellcheck disable=SC2086  # KERNEL_ARCH_FLAGS is a deliberate multi-flag list
# shellcheck disable=SC2086  # KERNEL_STATIC_FLAGS is a deliberate multi-flag list
"$KERNEL_CC" -std=c11 -ffp-contract=off -O2 -Wall -fPIC -shared $KERNEL_ARCH_FLAGS \
  -Ivendor/omnidecide-c/include \
  -Ivendor/omnidecide-c/odk-core -Ivendor/omnidecide-c/odk-brain -Ivendor/omnidecide-c/odk-spine \
  vendor/omnidecide-c/odk-core/*.c vendor/omnidecide-c/odk-brain/*.c vendor/omnidecide-c/odk-spine/*.c \
  $KERNEL_MATH $KERNEL_STATIC_FLAGS \
  -o "vendor/omnidecide-c/build/$KERNEL_LIB"
ls -la "vendor/omnidecide-c/build/$KERNEL_LIB"

# ------------------------------------------------------------------ runtime
echo "==> downloading the bundled CPython runtime"
# URL-encode the + in Python version string (GitHub requires %2B; + can be
# misinterpreted by curl on Windows Git Bash where + decodes to space).
PY_ASSET_ENCODED="${PY_ASSET//+/%2B}"
curl -fsSL --retry 3 -L -o "$TMP/python-archive" \
  "https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_TAG}/${PY_ASSET_ENCODED}"
echo "==> download complete, file size: $(wc -c < "$TMP/python-archive") bytes"

# install_only archives unpack to ./python/ ; system tar exists on every
# runner, so use it to bootstrap the very first extraction.
tar -xzf "$TMP/python-archive" -C "$TMP/rt"
PY="$TMP/rt/python/$PY_BIN"
if [ ! -e "$PY" ]; then
  echo "ERROR: bundled python not found at $PY" >&2
  exit 1
fi

if ! "$PY" -m pip --version >/dev/null 2>&1; then
  "$PY" -m ensurepip --upgrade
fi
"$PY" -m pip install --no-cache-dir --upgrade pip
"$PY" -m pip install --no-cache-dir -r requirements.txt
"$PY" -c "import reportlab, pypdf; print('bundled python: reportlab + pypdf OK')"
if [ "$ZIP" -eq 1 ] && [ ! -f "$TMP/rt/python/python3.exe" ]; then
  # the launcher invokes python3; Windows portable builds ship python.exe only
  cp "$TMP/rt/python/python.exe" "$TMP/rt/python/python3.exe"
fi

# --------------------------------------------------------- engine smoke test
# Prove this platform's kernel + the bundled python run the real engine
# BEFORE packaging anything.
echo "==> engine smoke (bundled python + $KERNEL_LIB)"
# The kernel library path uses Windows format on Windows (for ctypes to
# find omnidecide.dll), but the Python executable and run directory
# use POSIX paths (tar extracts to POSIX, MSYS Python handles both).
if [ "$PLATFORM" = "windows-x64" ]; then
  export OMNIDECIDE_C_LIB="$ROOT_WIN/vendor/omnidecide-c/build/$KERNEL_LIB"
  PY="$TMP/rt/python/$PY_BIN"
  SMOKE="$TMP/smoke-run"
else
  export OMNIDECIDE_C_LIB="$ROOT/vendor/omnidecide-c/build/$KERNEL_LIB"
  PY="$TMP/rt/python/$PY_BIN"
  SMOKE="$TMP/smoke-run"
fi
"$PY" attune-engine/engine.py \
  --folder attune-sample-data/candidates \
  --profile attune-data/templates/example-senior-data-engineer.json \
  --run-dir "$SMOKE"
"$PY" - "$SMOKE" <<'PYEOF'
import json, sys
run = sys.argv[1]
m = json.load(open(run + "/results.json"))
ver = m.get("omnidecide_version") or m.get("audit", {}).get("manifest", {}).get("omnidecide_version")
assert ver == "omnidecide-c 2.0.0", f"unexpected kernel id in manifest: {ver!r}"
print("engine smoke OK:", ver)
PYEOF

# ------------------------------------------------------------------ staging
echo "==> staging the distribution"
STAGE="$TMP/stage"
APP="$STAGE/$DIST_NAME/app"
mkdir -p "$APP" "$STAGE/$DIST_NAME/runtime"

# Python runtime with the preinstalled PDF-export packages.
mv "$TMP/rt/python" "$STAGE/$DIST_NAME/runtime/python"
# Use POSIX path for Python executable (tar extracts to POSIX paths on Windows)
PY="$STAGE/$DIST_NAME/runtime/python/$PY_BIN"

# ------------------------------------------------------------- slim runtime
# The install_only build carries developer-facing extras the packaged app
# never loads: full DWARF debug info in libpython (the single largest block,
# ~200 MB), Tcl/Tk + Tix + IDLE, lib2to3, ensurepip wheels, C headers,
# pkg-config data, terminfo/man pages and build-only config dirs. Trim them
# so the archive ships only what the app needs to run. Every removal is
# best-effort (guarded) because layouts differ slightly per platform.
RT="$STAGE/$DIST_NAME/runtime/python"
PY_LIB="$(echo "$RT"/lib/python3.* | tr ' ' '\n' | head -1)"
rm -rf "$RT/include" "$RT/lib/pkgconfig" "$RT/share/terminfo" "$RT/share/man" \
       "$RT/lib/libpython3.so" \
       "$RT/lib/tcl8" "$RT/lib/tcl8.6" "$RT/lib/tk8.6" "$RT/lib/Tix8.4.3" \
       "$RT/lib/itcl4.2.2" "$RT/lib/thread2.8.7" "$RT/tcl" "$RT/tk" \
       "$RT/bin/python3.12-config" 2>/dev/null || true
if [ -d "$PY_LIB" ]; then
  rm -rf "$PY_LIB/test" "$PY_LIB/idlelib" "$PY_LIB/pydoc_data" \
         "$PY_LIB/tkinter" "$PY_LIB/turtledemo" "$PY_LIB/lib2to3" \
         "$PY_LIB/ensurepip" \
         "$PY_LIB"/config-3.* \
         "$PY_LIB"/lib-dynload/_tkinter.*.so \
         "$PY_LIB"/lib-dynload/_tkinter*.pyd 2>/dev/null || true
fi
rm -f "$RT/bin"/idle3* "$RT/bin"/2to3* "$RT/bin"/pydoc3* 2>/dev/null || true
# Strip debug symbols from the runtime binaries. Windows runners have no
# strip (and MSVC builds carry no DWARF anyway), so this is guarded.
if command -v strip >/dev/null 2>&1; then
  case "$(uname -s)" in
    Darwin) STRIP_FLAGS="-x" ;;
    *)      STRIP_FLAGS="--strip-unneeded" ;;
  esac
  # shellcheck disable=SC2086  # STRIP_FLAGS is a deliberate multi-flag list
  find "$RT/bin" "$RT/lib" -maxdepth 1 -type f \
    \( -name "python*" -o -name "libpython*" \) \
    -exec strip $STRIP_FLAGS {} + 2>/dev/null || true
fi
echo "==> runtime slimmed: $(du -sh "$RT" | cut -f1)"

# The vanilla web app: the stdlib-only server plus static frontend. Python
# copytree materializes symlinks as real files, which survives platforms
# where plain cp -r can trip. On Windows, MSVC Python cannot resolve POSIX
# paths (e.g., /d/a/repo/repo) for the source, but handles POSIX paths in
# the staging directory fine. Use Windows-style paths for source root.
if [ "$PLATFORM" = "windows-x64" ]; then
  SRC_ROOT="$ROOT_WIN"
else
  SRC_ROOT="$ROOT"
fi
SRC_ROOT="$SRC_ROOT" APP="$APP" "$PY" - <<PYEOF
import os, shutil
root = os.environ["SRC_ROOT"]
app = os.environ["APP"]
shutil.copy(os.path.join(root, "server.py"), os.path.join(app, "server.py"))
shutil.copytree(os.path.join(root, "web"), os.path.join(app, "web"), symlinks=False, dirs_exist_ok=True)
print("web app staged")
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
# On Windows, use POSIX paths throughout - MSYS tar/Python work with both
# formats consistently. Using mixed POSIX/Windows paths causes issues.
mkdir -p "$DIST_ROOT"
ART="$DIST_ROOT/$DIST_NAME.$ARCHIVE_EXT"
rm -f "$ART" "$ART.sha256"
if [ "$ZIP" -eq 1 ]; then
  # Python zipfile with MSYS accepts POSIX paths for both input and output.
  # Previously attempted Windows paths (ART_WIN) caused silent failures.
  "$PY" - "$ART" "$STAGE/$DIST_NAME" <<'PYEOF'
import os, sys, zipfile
art, src = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(art, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
  for base, dirs, files in os.walk(src):
    for f in sorted(files):
      p = os.path.join(base, f)
      arcname = os.path.relpath(p, os.path.dirname(src)).replace(os.sep, "/")
      zf.write(p, arcname)
print(f"zip: {os.path.getsize(art) / 1e6:.1f} MB")
PYEOF
else
  # tar preserves the executable bits on the launchers using POSIX paths
  tar -czf "$ART" -C "$TMP/stage" "$DIST_NAME"
fi

# sha256 calculation - Python reads the archive and writes sha256.
# Use POSIX paths throughout on Windows (MSYS Python handles this).
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
