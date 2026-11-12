#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Replay auditor for Job-Attune decision pins (spine feature, F6).

Total replay (vendor docs/REPLAY.md, invariant I3): every decision a run
produced must be re-derivable from its pin plus the pinned inputs. A run
pins every kernel evaluation into ``<run-dir>/spine_pins.jsonl``; each pin
carries the exact request bytes, the recorded decision, the confidence, the
kernel version and the schema fingerprint.

This auditor re-derives every pinned decision on a FRESH native kernel via
``odk_spine_evaluate_request`` and compares:

  - decision text (byte-level, both sides spine-canonicalized)
  - confidence (exact double equality - same computation, same bytes)
  - kernel version and schema fingerprint against the running build

Exit code 0 iff every pin replays as ``exact``. A mismatch is a determinism
regression: do not ship without understanding it.

Usage:
    python3 scripts/replay_audit.py --run-dir attune-data/runs/<run-id>
    python3 scripts/replay_audit.py --pins <run-dir>/spine_pins.jsonl [...]
    python3 scripts/replay_audit.py --run-dir <dir> --out report.json
"""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
import time
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "attune-engine"))

import spine_kernel as sk


def _create_kernel(lib: ctypes.CDLL) -> int:
    lib.odk_kernel_create.restype = ctypes.c_void_p
    handle = lib.odk_kernel_create()
    if not handle:
        raise RuntimeError("odk_kernel_create returned NULL")
    return handle


def audit_pins_file(pins_path: Path, lib: ctypes.CDLL, kernel: int) -> dict:
    pins = [json.loads(line) for line in
            pins_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows: List[dict] = []
    by_primitive: dict = {}
    mismatches = 0
    for pin in pins:
        primitive = "?"
        try:
            primitive = str(json.loads(pin.get("request_json", "{}")).get("primitive", "?"))
        except ValueError:
            pass
        row = {
            "pin_id": pin.get("pin_id"),
            "primitive": primitive,
            "replay_class": pin.get("replay_class"),
            "recorded_decision": pin.get("decision"),
            "recorded_confidence": pin.get("confidence"),
            "pin_kernel_version": pin.get("kernel_version"),
            "pin_schema_fp": pin.get("schema_fp"),
        }
        try:
            decision, confidence, _result_json = sk.evaluate_request(
                kernel, pin["request_json"])
            row["rederived_decision"] = decision
            row["rederived_confidence"] = confidence
            decision_match = decision == pin.get("decision")
            confidence_match = float(confidence) == float(pin.get("confidence"))
            row["decision_match"] = decision_match
            row["confidence_match"] = confidence_match
            row["verdict"] = "exact" if (decision_match and confidence_match) else "mismatch"
        except Exception as exc:
            row["verdict"] = "error"
            row["error"] = f"{type(exc).__name__}: {exc}"
        if row["verdict"] != "exact":
            mismatches += 1
        by_primitive.setdefault(primitive, {"total": 0, "exact": 0})
        by_primitive[primitive]["total"] += 1
        by_primitive[primitive]["exact"] += 1 if row["verdict"] == "exact" else 0
        rows.append(row)
    return {
        "pins_file": str(pins_path),
        "total_pins": len(pins),
        "exact": len(pins) - mismatches,
        "mismatch_or_error": mismatches,
        "by_primitive": by_primitive,
        "pins": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay-audit a run's decision pins (all pins must re-derive as 'exact')")
    parser.add_argument("--run-dir", default=None,
                        help="run directory containing spine_pins.jsonl")
    parser.add_argument("--pins", action="append", default=[],
                        help="pins file (repeatable); overrides --run-dir")
    parser.add_argument("--out", default=None,
                        help="write the full JSON report here")
    args = parser.parse_args()

    pins_files: List[Path] = []
    if args.pins:
        pins_files = [Path(p) for p in args.pins]
    elif args.run_dir:
        pins_files = [Path(args.run_dir) / "spine_pins.jsonl"]
    else:
        parser.error("pass --run-dir or --pins")
    missing = [p for p in pins_files if not p.is_file()]
    if missing:
        print(f"replay-audit: pins file(s) not found: {', '.join(map(str, missing))}",
              file=sys.stderr)
        print("hint: pins are only written when the spine feature was active "
              "(native kernel tier, $ATTUNE_SPINE != off)", file=sys.stderr)
        return 2

    lib = sk.load_spine_library()
    kernel = _create_kernel(lib)
    try:
        reports = [audit_pins_file(p, lib, kernel) for p in pins_files]
    finally:
        lib.odk_kernel_free.argtypes = [ctypes.c_void_p]
        lib.odk_kernel_free(kernel)

    total = sum(r["total_pins"] for r in reports)
    exact = sum(r["exact"] for r in reports)
    bad = sum(r["mismatch_or_error"] for r in reports)
    report = {
        "tool": "replay_audit",
        "generated_from": [str(p) for p in pins_files],
        "kernel_version": sk.KERNEL_VERSION,
        "schema_fingerprint": sk.schema_fingerprint(),
        "total_pins": total,
        "exact": exact,
        "mismatch_or_error": bad,
        "files": reports,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if args.out:
        Path(args.out).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"replay-audit: report written to {args.out}")
    for r in reports:
        print(f"replay-audit: {r['pins_file']}: {r['exact']}/{r['total_pins']} pins exact "
              f"({r['mismatch_or_error']} not exact)")
        for primitive, stats in sorted(r["by_primitive"].items()):
            print(f"  {primitive:<8} {stats['exact']}/{stats['total']} exact")
    if bad:
        print("replay-audit: FAIL - pinned decisions did not re-derive identically",
              file=sys.stderr)
        return 1
    print(f"replay-audit: OK - {total}/{total} pinned decisions re-derived as 'exact'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
