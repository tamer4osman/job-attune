# Job Attune desktop shell (Electron)

An optional distribution channel that wraps the **existing** standalone app in
a native desktop window. It adds no second runtime: the engine, the compiled
`omnidecide-c` kernel, the demo corpus and the CPython runtime are the exact
artifacts `scripts/standalone/package.sh` already produces - the Electron
process just spawns `server.py` from that bundle on a random free loopback
port and supervises it.

```
┌─ Job Attune.app / .exe / .AppImage ───────────────────────────┐
│  Electron main (main.js)                                     │
│    └─ spawns: runtime/python/bin/python3 server.py           │
│              ATTUNE_ROOT=resources/bundle/app                │
│              OMNIDECIDE_C_LIB=resources/bundle/app/vendor/…  │
│              ATTUNE_PORT=<ephemeral 127.0.0.1 port>          │
│    └─ waits for GET /api/template (guarded API)              │
│    └─ BrowserWindow → http://127.0.0.1:<port>/               │
│         renderer: the vanilla web UI (sandboxed, no Node)    │
└──────────────────────────────────────────────────────────────┘
```

Security posture of the window: `contextIsolation: true`, `sandbox: true`,
`nodeIntegration: false`, all permission requests denied, no popups (real
external links open in the system browser), single-instance lock.

## Files

| File | Purpose |
| --- | --- |
| `main.js` | Electron main process: bundle resolution, server spawn/supervision, window |
| `preload.js` | `window.attuneDesktop = { isDesktop, platform }` - the only renderer bridge |
| `package.json` | Pins `electron` + `electron-builder`; keep `version` in lockstep with CHANGELOG |
| `electron-builder.yml` | Installer config; ships `standalone-bundle/` via `extraResources` |
| `build/icon.png` | 1024px icon source (regenerate with `python3 scripts/make_icons.py`) |
| `standalone-bundle/` | gitignored - the unpacked standalone archive (build input) |

## Build locally (Linux/macOS)

```bash
# 1. produce this platform's standalone bundle (kernel + engine + runtime)
bash scripts/standalone/package.sh

# 2. unpack it where electron-builder expects it
mkdir -p electron/standalone-bundle
tar -xzf dist/job-attune-standalone-*.tar.gz -C electron/standalone-bundle --strip-components=1

# 3. wrap it
cd electron && npm install && npx electron-builder --publish never
# artifacts land in electron/dist/
```

On Windows replace step 2 with `unzip dist\job-attune-standalone-windows-x64.zip`
and copy the inner `job-attune-standalone-windows-x64\*` into
`electron\standalone-bundle\`.

The CI workflow (`.github/workflows/electron.yml`) runs the same three steps on
all three runners - manual via *workflow_dispatch*, or automatically on `v*`
tags, in which case the installers attach to the GitHub Release.

## Dev mode without packaging

`npm start` against a repo checkout works when either of these holds:

- the repo has a compiled kernel (`vendor/omnidecide-c/build/<lib>`) and a
  system `python3` with `reportlab`/`pypdf` installed; or
- an unpacked standalone archive sits in `electron/standalone-bundle/`.

The bundled runtime is preferred automatically when present.

## Unsigned builds - what users see

The targets below are **not code-signed** (no certificates are configured):

| OS | Artifact | First-run behaviour |
| --- | --- | --- |
| Windows | `Job-Attune-Setup-*.exe`, `Job-Attune-Portable-*.exe` | SmartScreen "unknown publisher" - click *More info → Run anyway* |
| macOS (Apple Silicon) | `Job-Attune-*-mac-arm64.dmg` | Gatekeeper prompt - right-click → *Open*, or `xattr -cr /Applications/Job\ Attune.app` |
| Linux | `Job-Attune-*-linux-x64.AppImage` | `chmod +x` then run |

Adding signing later: set `mac.identity` + notarization (`afterSign` hook),
`win.certificateFile`/Azure signing, and Linux needs no signing for AppImage.
The bundle stays ~200 MB installed because it carries its own CPython - that
is the price of "no prerequisites, everything local".

## Why not Electron for the PWA?

It is an alternative, not a requirement: the PWA (`web/manifest.webmanifest`
+ `web/sw.js`, see `docs/PWA.md`) installs the same UI as a standalone app
from a stock browser with zero extra bytes shipped. Electron earns its keep
when you want real installers, a taskbar/dock presence independent of the
browser, and a guaranteed window that cannot be confused with a tab.
