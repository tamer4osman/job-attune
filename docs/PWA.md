# PWA - the installable web app

Job Attune ships as a **Progressive Web App**: the same vanilla UI, served by
the same stdlib-only `server.py`, installable as a standalone app on Windows,
macOS, Linux, Android and iOS with zero extra dependencies, zero build step
and zero bytes of extra runtime shipped. A window of its own, its own
dock/taskbar icon, an instant-loading cached shell - and none of the
framework machinery a desktop shell would add.

The Electron alternative (real installers, no browser involved) lives in
[`electron/`](../electron/README.md) and is packaged by the *Desktop
(Electron)* workflow. It reuses the exact same UI and server; use it when
you want to hand users an `.exe`/`.dmg`/`.AppImage` instead of a browser
install. The two channels are additive, not competing.

## Install from the running server

Start Job Attune any way you like (standalone bundle, `python3 server.py`,
Docker) and open `http://127.0.0.1:3000` in a browser:

| Platform | How to install |
| --- | --- |
| Chrome / Edge (Windows, macOS, Linux) | Install icon in the address bar, or menu → *Cast, save and share → Install page as app* (Chrome) / *Apps → Install this site as an app* (Edge) |
| macOS Safari | *File → Add to Dock* |
| iOS Safari | *Share → Add to Home Screen* |
| Android Chrome | Menu → *Install app* / *Add to Home Screen* |

The installed app opens in its own window (`display: standalone`), with the
forest-green theme colour and the Job Attune mark (the icons are rasterized
from `web/logo.svg` - see *Icons* below).

## What is cached - and what deliberately is not

The service worker (`web/sw.js`) keeps a strict two-layer policy:

- **Static shell, cached**: `index.html`, CSS, all JS modules, fonts, icons.
  The app opens instantly and still opens when the local server is down
  (navigations go network-first with the cached shell as fallback).
- **`/api`, never cached**: screening results, audit trails and candidate
  data always come from the live local server. If the server is unreachable
  the worker answers with an honest `503` JSON error that the UI displays -
  there is no stale-results mode. This is deliberate: no second storage
  layer duplicates candidate data (GDPR story), and the determinism/freshness
  contract ("every decision reproducible from the run directory") is never
  silently served from a cache.

Consequence: an installed PWA needs the local server running for actual
screening. Start it with `start.sh` / `start.bat` / `python3 server.py` /
Docker, then reload the app window.

## Files

| File | Purpose |
| --- | --- |
| `web/manifest.webmanifest` | Identity: name, icons, `display: standalone`, theme/background colours |
| `web/sw.js` | Offline shell + `/api` network-only policy; cache named `job-attune-<version>` |
| `web/icons/icon-{192,512}.png` | `purpose: "any"` icons (transparent margins, as the SVG) |
| `web/icons/icon-maskable-{192,512}.png` | `purpose: "maskable"` icons, full-bleed forest tile, mark inside the W3C safe zone |
| `scripts/make_icons.py` | Regenerates all icons from `web/logo.svg` (cairosvg + Pillow) |
| `scripts/check_pwa.py` | PWA gate: manifest schema, icon geometry, precache-path coverage, served headers |

Server-side support is two small edits in `server.py`: pinned MIME types
(`application/manifest+json` for `.webmanifest`, `font/woff2`) and
`Cache-Control: no-cache` for `sw.js` + the manifest so updates revalidate
promptly (everything else stays `no-store` - there is no build step and no
cache-busting, the worker *is* the cache).

## Updating the app

Bump `CACHE_VERSION` in `web/sw.js` when releasing (keep it in lockstep with
the version in `CHANGELOG.md`). On the next load the worker installs the new
shell, deletes the previous cache on activate and takes over; no manual
hard-reload needed. The worker never caches `/api` responses, so scoring
behaviour is never affected by a cached shell.

## Icons

Icons are generated, never hand-edited:

```bash
pip install cairosvg pillow   # one-time dev dependency
python3 scripts/make_icons.py # web/icons/* + electron/build/icon.png
```

If `web/logo.svg` changes, re-run the script and commit the result - CI
(`scripts/check_pwa.py`) verifies the manifest still matches the real PNG
geometry.

## Verification

```bash
python3 scripts/check_pwa.py      # manifest + icons + sw coverage + live server headers
node --check web/sw.js            # syntax
python3 scripts/smoke_test.py --quick   # static phase now covers the PWA assets too
```

CI runs the `pwa` job in ci.yml on every push/PR (no kernel build needed -
static endpoints never spawn the engine), and the Release workflow's Linux
boot smoke additionally proves the packaged archives serve the manifest and
service worker.
