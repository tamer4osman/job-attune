#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Job Attune smoke test - fast health check for the vanilla UI + Python server.

Boots its own server on a scratch port, then verifies in ~30-60 s:

  1. boot        server starts and answers /api
  2. static      index.html, css, all 13 JS modules, logo, robots.txt;
                 path traversal is contained to web/
  3. guard       loopback protection: no X-Attune-Client -> 403,
                 Sec-Fetch-Site: cross-site -> 403, header present -> 200
  4. api         every route answers with the right shape (13 routes)
  5. throughput  scan rate, engine candidates/files per minute,
                 PDF report generation rate  (answers: files per minute?)
  6. browser     Chromium loads the wizard, scans, loads the template,
                 runs the engine and renders results - zero JS errors

Usage:
  python3 scripts/smoke_test.py            # full smoke (default)
  python3 scripts/smoke_test.py --api-only # skip the browser phase
  python3 scripts/smoke_test.py --quick    # static + guard + api only (~10 s)
  python3 scripts/smoke_test.py --keep     # keep smoke-run dirs for inspection

Exit codes: 0 = all pass, 1 = failures, 2 = environment problem.
"""

import argparse
import http.client
import json
import os
import pathlib
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNS_DIR = PROJECT_ROOT / "attune-data" / "runs"
CLIENT_HDR = {"X-Attune-Client": "smoke"}

SAMPLE = "attune-sample-data/candidates"
CORPORA = [
    ("sample-6", SAMPLE),
    ("trades-12", "attune-data/casestudy-trades/candidates"),
    ("plumber-12", "attune-data/casestudy-plumber/candidates"),
]

STATIC_ASSETS = [
    "/", "/index.html", "/css/app.css", "/js/app.js", "/js/api.js", "/js/ui.js",
    "/js/charts.js", "/js/icons.js", "/js/views/candidate-detail.js",
    "/js/views/folder-picker.js", "/js/views/governance.js",
    "/js/views/job-profile.js", "/js/views/position-report.js",
    "/js/views/results.js", "/js/views/run-monitor.js", "/logo.svg",
    "/robots.txt",
    # PWA layer: installable web app (manifest + offline service worker)
    "/manifest.webmanifest", "/sw.js",
    "/icons/icon-192.png", "/icons/icon-512.png",
    "/icons/icon-maskable-192.png", "/icons/icon-maskable-512.png",
]

results = []          # (name, ok, detail)
timings = {}          # phase -> seconds
throughput = []       # (label, value, unit)


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    mark = "PASS" if ok else "FAIL"
    line = f"  [{mark}] {name}"
    if detail and not ok:
        line += f"  <- {detail}"
    print(line, flush=True)
    return ok


def phase(title):
    print(f"\n== {title} " + "=" * max(0, 64 - len(title)), flush=True)


# --------------------------------------------------------------------------- #
# HTTP helper (http.client: full control over raw paths + headers)
# --------------------------------------------------------------------------- #

def req(port, method, path, body=None, headers=None, timeout=180):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    hdrs = {"Content-Type": "application/json", "Accept": "*/*"}
    hdrs.update(headers or {})
    t0 = time.perf_counter()
    try:
        conn.request(method, path, body=payload, headers=hdrs)
        resp = conn.getresponse()
        data = resp.read()
        status, ctype = resp.status, resp.getheader("Content-Type", "")
    finally:
        conn.close()
    elapsed = time.perf_counter() - t0
    parsed = None
    if "json" in ctype and data:
        try:
            parsed = json.loads(data)
        except ValueError:
            parsed = None
    return status, (parsed if parsed is not None else data), ctype, elapsed


# --------------------------------------------------------------------------- #
# Phases
# --------------------------------------------------------------------------- #

def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def boot_server(port, log_path):
    env = dict(os.environ, ATTUNE_PORT=str(port), ATTUNE_HOST="127.0.0.1",
               PYTHONUNBUFFERED="1")
    log_fh = open(log_path, "wb")
    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "server.py")],
        cwd=str(PROJECT_ROOT), env=env,
        stdout=log_fh, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        if proc.poll() is not None:
            break
        try:
            status, _payload, _, _ = req(port, "GET", "/api", headers=CLIENT_HDR, timeout=3)
            if status == 200:
                return proc, log_fh
        except OSError:
            pass
        time.sleep(0.15)
    proc.kill()
    log_fh.flush()
    tail = pathlib.Path(log_path).read_text(errors="replace")[-800:]
    raise SystemExit(f"server did not boot on port {port}. Log tail:\n{tail}")


def phase_static(port):
    phase("2. static frontend")
    ok_all = True
    for asset in STATIC_ASSETS:
        status, data, ctype, _ = req(port, "GET", asset)
        nice = asset if asset != "/" else "/ (index)"
        # req() parses JSON-typed bodies into dicts - the PWA manifest is
        # application/manifest+json, so measure bytes only for raw payloads.
        ok = status == 200 and (len(data) > 50 if isinstance(data, bytes) else len(data) >= 10)
        if asset.endswith(".css"):
            ok = ok and "css" in ctype
        elif asset.endswith(".js"):
            ok = ok and ("javascript" in ctype)
        elif asset.endswith(".webmanifest"):
            ok = ok and "manifest+json" in ctype
        elif asset.endswith(".png"):
            ok = ok and ctype == "image/png" and data[:8] == b"\x89PNG\r\n\x1a\n"
        elif asset == "/" or asset.endswith(".html"):
            ok = ok and b"Job Attune" in data
        ok_all &= check(f"GET {nice} -> 200", ok, f"status={status} ctype={ctype} bytes={len(data)}")
    # PWA wiring: the shell must reference the manifest + worker so the app
    # is installable from a stock browser visit.
    status, data, _, _ = req(port, "GET", "/")
    ok_all &= check("index links the PWA manifest", b'rel="manifest"' in data)
    ok_all &= check("index registers the service worker", b"serviceWorker.register" in data)
    # containment: traversal out of web/ must 404 (raw dot-segments + encoded)
    for evil in ("/%2e%2e/server.py", "/js/../../../server.py", "/.../etc/passwd"):
        status, _, _, _ = req(port, "GET", evil)
        ok_all &= check(f"traversal blocked {evil}", status == 404, f"status={status}")
    status, _, _, _ = req(port, "GET", "/no-such-asset.js")
    ok_all &= check("unknown asset -> 404", status == 404, f"status={status}")
    return ok_all


def phase_guard(port):
    phase("3. loopback guard (port of src/middleware.ts)")
    ok_all = True
    status, payload, _, _ = req(port, "GET", "/api")
    ok_all &= check("no X-Attune-Client -> 403", status == 403, f"status={status}")
    status, _, _, _ = req(port, "GET", "/api", headers={**CLIENT_HDR, "Sec-Fetch-Site": "cross-site"})
    ok_all &= check("Sec-Fetch-Site: cross-site -> 403", status == 403, f"status={status}")
    status, payload, _, _ = req(port, "GET", "/api", headers=CLIENT_HDR)
    ok_all &= check("header present -> 200 Hello, world!",
                    status == 200 and payload.get("message") == "Hello, world!",
                    f"status={status} body={payload}")
    status, _, _, _ = req(port, "POST", "/api/scan", body={"folder": SAMPLE})
    ok_all &= check("guard covers POST routes too", status == 403, f"status={status}")
    return ok_all


def phase_api(port, profile):
    phase("4. api surface (13 routes)")
    ok_all = True
    # template list + fetch
    status, payload, _, _ = req(port, "GET", "/api/template", headers=CLIENT_HDR)
    names = [t.get("name") for t in payload.get("templates", [])]
    ok_all &= check("GET /api/template lists examples",
                    status == 200 and "example-senior-data-engineer" in names,
                    f"status={status} names={names}")
    status, payload, _, _ = req(port, "GET",
                                "/api/template?name=example-senior-data-engineer",
                                headers=CLIENT_HDR)
    ok = status == 200 and payload.get("profile", {}).get("job", {}).get("title") == "Senior Data Engineer"
    ok_all &= check("GET /api/template?name=... returns profile", ok, f"status={status}")
    # browse
    status, payload, _, _ = req(port, "POST", "/api/browse", body={"path": str(PROJECT_ROOT)},
                                headers=CLIENT_HDR)
    dirs = [d["name"] for d in payload.get("directories", [])]
    ok_all &= check("POST /api/browse lists project root",
                    status == 200 and "web" in dirs and "attune-engine" in dirs,
                    f"status={status} dirs={dirs[:6]}")
    status, payload, _, _ = req(port, "POST", "/api/browse", body={"path": "/no/such/dir"},
                                headers=CLIENT_HDR)
    ok_all &= check("browse unknown path -> 404", status == 404, f"status={status}")
    # scan
    status, payload, _, _ = req(port, "POST", "/api/scan", body={"folder": SAMPLE},
                                headers=CLIENT_HDR)
    n_cands = len(payload.get("candidates", []))
    ok_all &= check("POST /api/scan finds 6 sample candidates",
                    status == 200 and n_cands == 6, f"status={status} n={n_cands}")
    status, payload, _, _ = req(port, "POST", "/api/scan", body={"folder": "no-such-folder"},
                                headers=CLIENT_HDR)
    ok_all &= check("scan unknown folder -> 404", status == 404, f"status={status}")
    # run list + error shapes
    status, payload, _, _ = req(port, "GET", "/api/run", headers=CLIENT_HDR)
    ok_all &= check("GET /api/run lists runs", status == 200 and isinstance(payload.get("runs"), list),
                    f"status={status}")
    status, _, _, _ = req(port, "GET", "/api/run/status?run_id=bogus", headers=CLIENT_HDR)
    ok_all &= check("status of unknown run -> 404", status == 404, f"status={status}")
    status, _, _, _ = req(port, "GET", "/api/audit?run_id=bogus", headers=CLIENT_HDR)
    ok_all &= check("audit of unknown run -> 404", status == 404, f"status={status}")
    status, _, _, _ = req(port, "POST", "/api/run", body={"folder": SAMPLE},
                          headers=CLIENT_HDR)
    ok_all &= check("run without profile -> 400", status == 400, f"status={status}")
    status, _, _, _ = req(port, "POST", "/api/run", body={"profile": profile},
                          headers=CLIENT_HDR)
    ok_all &= check("run without folder -> 400", status == 400, f"status={status}")
    status, payload, _, _ = req(port, "GET", "/api/template?name=../evil", headers=CLIENT_HDR)
    ok_all &= check("template name injection -> 400/404", status in (400, 404), f"status={status}")
    return ok_all


def wait_done(port, run_id, deadline_s=180):
    t0 = time.perf_counter()
    deadline = time.time() + deadline_s
    last = {}
    while time.time() < deadline:
        _status, payload, _, _ = req(port, "GET", f"/api/run/status?run_id={run_id}",
                                    headers=CLIENT_HDR, timeout=10)
        last = payload if isinstance(payload, dict) else {}
        if last.get("stage") in ("done", "error"):
            return last, time.perf_counter() - t0
        time.sleep(0.2)
    return {"stage": "timeout"}, time.perf_counter() - t0


def phase_throughput(port, profile):
    """Scan + engine + report rates - the 'files per minute' numbers."""
    phase("5. throughput (scan / engine / reports)")
    ok_all = True
    total_files = 0
    total_cands = 0

    # ---- scan rate --------------------------------------------------------
    scan_t0 = time.perf_counter()
    for label, folder in CORPORA:
        status, payload, _, _ = req(port, "POST", "/api/scan", body={"folder": folder},
                                    headers=CLIENT_HDR)
        cands = payload.get("candidates", [])
        files = sum(len(c.get("files", [])) for c in cands)
        total_files += files
        total_cands += len(cands)
        ok_all &= check(f"scan {label}: {len(cands)} candidates / {files} files",
                        status == 200 and len(cands) > 0, f"status={status}")
    scan_wall = time.perf_counter() - scan_t0
    if scan_wall < 0.05:
        # 3 local HTTP round-trips dominate: report honestly, not as a huge rate
        throughput.append((f"folder scan ({total_files} files, I/O-bound)",
                           total_files, "files in {:.1f} ms - effectively instant".format(scan_wall * 1000)))
    else:
        throughput.append(("folder scan", total_files / scan_wall * 60, "files/min"))

    # ---- engine rate (one run per corpus, polled to done) ------------------
    engine_t0 = time.perf_counter()
    engine_files = 0
    run_ids = []
    for label, folder in CORPORA:
        status, payload, _, _ = req(port, "POST", "/api/run",
                                    body={"folder": folder, "profile": profile,
                                          "pseudonymous": True, "roleOverrides": {}},
                                    headers=CLIENT_HDR)
        run_id = payload.get("runId")
        run_ids.append(run_id)
        prog, wall = wait_done(port, run_id)
        _status2, res_payload, _, _ = req(port, "GET",
                                          f"/api/run/results?run_id={run_id}",
                                          headers=CLIENT_HDR)
        ranked = len((res_payload.get("results") or {}).get("ranking", []))
        files = sum(1 for _ in (PROJECT_ROOT / folder).glob("*/*.pdf"))
        engine_files += files
        ok_all &= check(f"engine run {label}: done in {wall:.1f}s, ranked {ranked}",
                        prog.get("stage") == "done" and ranked > 0,
                        f"stage={prog.get('stage')} ranked={ranked}")
    engine_wall = time.perf_counter() - engine_t0
    throughput.append(("engine scoring", total_cands / engine_wall * 60, "candidates/min"))
    throughput.append(("engine scoring", engine_files / engine_wall * 60, "files/min"))

    # ---- audit write + read on a real run ----------------------------------
    audit_run = run_ids[0]
    status, payload, _, _ = req(port, "POST", "/api/audit",
                                body={"run_id": audit_run, "action": "resolve",
                                      "candidate_ref": "SMOKE-1", "kind": "note",
                                      "decision": "acknowledged", "reviewer": "smoke-test"},
                                headers=CLIENT_HDR)
    ok_all &= check("POST /api/audit writes a decision",
                    status == 200 and payload.get("entry", {}).get("reviewer") == "smoke-test",
                    f"status={status}")
    status, payload, _, _ = req(port, "GET", f"/api/audit?run_id={audit_run}",
                                headers=CLIENT_HDR)
    ok_all &= check("GET /api/audit reads it back",
                    status == 200 and len(payload.get("decisions", [])) >= 1,
                    f"status={status}")

    # ---- report generation + download --------------------------------------
    rep_t0 = time.perf_counter()
    status, payload, _, _ = req(port, "POST", "/api/report",
                                body={"run_id": audit_run}, headers=CLIENT_HDR, timeout=150)
    rep_wall = time.perf_counter() - rep_t0
    files = payload.get("files", []) if isinstance(payload, dict) else []
    ok_all &= check(f"POST /api/report generated {len(files)} PDFs in {rep_wall:.1f}s",
                    status == 200 and len(files) > 0, f"status={status}")
    throughput.append(("pdf reports", len(files) / rep_wall * 60, "files/min"))
    if files:
        fname = files[0].get("file", "batch-report.pdf")
        status, blob, ctype, _ = req(port, "GET",
                                     f"/api/report?run_id={audit_run}&file={fname}",
                                     headers=CLIENT_HDR, timeout=60)
        ok_all &= check(f"GET /api/report downloads {fname} ({ctype})",
                        status == 200 and bytes(blob[:5]) == b"%PDF-" and len(blob) > 10000,
                        f"status={status} ctype={ctype} bytes={len(blob)}")
    return ok_all, run_ids


def phase_browser(port, shots_dir):
    phase("6. browser smoke (Chromium + Playwright)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [SKIP] playwright not installed - run: pip install playwright && playwright install chromium")
        return True
    ok_all = True
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: errors.append(f"console.error: {m.text}")
                if m.type == "error" else None)

        page.goto(f"http://127.0.0.1:{port}/", wait_until="load")
        page.wait_for_timeout(400)
        ok_all &= check("title + 4-step wizard render",
                        page.title() == "Job Attune - Hire for aptitude"
                        and page.locator(".step").count() == 4,
                        page.title())

        page.fill("#folder", SAMPLE)
        page.click("text=Scan folder")
        page.wait_for_selector("text=Validation preview", timeout=15000)
        ok_all &= check("UI scan -> 6 candidate tiles",
                        page.locator(".candidate-tile").count() == 6)

        page.click("text=Continue to job profile")
        page.wait_for_selector("text=Company & job profile", timeout=5000)
        page.click("text=Load example")
        page.wait_for_timeout(600)
        ok_all &= check("template loads into the form",
                        page.input_value("#jtitle") == "Senior Data Engineer",
                        page.input_value("#jtitle"))

        page.click("text=Start screening run")
        page.wait_for_selector("text=View results", timeout=120000)
        page.click("text=View results")
        page.wait_for_selector(".stat-grid", timeout=20000)
        page.wait_for_timeout(600)
        stats = page.locator(".stat-value").all_inner_texts()
        ok_all &= check("results overview: 6 candidates + charts",
                        stats and stats[0] == "6" and page.locator(".chart-box svg").count() >= 3,
                        f"stats={stats[:3]}")
        shots_dir.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(shots_dir / "smoke-results.png"), full_page=True)

        page.click("button[role='tab'] >> text=Ranking")
        page.wait_for_selector(".rank-row", timeout=5000)
        ok_all &= check("ranking tab: 6 rows",
                        page.locator(".rank-row").count() == 6)
        page.screenshot(path=str(shots_dir / "smoke-ranking.png"), full_page=True)

        js_errors = [e for e in errors if "favicon" not in e]
        ok_all &= check("zero JS errors during the whole flow", len(js_errors) == 0,
                        "; ".join(js_errors[:3]))
        browser.close()
    return ok_all


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser(description="Job Attune smoke test")
    ap.add_argument("--api-only", action="store_true", help="skip the browser phase")
    ap.add_argument("--quick", action="store_true", help="static + guard + api only")
    ap.add_argument("--keep", action="store_true", help="keep smoke-test run directories")
    ap.add_argument("--port", type=int, default=0, help="fixed server port (default: random free)")
    args = ap.parse_args()

    t_start = time.time()
    port = args.port or free_port()
    print(f"Job Attune smoke test - project {PROJECT_ROOT}")
    print(f"scratch server port: {port}")

    runs_before = set(os.listdir(RUNS_DIR)) if RUNS_DIR.is_dir() else set()
    log_path = tempfile.mktemp(prefix="attune-smoke-server-", suffix=".log")

    proc = None
    log_fh = None
    try:
        phase("1. boot")
        t0 = time.perf_counter()
        proc, log_fh = boot_server(port, log_path)
        timings["server boot"] = time.perf_counter() - t0
        check(f"server.py boots in {timings['server boot']:.1f}s", True)

        ok = phase_static(port)
        timings["static"] = 0
        ok &= phase_guard(port)

        _status, payload, _, _ = req(port, "GET",
                                     "/api/template?name=example-senior-data-engineer",
                                     headers=CLIENT_HDR)
        profile = payload.get("profile", {})
        ok &= phase_api(port, profile)

        if not args.quick:
            ok_tp, _run_ids = phase_throughput(port, profile)
            ok &= ok_tp
            if not args.api_only:
                ok &= phase_browser(port, pathlib.Path("/tmp/smoke-shots"))
    finally:
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if log_fh:
            log_fh.close()

    # cleanup: remove only the run dirs this smoke test created
    if not args.keep and RUNS_DIR.is_dir():
        created = set(os.listdir(RUNS_DIR)) - runs_before
        for entry in created:
            shutil.rmtree(RUNS_DIR / entry, ignore_errors=True)
        if created:
            print(f"\ncleaned up {len(created)} smoke-test run dir(s)")

    wall = time.time() - t_start
    failed = [r for r in results if not r[1]]

    print("\n" + "=" * 70)
    print(f"SMOKE RESULT: {len(results) - len(failed)}/{len(results)} checks passed "
          f"in {wall:.1f} s")
    if throughput:
        print("\nthroughput (this machine, small corpora - not a benchmark suite):")
        for label, value, unit in throughput:
            print(f"  {label:<18} {value:,.0f} {unit}")
    if failed:
        print(f"\n{len(failed)} FAILURE(S):")
        for name, _, detail in failed:
            print(f"  - {name}: {detail}")
        sys.exit(1)
    print("all green - the vanilla UI + Python server are healthy")
    sys.exit(0)


if __name__ == "__main__":
    main()
