#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
#
# macOS double-click entry point: runs start.sh next to it.
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/start.sh"
