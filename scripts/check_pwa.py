#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""PWA gate: manifest schema, icon geometry, service-worker shell coverage,
and the headers the local server actually serves for the installable web app.

Stdlib only, no kernel needed (static endpoints never spawn the engine):

    python3 scripts/check_pwa.py            # runs the checks below
    python3 scripts/check_pwa.py --no-boot  # skip the live server phase

Exit 0 = PWA install-ready. CI wiring: the `pwa` job in ci.yml.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB = PROJECT_ROOT / "web"

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'ok' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)
    return ok


def png_size(path: Path) -> tuple[int, int]:
    """PNG IHDR: width/height live at fixed offsets 16..24 of every PNG."""
    blob = path.read_bytes()
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path.name}: not a PNG")
    w, h = struct.unpack(">II", blob[16:24])
    return int(w), int(h)


def check_manifest() -> dict:
    phase = "manifest"
    print(f"--- {phase}")
    mp = WEB / "manifest.webmanifest"
    if not check("manifest exists", mp.is_file()):
        return {}
    try:
        m = json.loads(mp.read_text(encoding="utf-8"))
    except ValueError as exc:
        check("manifest parses as JSON", False, str(exc))
        return {}

    for key in ("name", "short_name", "description", "start_url", "scope",
                "display", "background_color", "theme_color", "icons"):
        check(f"manifest has {key}", key in m)
    check("display is standalone", m.get("display") == "standalone", repr(m.get("display")))
    check("start_url is in scope", str(m.get("start_url", "")).startswith(str(m.get("scope", "/"))))

    for icon in m.get("icons", []):
        src = str(icon.get("src", ""))
        purpose = str(icon.get("purpose", "any"))
        check(f"icon {src} purpose valid", purpose in ("any", "maskable"), purpose)
        path = WEB / src.lstrip("/")
        if not check(f"icon {src} exists", path.is_file()):
            continue
        if str(icon.get("type", "")) == "image/png":
            try:
                w, h = png_size(path)
            except ValueError as exc:
                check(f"icon {src} is a real PNG", False, str(exc))
                continue
            want = str(icon.get("sizes", "")).lower()
            check(f"icon {src} geometry matches {want}",
                  want == f"{w}x{h}", f"actual {w}x{h}")
        if purpose == "maskable":
            # Maskable canvases must be square (full-bleed re-padding in
            # scripts/make_icons.py guarantees a circular mask never clips).
            w, h = png_size(path)
            check(f"icon {src} is square", w == h, f"{w}x{h}")

    return m


def check_service_worker(m: dict) -> None:
    phase = "service worker"
    print(f"--- {phase}")
    swp = WEB / "sw.js"
    if not check("sw.js exists", swp.is_file()):
        return
    src = swp.read_text(encoding="utf-8")
    check("sw registers a fetch handler", "addEventListener(\"fetch\"" in src)
    check("sw skips waiting on install", "skipWaiting" in src)
    check("sw claims clients on activate", "clients.claim" in src)
    check("sw names its cache after a version",
          re.search(r'CACHE_VERSION\s*=\s*"v\d+\.\d+\.\d+"', src) is not None
          and re.search(r"job-attune-\$\{CACHE_VERSION\}", src) is not None)

    # Every cached path the worker mentions must exist in web/ - the classic
    # drift bug is renaming a view/font and leaving a stale precache entry.
    literals = set(re.findall(r'"(/[A-Za-z0-9_@?&=.\-/]*)"', src))
    static_paths = {p for p in literals if not p.startswith("/api")}
    for path in sorted(static_paths):
        # "/" and "/index.html" both resolve to the same file.
        target = WEB / path.lstrip("/")
        exists = target.is_file() or (path == "/" and (WEB / "index.html").is_file())
        check(f"precache path {path} exists in web/", exists)

    # /api must never be cached: the network-only wrapper must exist and the
    # precache lists must not contain api paths.
    check("sw forces /api onto the network", "apiNetworkOnly" in src and "fetch(req)" in src)
    check("sw precache holds no /api path", not any(p.startswith("/api") for p in static_paths))

    index = (WEB / "index.html").read_text(encoding="utf-8")
    check("index links the manifest", 'rel="manifest"' in index)
    # The registration call lives in an external module (web/js/sw-register.js)
    # so the inline CSP script-src 'self' stays satisfied without
    # 'unsafe-inline' - verify the module is wired up, not an inline script.
    sw_register = (WEB / "js" / "sw-register.js").read_text(encoding="utf-8")
    check("index loads the service-worker registration module",
          '/js/sw-register.js' in index)
    check("sw-register.js registers the service worker",
          "serviceWorker.register" in sw_register)
    check("index declares the theme color", "theme-color" in index)


def check_icons_served_sizes(m: dict) -> None:
    # The manifest is the source of truth; make sure the 512 icon is at least
    # 512 (Chrome requires a 512 icon for the richer install UI).
    icons = m.get("icons", [])
    png_sizes = {int(str(i.get("sizes", "0x0")).split("x")[0])
                 for i in icons if i.get("type") == "image/png"}
    check("manifest declares a 512px PNG icon", 512 in png_sizes, str(sorted(png_sizes)))
    check("manifest declares a maskable icon",
          any(i.get("purpose") == "maskable" for i in icons))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def serve_get(port: int, path: str) -> tuple[int, str, dict, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("GET", path, headers={"Accept": "*/*"})
    resp = conn.getresponse()
    data = resp.read()
    headers = {k.lower(): v for k, v in resp.getheaders()}
    ctype = headers.get("content-type", "")
    conn.close()
    return resp.status, ctype, headers, data


def check_served() -> None:
    phase = "live server"
    print(f"--- {phase}")
    port = free_port()
    env = dict(os.environ, ATTUNE_PORT=str(port), PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(
        [sys.executable, "server.py"], cwd=PROJECT_ROOT, env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    try:
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                status, _, _, _ = serve_get(port, "/manifest.webmanifest")
                if status == 200:
                    break
            except OSError:
                pass
            time.sleep(0.15)
        else:
            check("server boots", False, "manifest never returned 200")
            return
        check("server boots", True)

        status, ctype, headers, _ = serve_get(port, "/manifest.webmanifest")
        check("GET /manifest.webmanifest -> 200", status == 200, str(status))
        check("manifest Content-Type", ctype.startswith("application/manifest+json"), ctype)
        check("manifest revalidates (no-cache)", headers.get("cache-control") == "no-cache",
              headers.get("cache-control", ""))

        status, ctype, headers, _ = serve_get(port, "/sw.js")
        check("GET /sw.js -> 200", status == 200, str(status))
        check("sw Content-Type is JavaScript", "javascript" in ctype, ctype)
        check("sw revalidates (no-cache)", headers.get("cache-control") == "no-cache",
              headers.get("cache-control", ""))

        for icon in ("/icons/icon-192.png", "/icons/icon-512.png",
                     "/icons/icon-maskable-192.png", "/icons/icon-maskable-512.png"):
            status, ctype, _, blob = serve_get(port, icon)
            check(f"GET {icon} -> 200", status == 200, str(status))
            check(f"{icon} served as image/png", ctype == "image/png", ctype)
            check(f"{icon} payload is a PNG", blob[:8] == b"\x89PNG\r\n\x1a\n")

        status, _, headers, data = serve_get(port, "/")
        check("GET / -> 200", status == 200, str(status))
        check("/ links the manifest", b'rel="manifest"' in data)
        # CSP must be present and must not relax script-src with
        # 'unsafe-inline' (the app is fully external - that is the whole
        # point of the transport hardening).
        csp = headers.get("content-security-policy", "")
        check("GET / serves a Content-Security-Policy", bool(csp), csp)
        # script-src must not relax to unsafe-inline (style-src may, because
        # the DOM builder sets string style="" attributes - that is the one
        # deliberate relaxation and it is scoped to style-src only).
        script_src = ""
        for part in csp.split(";"):
            part = part.strip()
            if part.startswith("script-src"):
                script_src = part
        check("CSP script-src is 'self' only (no unsafe-inline)",
              script_src == "script-src 'self'", script_src or csp)
        # The registration script is an external module (web/js/sw-register.js)
        # so the inline CSP script-src 'self' stays satisfied - verify both
        # the module is served and it actually calls register().
        status, _, _, sw_data = serve_get(port, "/js/sw-register.js")
        check("GET /js/sw-register.js -> 200", status == 200, str(status))
        check("sw-register.js calls serviceWorker.register",
              b"serviceWorker.register" in sw_data)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> None:
    m = check_manifest()
    check_service_worker(m)
    check_icons_served_sizes(m)
    if "--no-boot" not in sys.argv:
        check_served()
    print()
    if failures:
        print(f"PWA gate: {len(failures)} check(s) FAILED: {', '.join(failures)}")
        raise SystemExit(1)
    print("PWA gate: all checks passed - manifest, icons, service worker and server headers are install-ready.")


if __name__ == "__main__":
    main()
