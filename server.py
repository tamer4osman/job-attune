#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Job Attune local server - the whole web backend in one stdlib-only file.

Replaces the previous Next.js UI server (src/app/api/* + src/middleware.ts)
with a zero-dependency Python HTTP server that:

  * serves the vanilla HTML/CSS/JS frontend from ``web/`` (no build step);
  * implements the exact same ``/api`` contract as documented in docs/API.md
    (browse, scan, run, run/status, run/results, report, audit, template);
  * keeps the loopback guard: every ``/api`` request must carry the
    ``X-Attune-Client`` header, and ``Sec-Fetch-Site: cross-site`` requests
    are rejected outright (drive-by CSRF / DNS-rebinding mitigation);
  * spawns the deterministic Python engine and the PDF reporter as child
    processes, exactly like the old Node routes did.

Run it with:

    python3 server.py                 # http://127.0.0.1:3000

Environment: ``ATTUNE_ROOT`` relocates the project root (defaults to the
working directory); ``ATTUNE_HOST`` / ``ATTUNE_PORT`` rebind the listener
(defaults: 127.0.0.1:3000 - keep it loopback-bound, see docs/API.md).
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
import unicodedata
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

# --------------------------------------------------------------------------- #
# Paths (same layout the Next.js server used; the tree stays relocatable)
# --------------------------------------------------------------------------- #

PROJECT_ROOT = Path(os.environ.get("ATTUNE_ROOT") or os.getcwd()).resolve()
DATA_ROOT = PROJECT_ROOT / "attune-data"
RUNS_DIR = DATA_ROOT / "runs"
TEMPLATES_DIR = DATA_ROOT / "templates"
ENGINE = PROJECT_ROOT / "attune-engine" / "engine.py"
REPORTER = PROJECT_ROOT / "attune-engine" / "make_report.py"
WEB_DIR = PROJECT_ROOT / "web"

HOST = os.environ.get("ATTUNE_HOST", "127.0.0.1")
PORT = int(os.environ.get("ATTUNE_PORT", "3000"))

#: How long a run may go without progress.json before /api/run/status calls
#: it failed (mirrors the old STALE_AFTER_MS).
STALE_AFTER_S = 120

#: Same alias sets and tie-breaking as the engine's classifier.
CV_ALIASES = ["resume", "cv", "lebenslauf", "curriculumvitae", "curriculum", "vitae"]
COVER_ALIASES = ["cover", "coverletter", "letter", "motivation", "motivationsschreiben", "anschreiben"]

_RUN_ID_RE = re.compile(r"^run-\d{14}(-[0-9a-f]{4,})?$")
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]{0,60}$")
_PDF_FILE_RE = re.compile(r"^[A-Za-z0-9._-]+\.pdf$")

#: Loopback guard config (see the security note at the top of this file).
CLIENT_HEADER = "x-attune-client"

_print_lock = threading.Lock()


def log(tag: str, message: str) -> None:
    with _print_lock:
        print(f"[{tag}] {message}", file=sys.stderr, flush=True)


def ensure_dirs() -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Scan classification - parity with the engine (same alias sets, same order)
# --------------------------------------------------------------------------- #

def fold_name(text: str) -> str:
    """JS ``foldName`` port: NFKD, strip combining marks, lower, [a-z0-9]."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", stripped.lower())


def classify_role(stem: str) -> str:
    s = fold_name(stem)
    if s in CV_ALIASES:
        return "cv"
    if s in COVER_ALIASES:
        return "cover"
    covers = sorted(COVER_ALIASES, key=len, reverse=True)
    cvs = sorted(CV_ALIASES, key=len, reverse=True)
    if any(a in s for a in covers):
        return "cover"
    if any(a in s for a in cvs):
        return "cv"
    return "unclassified"


def resolve_folder(folder: str) -> Path:
    """Absolute paths pass through; relative resolve against PROJECT_ROOT."""
    return Path(os.path.normpath(os.path.join(str(PROJECT_ROOT), folder)))


def scan_folder(folder: str):
    root = resolve_folder(folder)
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        return {"error": "Folder is not readable. Please check the path."}
    candidates = []
    notes = []
    subs = sorted(e for e in entries if (root / e).is_dir() and not e.startswith("."))
    for sub in subs:
        sub_path = root / sub
        try:
            pdfs = sorted(
                f for f in os.listdir(sub_path) if f.lower().endswith(".pdf")
            )
        except OSError:
            notes.append({"folder": sub, "note": "sub-folder not readable"})
            continue
        if not pdfs:
            notes.append(f'"{sub}" contains no PDF files - candidate will be skipped')
            continue
        files = []
        roles = []
        for name in pdfs:
            role = classify_role(re.sub(r"\.pdf$", "", name, flags=re.IGNORECASE))
            if role == "unclassified" and len(pdfs) == 1 and not roles:
                role = "cv"
            if role == "unclassified":
                role = "cover" if "cv" in roles else "cv"
            roles.append(role)
            try:
                size_bytes = (sub_path / name).stat().st_size
            except OSError:
                size_bytes = 0
            files.append(
                {"name": name, "relPath": f"{sub}/{name}", "role": role, "sizeBytes": size_bytes}
            )
        if "cv" not in roles:
            notes.append(f'"{sub}": no file classified as CV - candidate will be flagged for review')
        candidates.append(
            {
                "folder": sub,
                "files": files,
                "hasCv": "cv" in roles,
                "hasCover": "cover" in roles,
            }
        )
    return {"folder": str(root), "candidates": candidates, "notes": notes}


# --------------------------------------------------------------------------- #
# Run-directory resolution (no traversal outside RUNS_DIR, no symlinks)
# --------------------------------------------------------------------------- #

def resolve_run_dir(run_id: str):
    if not run_id or not _RUN_ID_RE.match(run_id):
        return None
    runs_root = RUNS_DIR.resolve()
    resolved = Path(os.path.normpath(os.path.join(str(runs_root), run_id)))
    # sep-safe containment: also rejects sibling dirs like "runs-evil"
    if resolved != runs_root and not str(resolved).startswith(str(runs_root) + os.sep):
        return None
    try:
        root_real = runs_root.resolve(strict=True)
        real = resolved.resolve(strict=True)
        if real != root_real and not str(real).startswith(str(root_real) + os.sep):
            return None
        if not real.is_dir():
            return None
        return real
    except OSError:
        return None


def read_json(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


#: {run_id: {"mtime": float, "finishedAt": str|None, "summary": dict|None}}
_summary_cache: dict = {}
_summary_lock = threading.Lock()


def run_summary(run_id: str, results_path: Path):
    """Parse results.json into the list-endpoint summary, cached by mtime."""
    mtime = results_path.stat().st_mtime
    with _summary_lock:
        cached = _summary_cache.get(run_id)
        if cached and cached["mtime"] == mtime:
            return cached["finishedAt"], cached["summary"]
    try:
        results = read_json(results_path)
        stats = results.get("statistics", {})
        review_queue = results.get("review_queue", [])
        summary = {
            "candidates": stats.get("candidates_total", 0),
            "shortlisted": stats.get("shortlisted", 0),
            "topLabel": (results.get("ranking_labels") or [None])[0],
            "profileTitle": (results.get("profile") or {}).get("title", ""),
            "company": (results.get("profile") or {}).get("company", ""),
            "reviewItems": len(review_queue),
            "blocking": sum(1 for q in review_queue if q.get("blocking")),
        }
        finished_at = results.get("created_at")
    except (OSError, ValueError) as exc:
        log("attune:run", f"results summary unavailable for {run_id}: {exc}")
        summary, finished_at = None, None
    with _summary_lock:
        _summary_cache[run_id] = {"mtime": mtime, "finishedAt": finished_at, "summary": summary}
    return finished_at, summary


# --------------------------------------------------------------------------- #
# API handlers. Each returns (status, body) where body is JSON-serialisable.
# --------------------------------------------------------------------------- #

def api_index(query, body):
    return 200, {"message": "Hello, world!"}


def api_browse(query, body):
    raw = body.get("path")
    raw = raw.strip() if isinstance(raw, str) and raw.strip() else str(PROJECT_ROOT)
    target = Path(raw).resolve()
    if not target.is_dir():
        return 404, {"error": "Not a directory"}
    try:
        entries = os.listdir(target)
    except OSError as exc:
        log("attune:browse", f"failed: {exc}")
        return 500, {"error": "Browse failed"}
    dirs = sorted(
        (e for e in entries if (target / e).is_dir() and not e.startswith(".")),
        key=str.lower,
    )[:400]
    parent = target.parent
    return 200, {
        "path": str(target),
        "parent": None if parent == target else str(parent),
        "directories": [{"name": n, "path": str(target / n)} for n in dirs],
    }


def api_scan(query, body):
    folder = body.get("folder")
    if not isinstance(folder, str) or not folder.strip():
        return 400, {"error": "Missing folder path"}
    result = scan_folder(folder)
    if "error" in result:
        return 404, result
    return 200, result


def api_run_start(query, body):
    ensure_dirs()
    folder = body.get("folder")
    folder = resolve_folder(folder.strip()) if isinstance(folder, str) else None
    if not folder:
        return 400, {"error": "Missing folder"}
    profile = body.get("profile")
    if not isinstance(profile, dict):
        return 400, {"error": "Missing job profile"}
    if not folder.is_dir():
        return 404, {"error": "Main folder not readable"}

    # collision-proof run id: mkdir without exist_ok fails when the
    # second-resolution timestamp id is taken (double POST, scripted use)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    run_id = None
    run_dir = None
    for attempt in range(5):
        if run_id:
            break
        candidate = f"run-{ts}" if attempt == 0 else f"run-{ts}-{uuid.uuid4().hex[:4]}"
        try:
            run_dir = RUNS_DIR / candidate
            run_dir.mkdir()
            run_id = candidate
        except FileExistsError:
            continue
    if not run_id:
        return 500, {"error": "Could not allocate a run directory"}

    # honor the recruiter's file re-tagging: the UI sends overrides nested in
    # the profile; a top-level roleOverrides (API convenience) wins if present.
    role_overrides = body.get("roleOverrides") or profile.get("role_overrides") or {}
    engine_profile = dict(profile)
    engine_profile["pseudonymous"] = body.get("pseudonymous", True) is not False
    engine_profile["role_overrides"] = role_overrides
    profile_json = json.dumps(engine_profile, indent=2)
    if len(profile_json.encode("utf-8")) > 2_000_000:
        return 413, {"error": "Job profile too large"}
    (run_dir / "profile.json").write_text(profile_json, encoding="utf-8")
    (run_dir / "input.json").write_text(
        json.dumps(
            {"folder": str(folder), "startedAt": datetime.now(timezone.utc).isoformat()},
            indent=2,
        ),
        encoding="utf-8",
    )

    # Spawn the deterministic local engine; progress is polled via
    # progress.json. A spawn failure is written into progress.json so the
    # UI's status polling reports it instead of hanging in "starting".
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    try:
        subprocess.Popen(
            [sys.executable, str(ENGINE), "--folder", str(folder),
             "--profile", str(run_dir / "profile.json"),
             "--run-dir", str(run_dir), "--salt", run_id],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True, close_fds=True, env=env,
        )
    except OSError as exc:
        log("attune:run", f"engine spawn failed: {exc}")
        (run_dir / "progress.json").write_text(
            json.dumps(
                {"progress": {
                    "stage": "error", "pct": 100,
                    "message": f"Run failed: engine could not be started ({exc})",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
                indent=2,
            ),
            encoding="utf-8",
        )
    # runId only: absolute server paths are an internal detail
    return 200, {"runId": run_id}


def api_run_list(query, body):
    ensure_dirs()
    try:
        ids = sorted(
            (e for e in os.listdir(RUNS_DIR) if (RUNS_DIR / e).is_dir()),
            reverse=True,
        )
    except OSError as exc:
        log("attune:run", f"list failed: {exc}")
        return 500, {"error": "List failed"}
    runs = []
    for run_id in ids[:25]:
        run_dir = resolve_run_dir(run_id)
        if not run_dir:
            continue
        status, pct, finished_at, summary = "unknown", 0, None, None
        try:
            prog = read_json(run_dir / "progress.json")
            status = prog.get("progress", {}).get("stage", "unknown")
            pct = prog.get("progress", {}).get("pct", 0)
        except (OSError, ValueError):
            pass  # no progress yet: show a booting run, not a fake stage
        results_path = run_dir / "results.json"
        if results_path.is_file():
            finished_at, summary = run_summary(run_id, results_path)
            status, pct = "done", 100
        runs.append(
            {"runId": run_id, "status": status, "pct": pct,
             "finishedAt": finished_at, "summary": summary}
        )
    return 200, {"runs": runs}


def api_run_status(query, body):
    run_id = (query.get("run_id") or [""])[0]
    run_dir = resolve_run_dir(run_id)
    if not run_dir:
        return 404, {"error": "Unknown run"}
    try:
        prog = read_json(run_dir / "progress.json").get("progress", {})
    except (OSError, ValueError):
        # no progress yet: distinguish a booting engine from a dead one via
        # the age of input.json (written right before spawn)
        try:
            age = time.time() - (run_dir / "input.json").stat().st_mtime
        except OSError:
            age = 0
        if age > STALE_AFTER_S:
            return 200, {
                "runId": run_id, "stage": "error", "pct": 100,
                "message": "Engine did not report progress - the run failed or stalled before starting.",
            }
        return 200, {"runId": run_id, "stage": "starting", "pct": 1, "message": "Engine starting..."}
    payload = {"runId": run_id}
    payload.update({k: prog[k] for k in ("stage", "pct", "message") if k in prog})
    return 200, payload


def api_run_results(query, body):
    run_id = (query.get("run_id") or [""])[0]
    run_dir = resolve_run_dir(run_id)
    if not run_dir:
        return 404, {"error": "Unknown run"}
    try:
        results = read_json(run_dir / "results.json")
    except (OSError, ValueError) as exc:
        log("attune:results", f"not ready: {exc}")
        return 404, {"error": "Results not ready"}
    decisions = []
    try:
        raw = (run_dir / "review_decisions.jsonl").read_text(encoding="utf-8")
        decisions = [json.loads(line) for line in raw.split("\n") if line]
    except (OSError, ValueError):
        pass
    exports = []
    try:
        exports = read_json(run_dir / "exports" / "manifest.json").get("files", [])
    except (OSError, ValueError):
        pass
    return 200, {"results": results, "decisions": decisions, "exports": exports}


def api_report_generate(query, body):
    run_id = body.get("run_id")
    run_dir = resolve_run_dir(run_id if isinstance(run_id, str) else "")
    if not run_dir:
        return 404, {"error": "Unknown run"}
    if not (run_dir / "results.json").is_file():
        return 500, {"error": "Report export failed"}
    pseudonymous = "0" if body.get("pseudonymous") is False else "1"
    try:
        proc = subprocess.Popen(
            [sys.executable, str(REPORTER), "--run-dir", str(run_dir),
             "--pseudonymous", pseudonymous],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        # bound the wait: a hung reportlab render must not hang the request
        try:
            exit_code = proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return 504, {"error": "Report generation timed out"}
    except OSError as exc:
        log("attune:report", f"spawn failed: {exc}")
        return 500, {"error": "Report generation failed"}
    if exit_code != 0:
        return 500, {"error": "Report generation failed"}
    try:
        files = read_json(run_dir / "exports" / "manifest.json").get("files", [])
    except (OSError, ValueError):
        return 500, {"error": "Report export failed"}
    return 200, {"ok": True, "files": files}


#: (status, headers, bytes) responses for the streaming download endpoint.
def api_report_download(query, body):
    run_id = (query.get("run_id") or [""])[0]
    file = (query.get("file") or [""])[0]
    run_dir = resolve_run_dir(run_id)
    if not run_dir:
        return 404, {"error": "Unknown run"}, {}
    if not _PDF_FILE_RE.match(file):
        return 400, {"error": "Bad file name"}, {}
    try:
        manifest = read_json(run_dir / "exports" / "manifest.json")
    except (OSError, ValueError):
        manifest = {}
    # only files listed in the export manifest may be read (no arbitrary
    # file reads off the run directory)
    if not any(f.get("file") == file for f in manifest.get("files", [])):
        return 404, {"error": "File not in export manifest"}, {}
    try:
        blob = (run_dir / "exports" / file).read_bytes()
    except OSError:
        return 404, {"error": "File not in export manifest"}, {}
    label = "attune-batch-report" if file == "batch-report.pdf" else f"attune-{file[:-4]}"
    headers = {
        "Content-Type": "application/pdf",
        "Content-Disposition": f'attachment; filename="{run_id}-{label}.pdf"',
    }
    return 200, blob, headers


def api_audit_read(query, body):
    run_id = (query.get("run_id") or [""])[0]
    run_dir = resolve_run_dir(run_id)
    if not run_dir:
        return 404, {"error": "Unknown run"}
    try:
        raw = (run_dir / "review_decisions.jsonl").read_text(encoding="utf-8")
        decisions = [json.loads(line) for line in raw.split("\n") if line]
    except FileNotFoundError:
        return 200, {"decisions": []}  # no decisions recorded yet
    except (OSError, ValueError) as exc:
        log("attune:audit", f"decisions unreadable: {exc}")
        return 200, {"decisions": []}
    return 200, {"decisions": decisions}


def _cap(value, max_len):
    if isinstance(value, str) and value.strip():
        return value.strip()[:max_len]
    return None


def api_audit_write(query, body):
    run_id = body.get("run_id")
    run_dir = resolve_run_dir(run_id if isinstance(run_id, str) else "")
    if not run_dir:
        return 404, {"error": "Unknown run"}
    # every free-text field is capped: the JSONL is immutable, so oversized or
    # abusive payloads must not bloat the audit trail
    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "action": "signoff" if body.get("action") == "signoff" else "resolve",
        "candidate_ref": _cap(body.get("candidate_ref"), 64),
        "kind": _cap(body.get("kind"), 64),
        "decision": _cap(body.get("decision"), 32),
        "reviewer": _cap(body.get("reviewer"), 80) or "anonymous",
        "note": body.get("note")[:500] if isinstance(body.get("note"), str) else "",
    }
    try:
        with open(run_dir / "review_decisions.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError as exc:
        log("attune:audit", f"append failed: {exc}")
        return 500, {"error": "Could not record the decision"}
    return 200, {"ok": True, "entry": entry}


def api_template(query, body):
    ensure_dirs()
    name = (query.get("name") or [None])[0]
    if name is not None:
        if not _SAFE_NAME_RE.match(name):
            return 400, {"error": "Invalid template name"}
        try:
            profile = read_json(TEMPLATES_DIR / f"{name}.json")
        except (OSError, ValueError):
            return 404, {"error": "Template not found"}
        return 200, {"name": name, "profile": profile}
    templates = []
    try:
        files = sorted(f for f in os.listdir(TEMPLATES_DIR) if f.endswith(".json"))
    except OSError:
        files = []
    for f in files:
        try:
            profile = read_json(TEMPLATES_DIR / f)
            templates.append({
                "name": f[:-5],
                "title": profile.get("profile_name") or (profile.get("job") or {}).get("title") or f,
            })
        except (OSError, ValueError):
            continue
    return 200, {"templates": templates}


def api_template_write(query, body):
    ensure_dirs()
    action = body.get("action")
    name = body.get("name")
    name = name if isinstance(name, str) else ""
    if not _SAFE_NAME_RE.match(name or ""):
        return 400, {"error": "Invalid template name (letters, numbers, spaces, - and _ only)"}
    file = TEMPLATES_DIR / f"{name}.json"
    if action == "save":
        profile = body.get("profile")
        if not isinstance(profile, dict):
            return 400, {"error": "Missing profile"}
        profile_json = json.dumps(profile, indent=2)
        if len(profile_json.encode("utf-8")) > 2_000_000:
            return 413, {"error": "Profile too large"}
        file.write_text(profile_json, encoding="utf-8")
        return 200, {"ok": True, "name": name}
    if action == "delete":
        try:
            file.unlink()
        except FileNotFoundError:
            return 200, {"ok": True}  # already gone - delete is idempotent
        except OSError as exc:
            log("attune:template", f"delete failed: {exc}")
            return 500, {"error": "Delete failed"}
        return 200, {"ok": True}
    return 400, {"error": "Unknown action"}


#: (method, path) -> handler; the download endpoint returns a triple.
ROUTES = {
    ("GET", "/api"): api_index,
    ("POST", "/api/browse"): api_browse,
    ("POST", "/api/scan"): api_scan,
    ("POST", "/api/run"): api_run_start,
    ("GET", "/api/run"): api_run_list,
    ("GET", "/api/run/status"): api_run_status,
    ("GET", "/api/run/results"): api_run_results,
    ("POST", "/api/report"): api_report_generate,
    ("GET", "/api/report"): api_report_download,
    ("GET", "/api/audit"): api_audit_read,
    ("POST", "/api/audit"): api_audit_write,
    ("GET", "/api/template"): api_template,
    ("POST", "/api/template"): api_template_write,
}

MAX_BODY_BYTES = 10 * 1024 * 1024  # hard cap: JSON bodies are <= 2 MB by contract


class AttuneHandler(BaseHTTPRequestHandler):
    server_version = "JobAttune"
    protocol_version = "HTTP/1.1"

    # ---- plumbing -------------------------------------------------------- #

    def log_message(self, fmt, *args):  # route access logs through log()
        log("http", f"{self.address_string()} {fmt % args}")

    def _send(self, status, payload, content_type="application/json; charset=utf-8", extra_headers=None):
        blob = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(blob)))
        for key, value in (extra_headers or {}).items():
            if key.lower() not in ("content-type", "content-length"):
                self.send_header(key, value)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(blob)

    def _json_error(self, message, status=400):
        self._send(status, {"error": message})

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            raise ValueError("body too large")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    # ---- loopback guard (port of src/middleware.ts) ---------------------- #

    def _guard_passes(self) -> bool:
        """Every /api request must carry X-Attune-Client; cross-site browser
        requests are rejected. Cross-site `no-cors` fetches cannot set custom
        headers, which kills the realistic drive-by CSRF vector; plain HTTP
        clients must send the header explicitly, e.g. -H "X-Attune-Client: cli".
        """
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            self._json_error("Forbidden: cross-site requests are not allowed", 403)
            return False
        if not (self.headers.get(CLIENT_HEADER) or "").strip():
            self._json_error("Forbidden: missing X-Attune-Client header", 403)
            return False
        return True

    # ---- routing --------------------------------------------------------- #

    def _dispatch(self, method):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path.startswith("/api"):
            if not self._guard_passes():
                return
            handler = ROUTES.get((method, path.rstrip("/") or path))
            if handler is None:
                return self._json_error("Not found", 404)
            try:
                body = self._read_body() if method == "POST" else {}
            except ValueError:
                return self._json_error("Request body too large", 413)
            try:
                if handler is api_report_download:
                    # streaming endpoint: (status, payload, extra headers)
                    status, payload, headers = handler(parse_qs(parsed.query), body)
                    if isinstance(payload, bytes):
                        return self._send(status, payload, headers.get(
                            "Content-Type", "application/json; charset=utf-8"), headers)
                    return self._send(status, payload)
                status, payload = handler(parse_qs(parsed.query), body)
            except Exception as exc:  # never leak a stack trace
                log("attune:api", f"{method} {path} failed: {exc!r}")
                return self._json_error("Request failed", 500)
            return self._send(status, payload)
        return self._serve_static(path)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_HEAD(self):
        self._dispatch("GET")

    # ---- static frontend -------------------------------------------------- #

    def _serve_static(self, path):
        if path in ("", "/"):
            path = "/index.html"
        # normalize + containment check: the resolved path must stay in web/
        target = (WEB_DIR / path.lstrip("/")).resolve()
        web_root = WEB_DIR.resolve()
        if target != web_root and not str(target).startswith(str(web_root) + os.sep):
            return self._json_error("Not found", 404)
        if not target.is_file():
            return self._json_error("Not found", 404)
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        try:
            blob = target.read_bytes()
        except OSError:
            return self._json_error("Not found", 404)
        self._send(200, blob, ctype)


def main():
    ensure_dirs()
    if not WEB_DIR.is_dir():
        log("attune", f"web/ directory not found under {PROJECT_ROOT} - run me from the repo root")
        sys.exit(1)
    server = ThreadingHTTPServer((HOST, PORT), AttuneHandler)
    server.daemon_threads = True
    log("attune", f"Job Attune listening on http://{HOST}:{PORT} (web: {WEB_DIR})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("attune", "shutting down")


if __name__ == "__main__":
    main()
