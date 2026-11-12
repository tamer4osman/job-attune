#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Calibration report for Job-Attune review outcomes (spine feature, F4).

Closes the feedback loop: every human sign-off in a run's
``review_decisions.jsonl`` becomes a pair of spine observations -

  - a ``decision`` observation recording the engine's predicted confidence
    for that candidate's shortlist choice (from results.json), and
  - an ``outcome`` observation recording whether the human agreed
    (``success``) or overrode (``failure``), pointing at the decision
    observation by id (the kernel's pairing convention).

``odk_spine_calibrate`` then compares predicted confidence against observed
agreement rate, binned into ten confidence buckets - the live, per-deployment
counterpart of the frozen floors calibration (floors v1.0). Two runs over the
same log produce byte-identical reports (the spine never reads the clock;
timestamps come from the review entries themselves).

Usage:
    python3 scripts/calibrate_report.py --run-dir attune-data/runs/<id> [...]
    python3 scripts/calibrate_report.py --runs-glob "attune-data/runs/*"
    python3 scripts/calibrate_report.py --run-dir <dir> --out report.json

The spine is native-tier only: this tool needs the native kernel library
(scripts/build-kernel.sh). Requires no network access, ingests only the
pseudonymous refs already present in the run directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "attune-engine"))

import spine_kernel as sk

#: Review decisions whose text agrees with the engine's verdict. Everything
#: else counts as an override ("failure" in calibration terms).
AGREE_WORDS = {
    "confirm", "confirmed", "agree", "agreed", "accept", "accepted",
    "approve", "approved", "shortlist", "shortlisted", "ok", "yes", "keep",
}


def _epoch_ms(iso: str) -> int:
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    except ValueError:
        return 0


def _obs_id(entry: dict, idx: int) -> str:
    digest = hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False)
                            .encode("utf-8")).hexdigest()[:12]
    return f"obs-{digest}-{idx}"


def _bare_kernel_version(omnidecide_version: str) -> str:
    """'omnidecide-c 2.0.0' -> '2.0.0' (pin/observation convention)."""
    parts = str(omnidecide_version or "").split()
    return parts[-1] if parts else sk.KERNEL_VERSION


def collect_observations(run_dir: Path, fingerprint: str) -> tuple:
    """Build (decision, outcome) observation pairs from one run directory."""
    results_path = run_dir / "results.json"
    decisions_path = run_dir / "review_decisions.jsonl"
    if not results_path.is_file() or not decisions_path.is_file():
        return [], {"run": str(run_dir), "skipped": "missing results.json or review_decisions.jsonl"}
    results = json.loads(results_path.read_text(encoding="utf-8"))
    by_ref = {c.get("candidate_ref"): c for c in results.get("candidates", [])}
    kernel_version = _bare_kernel_version(results.get("omnidecide_version", ""))
    entries: List[dict] = []
    for line in decisions_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except ValueError:
                pass

    observations: List[dict] = []
    used, skipped_no_choice, skipped_override_action = 0, 0, 0
    for idx, entry in enumerate(entries):
        if entry.get("action") != "signoff":
            # 'resolve' entries address a specific review flag, not the
            # candidate verdict; they carry no agreement signal.
            skipped_override_action += 1
            continue
        cand = by_ref.get(entry.get("candidate_ref"))
        choice = (cand or {}).get("choice") or {}
        if not cand or "confidence" not in choice:
            skipped_no_choice += 1
            continue
        decision_text = str(entry.get("decision", "")).strip().lower()
        outcome = "success" if decision_text in AGREE_WORDS else "failure"
        obs_id = _obs_id(entry, idx)
        t = _epoch_ms(entry.get("at", ""))
        decision_obs = {
            "observation_id": obs_id,
            "kind": "decision",
            "t": t,
            "scope": "",
            "subject_ref": entry.get("candidate_ref", ""),
            "primitive": "choice",
            "scheme_id": "",
            "payload_json": json.dumps(
                {"decision": choice.get("decision"), "overall": cand.get("overall")},
                sort_keys=True),
            "confidence": float(choice["confidence"]),
            "tier": "A",
            "brain_snapshot_id": "",
            "outcome": "",
            "kernel_version": kernel_version,
            "schema_fp": fingerprint,
            "registrations": [],
        }
        outcome_obs = {
            "observation_id": obs_id + "-o",
            "kind": "outcome",
            "t": t + 1,
            "scope": "",
            "subject_ref": obs_id,
            "primitive": "",
            "scheme_id": "",
            "payload_json": "{}",
            "confidence": 0.0,
            "tier": "",
            "brain_snapshot_id": "",
            "outcome": outcome,
            "kernel_version": kernel_version,
            "schema_fp": fingerprint,
            "registrations": [],
        }
        observations.extend([decision_obs, outcome_obs])
        used += 1
    info = {"run": str(run_dir), "signoffs_used": used,
            "skipped_resolve_actions": skipped_override_action,
            "skipped_no_choice": skipped_no_choice}
    return observations, info


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calibration report over review-queue sign-offs (spine F4)")
    parser.add_argument("--run-dir", action="append", default=[],
                        help="run directory (repeatable)")
    parser.add_argument("--runs-glob", default=None,
                        help="glob of run directories, e.g. \"attune-data/runs/*\"")
    parser.add_argument("--out", default=None,
                        help="output path (default: <last-run-dir>/calibration-report.json "
                             "or attune-data/calibration-report.json)")
    args = parser.parse_args()

    run_dirs = [Path(p) for p in args.run_dir]
    if args.runs_glob:
        from glob import glob as _glob
        run_dirs.extend(Path(p) for p in sorted(_glob(args.runs_glob)))
    run_dirs = [p for p in run_dirs if p.is_dir()]
    if not run_dirs:
        parser.error("no run directories found - pass --run-dir or --runs-glob")

    ctx = sk.SpineContext.open(register_schemes=False)
    try:
        fingerprint = ctx.fingerprint
        all_observations: List[dict] = []
        run_infos = []
        for run_dir in run_dirs:
            observations, info = collect_observations(run_dir, fingerprint)
            run_infos.append(info)
            all_observations.extend(observations)
        for obs in all_observations:
            ctx.ingest_observation(obs)

        generated_from = (f"job-attune review outcomes ({len(run_dirs)} run(s), "
                          f"{len(all_observations) // 2} signed-off candidates)")
        report = ctx.calibrate(generated_from)
    finally:
        ctx.close()

    payload = {
        "tool": "calibrate_report",
        "runs": run_infos,
        "observations_ingested": len(all_observations),
        "report": report,
    }
    out = Path(args.out) if args.out else (
        run_dirs[-1] / "calibration-report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"calibrate-report: {len(all_observations) // 2} outcome pair(s) from "
          f"{len(run_dirs)} run(s) -> {out}")
    bins = report.get("bins", [])
    if bins:
        print(f"{'primitive':<10} {'bin':<8} {'n':>4} {'predicted':>10} {'observed':>9} {'error':>7}")
        for b in bins:
            print(f"{b['primitive']:<10} "
                  f"{b['lo']:.1f}-{b['hi']:.1f}  "
                  f"{b['sample_count']:>4} "
                  f"{b['predicted_mean']:>10.3f} "
                  f"{b['observed_rate']:>9.3f} "
                  f"{b['calibration_error']:>7.3f}")
    else:
        print("calibrate-report: no outcome pairs matched a decision - nothing to bin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
