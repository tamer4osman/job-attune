// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// Job Attune service worker - the offline installable-app layer.
//
// What it does:
//   * caches the static app shell (HTML/CSS/JS/fonts/icons) so an installed
//     PWA opens instantly and still opens when the local server is down;
//   * NEVER caches /api responses - screening results, audit trails and
//     candidate data must always come from the live local server (freshness
//     + the GDPR story: nothing is duplicated into a second storage layer);
//   * falls back to the cached shell for navigations when the server is
//     unreachable, and answers failed /api calls with an honest 503 JSON
//     body that the UI surfaces as a readable error.
//
// Update protocol: bump CACHE_VERSION below in lockstep with the release
// version in CHANGELOG.md (the web footer and the manifest stay generic).
// The old cache is deleted on activate; skipWaiting/clientsClaim make the
// new shell go live on the next load without a manual hard-reload.

const CACHE_VERSION = "v1.2.0";
const CACHE = `job-attune-${CACHE_VERSION}`;

/** Files the shell cannot open without - install fails if any of these miss. */
const CORE_ASSETS = [
  "/",
  "/index.html",
  "/css/app.css",
  "/js/app.js",
  "/js/api.js",
  "/js/sw-register.js",
  "/js/ui.js",
];

/** Best-effort precache: a missing file must not brick the whole update. */
const SHELL_ASSETS = [
  "/js/icons.js",
  "/js/charts.js",
  "/js/views/candidate-detail.js",
  "/js/views/folder-picker.js",
  "/js/views/governance.js",
  "/js/views/job-profile.js",
  "/js/views/position-report.js",
  "/js/views/results.js",
  "/js/views/run-monitor.js",
  "/manifest.webmanifest",
  "/logo.svg",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/icon-maskable-192.png",
  "/icons/icon-maskable-512.png",
  "/fonts/boldonse-400.woff2",
  "/fonts/dmsans-var.woff2",
  "/fonts/dmsans-400i.woff2",
  "/fonts/playfairdisplay-var.woff2",
  "/fonts/playfairdisplay-400i.woff2",
];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(CORE_ASSETS);
    await Promise.allSettled(
      SHELL_ASSETS.map(async (asset) => {
        const res = await fetch(asset);
        if (res.ok) await cache.put(asset, res);
      }),
    );
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(
      names.filter((name) => name.startsWith("job-attune-") && name !== CACHE)
        .map((name) => caches.delete(name)),
    );
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return; // POST run/report calls go to the network
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // never touch third-party

  if (url.pathname === "/api" || url.pathname.startsWith("/api/")) {
    event.respondWith(apiNetworkOnly(req));
    return;
  }
  if (req.mode === "navigate") {
    event.respondWith(navigationNetworkFirst(req));
    return;
  }
  event.respondWith(staleWhileRevalidate(req));
});

/** /api: live server or nothing - results are never served from a cache. */
async function apiNetworkOnly(req) {
  try {
    return await fetch(req);
  } catch (err) {
    return new Response(
      JSON.stringify({
        error: "Offline: the Job Attune server is not reachable from this "
          + "window. Start the local server (start.sh / start.bat) and reload.",
      }),
      {
        status: 503,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "no-store",
        },
      },
    );
  }
}

/** Navigations: fresh page when the server is up, cached shell when not. */
async function navigationNetworkFirst(req) {
  const cache = await caches.open(CACHE);
  try {
    const fresh = await fetch(req);
    if (fresh.ok) await cache.put("/index.html", fresh.clone());
    return fresh;
  } catch (err) {
    const cached = await cache.match("/index.html");
    if (cached) return cached;
    return new Response(
      "<!doctype html><meta charset=\"utf-8\"><title>Job Attune - offline</title>"
      + "<body style=\"font-family: sans-serif; background: #fefae7; color: #3b001b; "
      + "display: grid; place-items: center; min-height: 90vh;\">"
      + "<p>Offline and no cached shell yet - start the local server and reload.</p>",
      { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } },
    );
  }
}

/** Static assets: instant from cache, refreshed in the background. */
async function staleWhileRevalidate(req) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(req);
  const refresh = fetch(req).then((res) => {
    if (res.ok) cache.put(req, res.clone());
    return res;
  }).catch(() => null);
  return cached || (await refresh) || new Response("Not found", { status: 404 });
}
