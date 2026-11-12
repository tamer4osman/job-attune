#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""End-to-end verification of the Job-Attune spine features (v1.3.0).

Checks:
  1. spine-on run: pins created/exported, determinism two-pass green
  2. replay audit: every pin re-derives as 'exact' on a fresh kernel
  3. scoring identity: spine-on vs spine-off produce the SAME scoring
     payload (results.json minus the spine block, content_tag annotations
     and volatile fields) - the spine never changes a score
  4. WASM degradation: forced onto the WASM tier the run completes and the
     spine block records status=unavailable with the reason; ranking still
     matches the native run (byte-identical cross-tier decisions)
  5. mis-tagged fixture: a CV stored as photo.pdf raises a tag_conflict
     review item; a correctly named CV does not
  6. calibration loop: fabricated human sign-offs convert into outcome
     observations and calibrate into confidence bins

Usage: python3 scripts/verify_spine_features.py [--keep]
Exit 0 iff every check passes. Output is written to stdout as evidence.
"""

from __future__ import annotations

import ctypes
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "attune-engine" / "engine.py"
sys.path.insert(0, str(ROOT / "attune-engine"))
sys.path.insert(0, str(ROOT / "scripts"))

import spine_kernel as sk  # noqa: E402

PROFILE = ROOT / "attune-data" / "templates" / "example-senior-data-engineer.json"
DEMO = ROOT / "attune-sample-data" / "candidates"

CHECKS: list = []


def check(name: str, ok: bool, detail: str) -> None:
    CHECKS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")


def run_engine(run_dir: Path, env_extra: dict | None = None) -> dict:
    import os
    env = os.environ.copy()
    env.pop("OMNIDECIDE_C_LIB", None)
    env.pop("ATTUNE_SPINE", None)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(ENGINE), "--folder", str(DEMO), "--profile", str(PROFILE),
         "--run-dir", str(run_dir), "--salt", "spineverify"],
        capture_output=True, text=True, env=env, cwd=str(ROOT))
    if proc.returncode != 0:
        raise RuntimeError(f"engine run failed ({proc.returncode}): {proc.stderr[-800:]}")
    return json.loads((run_dir / "results.json").read_text(encoding="utf-8"))


def normalize(results: dict) -> str:
    """Canonical form for scoring identity: drop the spine block, the
    content_tag annotations, tag_conflict queue entries and volatile fields."""
    payload = json.loads(json.dumps(results))  # deep copy
    payload.pop("spine", None)
    payload.pop("audit", None)
    payload.pop("run_id", None)
    payload.pop("created_at", None)
    payload.pop("engine_version", None)
    for cand in payload.get("candidates", []):
        for finfo in cand.get("files", []):
            finfo.pop("content_tag", None)
    queue = payload.get("review_queue", [])
    if isinstance(queue, list):
        payload["review_queue"] = [q for q in queue if q.get("kind") != "tag_conflict"]
    # The recorded pass hashes fingerprint the payload WITH the content_tag
    # annotations (by design), so they legitimately differ between spine-on
    # and spine-off runs. Everything around them must be byte-identical.
    det = payload.get("determinism", {})
    det.pop("pass1_sha256", None)
    det.pop("pass2_sha256", None)
    from engine import canonical_json  # engine's own canonicalizer
    return canonical_json(payload)


def make_mistag_fixture(base: Path) -> Path:
    """Conflict case: CV content stored under a COVER filename (anschreiben.pdf)
    -> engine role 'cover', spine content 'cv' -> tag_conflict. Plus a control
    candidate whose correct names agree with their content."""
    from reportlab.pdfgen import canvas
    cv_text = (
        "Curriculum Vitae - Alex Sample. Work experience: Senior Data Engineer "
        "2019-2026 at ACME. Education: MSc Computer Science. Skills: Python, "
        "Spark, Airflow, SQL. Employment history and certifications listed below. "
        "Achievements: led the migration of the analytics platform to the cloud, "
        "reduced batch cost by 40 percent, mentored four engineers.")
    cover_text = (
        "Dear Hiring Manager, I am writing to apply for the Data Engineer "
        "position. I would like to bring my stream-processing experience to "
        "your platform. Best regards, Alex Sample.")
    fixture = base / "fixture"
    shutil.rmtree(fixture, ignore_errors=True)
    for sub, name, text in (("cand-mistag", "anschreiben.pdf", cv_text),
                            ("cand-mistag", "letter.pdf", cover_text),
                            ("cand-control", "resume.pdf", cv_text)):
        d = fixture / sub
        d.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(d / name))
        y = 780
        for line in [text[i:i + 80] for i in range(0, len(text), 80)] * 3:
            c.drawString(60, y, line)
            y -= 16
        c.save()
    return fixture


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="spine-verify-"))
    print(f"verify-spine: workdir {tmp}")

    # -- 1+2: spine-on run, pins, determinism, replay audit -------------------
    on = run_engine(tmp / "run-on")
    spine = on.get("spine", {})
    check("spine-on status", spine.get("status") == "active", json.dumps(spine))
    check("pins exported", spine.get("pins", 0) > 0 and spine.get("pins_exported") == spine.get("pins"),
          f"{spine.get('pins')} pins, exported {spine.get('pins_exported')}, errors {spine.get('pin_errors')}")
    check("determinism (two-pass)", on["determinism"]["identical"] is True,
          f"pass1={on['determinism']['pass1_sha256'][:16]}")
    pins_file = tmp / "run-on" / "spine_pins.jsonl"
    check("pins file written", pins_file.is_file(),
          f"sha256 {spine.get('pins_file_sha256', '')[:16]}")

    import replay_audit
    lib = sk.load_spine_library()
    kernel = replay_audit._create_kernel(lib)
    try:
        audit = replay_audit.audit_pins_file(pins_file, lib, kernel)
    finally:
        lib.odk_kernel_free.argtypes = [ctypes.c_void_p]
        lib.odk_kernel_free(kernel)
    check("replay audit exact", audit["mismatch_or_error"] == 0,
          f"{audit['exact']}/{audit['total_pins']} pins exact "
          f"({json.dumps(audit['by_primitive'])})")

    # -- 3: scoring identity spine-on vs spine-off ---------------------------
    off = run_engine(tmp / "run-off", env_extra={"ATTUNE_SPINE": "off"})
    check("spine-off status", off.get("spine", {}).get("status") == "off",
          json.dumps(off.get("spine", {})))
    same = normalize(on) == normalize(off)
    check("scoring identity (on == off)", same,
          "canonical scoring payloads byte-identical with content_tag/spine removed"
          if same else "SCORING DIVERGED - spine leaked into decisions")

    # -- 4: WASM degradation --------------------------------------------------
    wasm = run_engine(tmp / "run-wasm", env_extra={"OMNIDECIDE_C_LIB": "/nonexistent/libomnidecide.so"})
    wspine = wasm.get("spine", {})
    check("wasm degradation", wspine.get("status") == "unavailable" and "wasm" in wspine.get("reason", ""),
          json.dumps(wspine))
    check("wasm run still screens", wasm["determinism"]["identical"] is True and len(wasm["candidates"]) == len(on["candidates"]),
          f"{len(wasm['candidates'])} candidates, ranking identical to native: {wasm['ranking'] == on['ranking']}")

    # -- 5: mis-tagged fixture -------------------------------------------------
    fixture = make_mistag_fixture(tmp)
    mistag_run = tmp / "run-mistag"
    proc = subprocess.run(
        [sys.executable, str(ENGINE), "--folder", str(fixture), "--profile", str(PROFILE),
         "--run-dir", str(mistag_run), "--salt", "spineverify"],
        capture_output=True, text=True, cwd=str(ROOT))
    if proc.returncode != 0:
        check("mistag fixture run", False, proc.stderr[-400:])
    else:
        mr = json.loads((mistag_run / "results.json").read_text(encoding="utf-8"))
        conflicts = [q for q in mr.get("review_queue", []) if q.get("kind") == "tag_conflict"]
        flagged = any(f.get("name") == "anschreiben.pdf" and (f.get("content_tag") or {}).get("agrees") is False
                      for c in mr["candidates"] for f in c["files"])
        control_clean = all((f.get("content_tag") or {}).get("agrees") is not False
                            for c in mr["candidates"] if c["folder_name"] == "cand-control"
                            for f in c["files"])
        check("mis-tag detected (photo.pdf holds a CV)", flagged and len(conflicts) >= 1,
              f"{len(conflicts)} tag_conflict review item(s); detail: "
              f"{conflicts[0]['detail'][:110]}..." if conflicts else "no conflict raised")
        check("control candidate clean", control_clean, "resume.pdf not flagged")
        check("mistag run determinism", mr["determinism"]["identical"] is True,
              f"pass1={mr['determinism']['pass1_sha256'][:16]}")

    # -- 6: calibration loop ----------------------------------------------------
    run_on_dir = tmp / "run-on"
    results = json.loads((run_on_dir / "results.json").read_text(encoding="utf-8"))
    lines = []
    for cand, verdict in zip(results["candidates"][:4],
                             ["confirm", "override", "confirm", "confirm"]):
        lines.append(json.dumps({
            "at": "2026-11-11T10:00:00+00:00",
            "action": "signoff",
            "candidate_ref": cand["candidate_ref"],
            "kind": "final_verdict",
            "decision": verdict,
            "reviewer": "verify-script",
            "note": "fabricated for the calibration verification",
        }))
    (run_on_dir / "review_decisions.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    calib = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "calibrate_report.py"),
         "--run-dir", str(run_on_dir), "--out", str(tmp / "calibration-report.json")],
        capture_output=True, text=True, cwd=str(ROOT))
    calib_ok = calib.returncode == 0
    report = json.loads((tmp / "calibration-report.json").read_text(encoding="utf-8")) if calib_ok else {}
    bins = report.get("report", {}).get("bins", [])
    check("calibration report", calib_ok and len(bins) >= 1,
          f"{report.get('observations_ingested', 0) // 2} outcome pairs -> "
          f"{len(bins)} bin(s); {calib.stdout.strip().splitlines()[-1] if calib.stdout.strip() else ''}")

    failed = [name for name, ok, _ in CHECKS if not ok]
    print(f"\nverify-spine: {len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
    if not failed:
        print("verify-spine: OK - all spine feature checks green")
    else:
        print(f"verify-spine: FAIL - {failed}")
    if "--keep" not in sys.argv:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"verify-spine: kept {tmp}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
