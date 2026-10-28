#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
#
# Job Attune standalone launcher (Linux / macOS). Starts the local UI
# server on http://127.0.0.1:3000 using the bundled Node.js and CPython
# runtimes and the prebuilt omnidecide-c kernel. Keep this window open;
# Ctrl+C stops the server.

set -eu

ROOT="$(cd "$(dirname "$0")" && pwd)"
APP="$ROOT/app"

case "$(uname -s)" in
  Darwin) KERNEL_LIB="libomnidecide.dylib" ;;
  *)      KERNEL_LIB="libomnidecide.so" ;;
esac

if [ ! -x "$ROOT/runtime/node/bin/node" ]; then
  echo "start: bundled Node.js runtime missing under runtime/node - is the archive complete?" >&2
  exit 1
fi
if [ ! -f "$APP/vendor/omnidecide-c/build/$KERNEL_LIB" ]; then
  echo "start: compiled kernel missing at app/vendor/omnidecide-c/build/$KERNEL_LIB" >&2
  exit 1
fi

# The web app spawns `python3` for every run/report, so the bundled Python
# must lead the PATH; Node is invoked by absolute path below.
export PATH="$ROOT/runtime/python/bin:$PATH"
export ATTUNE_ROOT="$APP"
export OMNIDECIDE_C_LIB="$APP/vendor/omnidecide-c/build/$KERNEL_LIB"
export NODE_ENV=production
export PORT=3000
export HOSTNAME=127.0.0.1
export PYTHONUNBUFFERED=1

echo "Job Attune - local UI on http://127.0.0.1:3000 (Ctrl+C stops the server)"
cd "$APP"
exec "$ROOT/runtime/node/bin/node" server.js
