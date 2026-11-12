#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Emit the university case-study verification log (verification/).

Re-derives every claim from the on-disk runs + corpus:
  1. corpus inventory vs ground truth
  2. F1 content classification table vs ground truth
  3. tag-conflict review items
  4. two-run determinism (same salt; identity fields excluded)
  5. replay audit of all decision pins
  6. cross-tier (native vs WASM) ranking identity + spine degradation
  7. calibration report from HR sign-offs
Writes verification/case_study_university.txt and prints a summary.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CS = ROOT / "attune-data" / "casestudy-uni"
RUNS = ROOT / "attune-data" / "runs"
RUN = RUNS / "casestudy-uni-native"
RUN_DET = RUNS / "casestudy-uni-native-determinism"
RUN_WASM = RUNS / "casestudy-uni-wasm"
IDENTITY_FIELDS = {"run_id", "created_at", "audit", "spine"}

L: list[str] = []
def say(s: str = "") -> None:
    L.append(s)
    print(s)


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> int:
    gt = load(CS / "ground_truth.json")
    res = load(RUN / "results.json")
    gt_by = {c["folder"]: c for c in gt["candidates"]}
    ref2folder = {c["candidate_ref"]: c["folder_name"] for c in res["candidates"]}
    folders = {c["folder_name"] for c in res["candidates"]}

    say("Job-Attune university case study - verification evidence")
    say("engine " + res["engine_version"] + " | kernel " + res["omnidecide_version"]
        + " | position: " + res["profile"]["title"])
    say("grounding: " + gt["profile_grounding"])
    say()
    say("[1] corpus inventory")
    say(f"    candidates: {len(folders)}  documents: {sum(len(c['files']) for c in gt['candidates'])}"
        f"  languages: {sorted({c['language'] for c in gt['candidates']})}")
    challenges = [c["challenge"] for c in gt["candidates"] if c["challenge"] != "baseline"]
    say(f"    planted challenges: {len(challenges)}")
    for ch in challenges:
        say("      - " + ch)
    say()

    say("[2] spine F1 content classification vs ground truth")
    spine = res["spine"]
    say(f"    spine block: status={spine['status']} policy={spine['policy']} "
        f"backend={spine['backend']} classify_calls={spine['classify_calls']} "
        f"tag_conflicts={spine['tag_conflicts']} pins={spine['pins']} pin_errors={spine['pin_errors']}")
    ok = total = 0
    misses = []
    for c in sorted(res["candidates"], key=lambda c: c["folder_name"]):
        truth_files = {f["name"]: f["true_role"] for f in gt_by[c["folder_name"]]["files"]}
        for f in c["files"]:
            truth = truth_files[f["name"]]
            ct = f.get("content_tag", {})
            label = ct.get("label", "?")
            if truth == "mixed":
                say(f"      MIXED {c['folder_name']}/{f['name']}: content -> {label} "
                    f"(conf {ct.get('confidence')}) - role agrees: {ct.get('agrees')}")
                continue
            total += 1
            if label == truth:
                ok += 1
            else:
                misses.append(f"{c['folder_name']}/{f['name']}: content={label} truth={truth}")
    say(f"    classification accuracy (non-mixed documents): {ok}/{total}"
        + ("  - ALL CORRECT" if not misses else "  MISSES: " + "; ".join(misses)))
    say()

    say("[3] tag_conflict review items (confident filename/content disagreements)")
    tcs = [i for i in res["review_queue"] if i["kind"] == "tag_conflict"]
    for t in tcs:
        say(f"    {ref2folder[t['candidate_ref']]:<15} conf={t['confidence']:.2f} "
            f"(floor {t['floor']}): {t['detail']}")
    flagged = {ref2folder[t["candidate_ref"]] for t in tcs}
    planted = {c["folder"] for c in gt["candidates"] if "MISTAG" in c["challenge"] or "inverted" in c["challenge"]}
    say(f"    planted mistag packets flagged: {sorted(planted & flagged)}")
    say(f"    scan_notes (independent filename-routing flag): "
        f"{[n['folder'] for n in res['scan_notes']]}")
    say()

    say("[4] determinism across runs (same salt; identity fields excluded: "
        + ", ".join(sorted(IDENTITY_FIELDS)) + ")")
    def norm(p: Path):
        d = load(p)
        for k in IDENTITY_FIELDS:
            d.pop(k, None)
        return json.dumps(d, sort_keys=True, ensure_ascii=False)
    ha = hashlib.sha256(norm(RUN / "results.json").encode()).hexdigest()
    hb = hashlib.sha256(norm(RUN_DET / "results.json").encode()).hexdigest()
    say(f"    normalized run1 sha256: {ha[:40]}")
    say(f"    normalized run2 sha256: {hb[:40]}")
    say(f"    DETERMINISM: {'PASS - identical after excluding run-identity fields' if ha == hb else 'FAIL'}")
    say(f"    engine two-pass gate: pass1==pass2: "
        f"{res['determinism']['pass1_sha256'] == res['determinism']['pass2_sha256']}")
    say()

    say("[5] decision pins + replay audit")
    pins_a = [json.loads(line) for line in (RUN / "spine_pins.jsonl").read_text().splitlines() if line.strip()]
    pins_b = [json.loads(line) for line in (RUN_DET / "spine_pins.jsonl").read_text().splitlines() if line.strip()]
    diff_fields = set()
    for pa, pb in zip(pins_a, pins_b):
        for k in pa:
            if pa.get(k) != pb.get(k):
                diff_fields.add(k)
    say(f"    pins: {len(pins_a)} (run2: {len(pins_b)}); fields differing across runs: "
        f"{sorted(diff_fields) or 'none'}")
    audit = subprocess.run([sys.executable, str(ROOT / "scripts" / "replay_audit.py"),
                            "--run-dir", str(RUN)], capture_output=True, text=True)
    say("    replay_audit.py:")
    for line in audit.stdout.strip().splitlines():
        say("      " + line)
    say()

    say("[6] cross-tier check (native vs WASM, same salt)")
    wres = load(RUN_WASM / "results.json")
    say(f"    ranking identical: {res['ranking'] == wres['ranking']}")
    say(f"    overalls identical: "
        f"{[c['overall'] for c in res['candidates']] == [c['overall'] for c in wres['candidates']]}")
    say(f"    wasm spine block: status={wres['spine']['status']} "
        f"reason={wres['spine'].get('reason', '')[:80]}")
    say()

    say("[7] calibration loop (F4) from HR sign-offs")
    cal = load(RUN / "calibration-report.json")
    say(f"    sign-offs reviewed: review_decisions.jsonl = "
        f"{len((RUN / 'review_decisions.jsonl').read_text().splitlines())} entries")
    rep = cal.get("report", cal)
    say("    " + json.dumps(rep, sort_keys=True)[:400])
    say()
    say("evidence log ends")
    out = ROOT / "verification" / "case_study_university.txt"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"\nwritten -> {out.relative_to(ROOT)}")
    return 0 if ha == hb else 1


if __name__ == "__main__":
    raise SystemExit(main())
