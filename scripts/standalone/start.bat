@rem SPDX-License-Identifier: Apache-2.0
@rem SPDX-FileCopyrightText: 2026 Tamer Osman
@rem
@rem Job Attune standalone launcher (Windows). Starts the local UI server on
@rem http://127.0.0.1:3000 using the bundled Node.js and CPython runtimes
@rem and the prebuilt omnidecide-c kernel. Keep this window open; Ctrl+C
@rem stops the server.
@echo off
setlocal
set "ROOT=%~dp0"
set "APP=%ROOT%app"

if not exist "%ROOT%runtime\node\node.exe" (
  echo start: bundled Node.js runtime missing under runtime\node - is the archive complete?
  pause
  exit /b 1
)
if not exist "%APP%\vendor\omnidecide-c\build\omnidecide.dll" (
  echo start: compiled kernel missing at app\vendor\omnidecide-c\build\omnidecide.dll
  pause
  exit /b 1
)

rem The web app spawns `python3` for every run/report, so the bundled
rem Python (with its python3.exe alias) must lead the PATH; Node is invoked
rem by absolute path below.
set "PATH=%ROOT%runtime\python;%PATH%"
set "ATTUNE_ROOT=%APP%"
set "OMNIDECIDE_C_LIB=%APP%\vendor\omnidecide-c\build\omnidecide.dll"
set "NODE_ENV=production"
set "PORT=3000"
set "HOSTNAME=127.0.0.1"
set "PYTHONUNBUFFERED=1"

echo Job Attune - local UI on http://127.0.0.1:3000 (Ctrl+C stops the server)
cd /d "%APP%"
"%ROOT%runtime\node\node.exe" server.js
