@rem SPDX-License-Identifier: Apache-2.0
@rem SPDX-FileCopyrightText: 2026 Tamer Osman
@rem
@rem Job Attune standalone launcher (Windows). Starts the local UI server on
@rem http://127.0.0.1:3000 using the bundled CPython runtime and the prebuilt
@rem omnidecide-c kernel. Keep this window open; Ctrl+C stops the server.
@echo off
setlocal
set "ROOT=%~dp0"
set "APP=%ROOT%app"

if not exist "%ROOT%runtime\python\python.exe" (
  echo start: bundled CPython runtime missing under runtime\python - is the archive complete?
  pause
  exit /b 1
)
if not exist "%APP%\vendor\omnidecide-c\build\omnidecide.dll" (
  echo start: compiled kernel missing at app\vendor\omnidecide-c\build\omnidecide.dll
  pause
  exit /b 1
)

rem The web app spawns the engine and the PDF reporter as Python children,
rem so the bundled Python must lead the PATH.
set "PATH=%ROOT%runtime\python;%PATH%"
set "ATTUNE_ROOT=%APP%"
set "OMNIDECIDE_C_LIB=%APP%\vendor\omnidecide-c\build\omnidecide.dll"
set "PYTHONUNBUFFERED=1"

echo Job Attune - local UI on http://127.0.0.1:3000 (Ctrl+C stops the server)
cd /d "%APP%"
"%ROOT%runtime\python\python.exe" server.py
