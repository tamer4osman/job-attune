#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Python-side check suite for Job Attune (static + functional + report validation).

Checks:
  A. Static: AST unused-import scan on the engine files; vendored floors
     contract present with pinned calibration data.
  B. Floors contract: floors_attune.json loads via the vendored module; all 6
     primitives present; values clamped to [0,1]; matches the calibration values.
  C. Functional: full engine run on the demo corpus in a temp run dir; determinism
     (two passes, identical sha256); descending ranking; all 6 primitives load-bearing;
     blocking noul escalation present; PII persistence probe; enrichment
     (profile_card, skills_inventory, interview_prompts, cohort, comparison block);
     review-readiness (verdict labels, score decomposition, tiers, review notes,
     market gaps, bench, unique strengths, next steps, talent pool, tenure);
     accuracy remediation regression probes (C27-C32: experience date-range
     math, decimal-years parsing, employment_overlap flag, aspiration/low-proficiency
     claim caps, German values folding, seniority current-role rule, compare-tie
     escalation, claim_quality audit field).
     tuned-evidence probes (C33-C35: loader validation, override application
     + confidence gating + heuristic-input persistence, run-level manifest counters).
     bench baselines probes (C36-C38: boolean-ats must-have veto + coverage,
     tf-idf ordering + determinism, bm25 ordering + determinism).
  D. Report: make_report.py exports; every PDF parses (pypdf), page count >= 1,
     manifest sha256 matches recomputed file hashes.

Exit code 0 = all green, 1 = at least one FAIL.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repo root (portable: no hardcoded absolute path)
ENGINE = ROOT / "attune-engine" / "engine.py"
REPORTER = ROOT / "attune-engine" / "make_report.py"
FLOORS = ROOT / "attune-engine" / "floors_attune.json"
FLOORS_MODULE = ROOT / "attune-engine" / "floors.py"
FLOORS_DATA = ROOT / "attune-engine" / "data" / "floors_v1.json"
SAMPLES = ROOT / "attune-sample-data" / "candidates"
TEMPLATE = ROOT / "attune-data" / "templates" / "example-senior-data-engineer.json"
TMP = ROOT / "scripts" / "tmp_pycheck"

results: list[tuple[str, str, str]] = []  # (grade, name, detail)


def grade(name: str, ok: bool, detail: str, warn_ok: bool = False) -> None:
    g = "GREEN" if ok else ("AMBER" if warn_ok else "RED")
    results.append((g, name, detail))
    print(f"[{g}] {name}: {detail}")


# --------------------------------------------------------------------------- #
# A. static
# --------------------------------------------------------------------------- #
def unused_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported[(a.asname or a.name).split(".")[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    imported[a.asname or a.name] = node.lineno
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            pass
    src = path.read_text(encoding="utf-8")
    return [f"{n}:{ln}" for n, ln in imported.items()
            if n not in used and n != "annotations" and src.count(n) <= 1]


sys.path.insert(0, str(ROOT / "attune-engine"))
import floors as floors_contract  # noqa: E402  (vendored floors contract)
from floors import floors_version, load_floors  # noqa: E402

_vdata = json.loads(FLOORS_DATA.read_text(encoding="utf-8")) if FLOORS_DATA.is_file() else {}
grade("A1 vendored floors contract + pinned calibration data",
      (FLOORS_MODULE.is_file() and FLOORS_DATA.is_file()
       and floors_contract.FLOOR_DATA_VERSION == "1.0"
       and _vdata.get("version") == "1.0"
       and _vdata.get("floors") == {"noul": 0.98, "choice": 0.73, "compare": 0.58,
                                     "rank": 0.12, "score": 0.8, "extract": 0.37}),
      f"module={FLOORS_MODULE.name} data={FLOORS_DATA.name} "
      f"schema={floors_contract.FLOOR_DATA_VERSION} floors={_vdata.get('floors')}")

for f in (ENGINE, REPORTER):
    ui = unused_imports(f)
    grade(f"A2 unused imports {f.name}", not ui, "none" if not ui else ", ".join(ui), warn_ok=True)

# --------------------------------------------------------------------------- #
# B. floors contract
# --------------------------------------------------------------------------- #
try:
    floors = load_floors(FLOORS)
    expected = {"noul": 0.98, "choice": 0.73, "compare": 0.58, "rank": 0.12, "score": 0.8, "extract": 0.37}
    ok_keys = all(k in floors and abs(floors[k] - v) < 1e-9 for k, v in expected.items())
    ok_range = all(0.0 <= v <= 1.0 for v in floors.values())
    ver = floors_version(FLOORS)
    grade("B1 floors load + values", ok_keys and ok_range,
          f"{floors} version={ver}")
    raw = json.loads(FLOORS.read_text())
    grade("B2 floors provenance pinned to calibration dataset",
          raw.get("provenance", {}).get("dataset_sha256", "").startswith("64d36ce6"),
          f"dataset_sha256={raw.get('provenance', {}).get('dataset_sha256', '')[:16]}... episodes={raw.get('provenance', {}).get('episodes')}")
except Exception as exc:  # noqa: BLE001
    grade("B1 floors load", False, f"{type(exc).__name__}: {exc}")

# --------------------------------------------------------------------------- #
# C. functional end-to-end run
# --------------------------------------------------------------------------- #
import shutil  # noqa: E402

if TMP.exists():
    shutil.rmtree(TMP)
TMP.mkdir(parents=True)
run_dir = TMP / "run-check"

tpl = json.loads(TEMPLATE.read_text())
profile = tpl.get("profile", tpl) if isinstance(tpl, dict) else {}
profile_path = TMP / "profile.json"
profile_path.write_text(json.dumps(profile), encoding="utf-8")

cmd = [sys.executable, str(ENGINE), "--folder", str(SAMPLES), "--profile", str(profile_path),
       "--run-dir", str(run_dir), "--salt", "run-check"]
proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=str(ROOT))
grade("C1 engine exits 0", proc.returncode == 0,
      f"rc={proc.returncode}" + (f" stderr tail: {proc.stderr[-300:]}" if proc.returncode else ""))

res_path = run_dir / "results.json"
if proc.returncode == 0 and res_path.exists():
    r = json.loads(res_path.read_text())
    cands = r["candidates"]

    det = r.get("determinism", {})
    grade("C2 determinism two-pass sha256 identical", det.get("identical") is True,
          f"pass1={det.get('pass1_sha256', '')[:12]}... pass2={det.get('pass2_sha256', '')[:12]}...")

    overs = [c["overall"] for c in cands]
    ranked = [next(c for c in cands if c["candidate_ref"] == ref)["overall"] for ref in r["ranking"]]
    grade("C3 ranking strictly non-increasing", all(ranked[i] >= ranked[i + 1] for i in range(len(ranked) - 1)),
          f"ranking={ranked}")

    # all six primitives load-bearing
    noul_fired = any(g.get("kernel") for c in cands for g in c["noul_gates"])
    extract_fired = any(c["requirements"] and all("extract_confidence" in q for q in c["requirements"]) for c in cands)
    score_fired = all("kernel_score_confidence" in cat for c in cands for cat in c["categories"])
    choice_fired = all("choice" in c and c["choice"].get("kernel") for c in cands)
    compare_fired = r["events"]["compare"] is not None and isinstance(r["events"]["compare"], list)
    rank_fired = r["events"]["rank"] is not None
    primitives = {"noul": noul_fired, "extract": extract_fired, "score": score_fired,
                  "choice": choice_fired, "compare": compare_fired, "rank": rank_fired}
    grade("C4 all 6 primitives load-bearing", all(primitives.values()), json.dumps(primitives))

    kinds = {q.get("kind") for q in r["review_queue"]}
    blocking = [q for q in r["review_queue"] if q.get("blocking")]
    grade("C5 blocking unreadable-CV escalation present", any(k == "unreadable_document" for k in kinds),
          f"review kinds={sorted(kinds)}; blocking={len(blocking)}")

    petr = next((c for c in cands if c["folder_name"] == "petr_novak"), None)
    grade("C6 image-only scan.pdf handled", petr is not None and petr["overall"] == 0.0
          and any(g["blocking"] for g in petr["noul_gates"]),
          f"petr overall={petr['overall'] if petr else 'missing'}")

    shortl = [c["folder_name"] for c in cands if c["shortlisted"]]
    top = r["ranking_labels"][0] if r["ranking_labels"] else "?"
    grade("C7 shortlist + top-rank sanity", top == "james_okafor" and len(shortl) >= 1,
          f"top={top} shortlisted={shortl}")

    leaked_texts = [c["folder_name"] for c in cands if "@" in (c.get("texts", {}).get("cv", "") or "") or "+49" in (c.get("texts", {}).get("cv", "") or "")]
    leaked_paths = [c["folder_name"] for c in cands if c.get("folder_path")]
    grade("C8 data-minimisation probe (no raw texts / local paths persisted)", not leaked_texts and not leaked_paths,
          f"raw texts persisted: {leaked_texts or 'none'}; folder_path persisted: {leaked_paths or 'none'}",
          warn_ok=True)

    mh = [c["folder_name"] for c in cands if c["must_have_missing"]]
    grade("C9 must-have gap detection", len(mh) >= 1, f"candidates with gaps: {mh}")

    manifest = r.get("audit", {}).get("manifest", {})
    grade("C10 manifest audit fields", all(k in manifest for k in
          ("engine_version", "omnidecide_version", "floors_data_version", "floors_table", "file_hashes", "profile_sha256")),
          f"engine={manifest.get('engine_version')} omni={manifest.get('omnidecide_version')} floors_v={manifest.get('floors_data_version')}")

    # Kernel identity: the manifest must pin the kernel the run actually used.
    # The only kernel is the omnidecide-c C11 kernel (bridge: ckernel.py);
    # the check reads the constant expectation from the engine itself.
    import importlib.util as _il0
    _spec0 = _il0.spec_from_file_location("sp_engine", ENGINE)
    _eng = _il0.module_from_spec(_spec0)
    sys.modules["sp_engine"] = _eng
    _spec0.loader.exec_module(_eng)
    grade("C11 kernel version pinned in run", manifest.get("omnidecide_version") == _eng.ACTIVE_KERNEL_ID,
          f"manifest omnidecide_version={manifest.get('omnidecide_version')} "
          f"(engine expects {_eng.ACTIVE_KERNEL_ID})")

    # ---- v1.1.0 enrichment checks ------------------------------------------
    james = next((c for c in cands if c["folder_name"] == "james_okafor"), None)
    card = (james or {}).get("profile_card") or {}
    card_ok = (
        (card.get("experience_years") is None or isinstance(card.get("experience_years"), (int, float)))
        and isinstance(card.get("education"), list)
        and isinstance(card.get("languages"), list) and len(card.get("languages") or []) >= 1
        and isinstance(card.get("achievements"), list)
        and isinstance(card.get("risk_flags"), list)
        and card.get("seniority_estimate") in ("lead/principal", "senior", "mid-level", "junior", "unknown")
    )
    grade("C12 profile_card enrichment (experience/seniority/languages)", card_ok,
          f"james: exp={card.get('experience_years')} seniority={card.get('seniority_estimate')} "
          f"langs={len(card.get('languages') or [])} edu={len(card.get('education') or [])} "
          f"achievements={len(card.get('achievements') or [])} risks={len(card.get('risk_flags') or [])}")

    inv = (james or {}).get("skills_inventory") or []
    inv_ok = len(inv) >= 3 and all({"skill", "mentions"} <= set(s) for s in inv)
    grade("C13 skills_inventory beyond requirements", inv_ok,
          f"james inventory={[(s['skill'], s['mentions']) for s in inv[:4]]}... total={len(inv)}")

    prompts = (james or {}).get("interview_prompts") or []
    grade("C14 interview prompts generated where evidence gaps exist", isinstance(prompts, list) and len(prompts) >= 1,
          f"james prompts={len(prompts)}: {prompts[:1]}")

    comp = r.get("comparison") or {}
    verdict = comp.get("verdict") or {}
    matrix = comp.get("skill_coverage_matrix") or []
    top_ref = r["ranking"][0] if r["ranking"] else None
    comp_ok = (
        bool(verdict.get("recommendation"))
        and verdict.get("top_pick_ref") == top_ref
        and bool(verdict.get("rationale"))
        and comp.get("candidates_order") == r["ranking"]
        and len(matrix) == len(cands[0]["requirements"])
        and all(set(row.get("scores") or {}) == {c["candidate_ref"] for c in cands} for row in matrix)
        and isinstance(comp.get("category_leaders"), list) and comp["category_leaders"]
    )
    grade("C15 comparison block (verdict + coverage matrix + leaders)", comp_ok,
          f"recommendation={verdict.get('recommendation')} matrix={len(matrix)}x{len(cands)} "
          f"leaders={len(comp.get('category_leaders') or [])} differentiators={len(comp.get('differentiators') or [])}")

    cohort_ok = all(
        isinstance(c.get("cohort"), dict)
        and 0.0 <= c["cohort"]["percentile_overall"] <= 100.0
        and isinstance(c["cohort"].get("category_rank"), dict)
        for c in cands
    )
    top_pct = next((c["cohort"]["percentile_overall"] for c in cands if c["candidate_ref"] == top_ref), None)
    bottom_pct = min(c["cohort"]["percentile_overall"] for c in cands)
    grade("C16 cohort percentiles in [0,100], top=100", cohort_ok and top_pct == 100.0,
          f"top percentile={top_pct} bottom percentile={bottom_pct}")

    # PII redaction must also hold inside the NEW enrichment fields
    import re as _re
    enrich_blob = json.dumps([[c.get("profile_card"), c.get("skills_inventory"), c.get("interview_prompts")]
                              for c in cands] + [r.get("comparison")], ensure_ascii=False)
    pii_leaked = bool(_re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", enrich_blob))
    grade("C17 enrichment fields PII-redacted", not pii_leaked,
          "no raw email patterns in profile_card / inventory / prompts / comparison")

    # ---- v1.2.0 review-readiness checks -------------------------------------
    verdicts_ok, decomp_ok, tier_ok, tenure_ok = True, True, True, True
    for c in cands:
        for rq in c["requirements"]:
            s = rq["evidence_score"]
            expected = "met" if s >= 0.6 else ("partial" if s >= 0.4 else "missing")
            if rq.get("verdict") != expected:
                verdicts_ok = False
        vs = c.get("verdict_summary") or {}
        if vs.get("met") != sum(1 for rq in c["requirements"] if rq.get("verdict") == "met") \
                or vs.get("missing") != sum(1 for rq in c["requirements"] if rq.get("verdict") == "missing") \
                or vs.get("must_have_total") != sum(1 for rq in c["requirements"] if rq["must_have"]):
            verdicts_ok = False
        dec = c.get("score_decomposition") or {}
        if dec.get("cap_applied") != bool(c["must_have_missing"]):
            decomp_ok = False
        if not dec.get("cap_applied") and abs(dec.get("sum_points", -1) - c["overall"]) > 0.15:
            decomp_ok = False
        expected_tier = "A" if c["shortlisted"] else ("B" if c["overall"] >= 45.0 else "C")
        if c.get("tier") != expected_tier or not c.get("review_note"):
            tier_ok = False
        tn = (c.get("profile_card") or {}).get("tenure")
        if tn is not None and not (tn["positions"] >= 1 and 0 < tn["avg_months"] <= tn["longest_months"]):
            tenure_ok = False
    grade("C18 requirement verdict labels + summary consistent", verdicts_ok,
          f"verdict thresholds met>=0.6 / partial>=0.4 / missing hold for all "
          f"{sum(len(c['requirements']) for c in cands)} requirement rows")
    james_vs = james["verdict_summary"]
    grade("C19 verdict summary counts (met/partial/missing/must-have)",
          james_vs["met"] + james_vs["partial"] + james_vs["missing"] == len(james["requirements"]),
          f"james: {james_vs['met']} met / {james_vs['partial']} partial / {james_vs['missing']} missing, "
          f"must-haves {james_vs['must_have_met']}/{james_vs['must_have_total']}, "
          f"completeness {james_vs['completeness_pct']:.1f}%")
    grade("C20 score decomposition reconciles with overall", decomp_ok,
          f"james sum={james['score_decomposition']['sum_points']} vs overall={james['overall']} "
          f"(cap_applied={james['score_decomposition']['cap_applied']})")
    grade("C21 tier mapping A/B/C + review notes present", tier_ok,
          f"tiers={r['statistics']['tiers']} notes on all {len(cands)} dossiers")
    grade("C22 tenure metrics consistent", tenure_ok,
          f"james tenure={james['profile_card'].get('tenure')}")

    gaps_ok = all(g["best_score"] < 0.6 and g["best_ref"] for g in comp.get("market_gaps") or [])
    bench_ok = all(b["strong"] + b["capable"] + b["thin"] == b["candidates"] for b in comp.get("bench") or [])
    uniq_ok = True
    for u in comp.get("unique_strengths") or []:
        for row in comp["skill_coverage_matrix"]:
            if row["skill"] in u["skills"]:
                strong_n = sum(1 for v in row["scores"].values() if v is not None and v >= 0.6)
                if strong_n != 1 or (row["scores"].get(u["ref"]) or 0) < 0.6:
                    uniq_ok = False
    grade("C23 market gaps + bench + unique strengths consistent",
          gaps_ok and bench_ok and uniq_ok,
          f"gaps={len(comp.get('market_gaps') or [])} bench rows={len(comp.get('bench') or [])} "
          f"unique-strength refs={len(comp.get('unique_strengths') or [])}")

    ns = verdict.get("next_steps")
    grade("C24 verdict next_steps present", isinstance(ns, list) and len(ns) >= 1,
          f"{len(ns or [])} steps: {(ns or [''])[0][:80]}...")

    tp = r["statistics"].get("talent_pool") or {}
    tiers_stats = r["statistics"].get("tiers") or {}
    tp_ok = (all(0 <= s["pct"] <= 100 and s["count"] <= len(cands) for s in tp.get("common_skills") or [])
             and sum(tiers_stats.values()) == len(cands)
             and isinstance(tp.get("education_distribution"), dict))
    grade("C25 talent pool + tier statistics valid", tp_ok,
          f"tiers={tiers_stats} common_skills={len(tp.get('common_skills') or [])} "
          f"median_exp={tp.get('median_experience_years')}")

    enrich_blob2 = json.dumps([[c.get("review_note"), c.get("score_decomposition"), c.get("evidence_quality"),
                                c.get("verdict_summary")] for c in cands]
                              + [r.get("statistics", {}).get("talent_pool")], ensure_ascii=False)
    pii_leaked2 = bool(_re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", enrich_blob2))
    grade("C26 v1.2.0 fields PII-redacted", not pii_leaked2,
          "no raw email patterns in review_note / decomposition / evidence_quality / talent_pool")

    # ---- v1.3.0 accuracy remediation regression probes (unit-level) ---------
    # The engine module was already loaded for C11; reuse it (_eng in scope).

    _spans = [{"start": 2020, "end": 2022, "span": "2020-2022", "months": 24},
              {"start": 2021, "end": 2023, "span": "2021-2023", "months": 24}]
    _y, _basis = _eng.estimate_experience("no explicit years here", _spans)
    _y65, _ = _eng.estimate_experience("Senior data engineer with 6.5 years of experience", [])
    _y15, _ = _eng.estimate_experience("Junior data engineer, 1.5 years of experience", [])
    grade("C27 D1+D2 experience math (ranges in years, decimals exact)",
          _y == 3.0 and _basis == "date_ranges" and _y65 == 6.5 and _y15 == 1.5,
          f"ranges={_y}y ({_basis}), 6.5y-> {_y65}, 1.5y-> {_y15}")

    _cand = {"noul_gates": []}
    _oflags = _eng.risk_flags_for(_cand, _spans, "", 500)
    _clean = [{"start": 2017, "end": 2019, "span": "2017-2019", "months": 24},
              {"start": 2019, "end": None, "span": "2019-present", "months": 84}]
    _cflags = _eng.risk_flags_for(_cand, _clean, "", 500)
    grade("C28 D3 employment_overlap flag (fires on overlap, silent on clean)",
          any(f["flag"] == "employment_overlap" for f in _oflags)
          and not any(f["flag"] == "employment_overlap" for f in _cflags),
          f"overlap case: {[f['flag'] for f in _oflags]}; clean case: {[f['flag'] for f in _cflags]}")

    _req = {"skill": "Python", "aliases": ["python3"]}
    _evA = _eng.evidence_for(_req, "I would be excited to learn Python on the job.", "")
    _sA = _eng.evidence_score(_evA, False)
    _evB = _eng.evidence_for(_req, "Wrote Python (basic scripts) for glue jobs.", "")
    _sB = _eng.evidence_score(_evB, False)
    _evC = _eng.evidence_for(_req, "Built Python ETL pipelines for charge-point telemetry.", "")
    grade("C29 D4 claim caps (aspirational<=0.30, basic<=0.35, direct uncapped)",
          _evA["claim_quality"] == "aspirational" and _sA <= 0.30
          and _evB["claim_quality"] == "qualified_low" and _sB <= 0.35
          and _evC["claim_quality"] == "direct",
          f"aspirational={_sA}, qualified_low={_sB}, direct q={_evC['claim_quality']}")

    _vals = "safety first; reliable engineering; open communication; sustainability; ownership and accountability"
    _fitDE, _ = _eng.values_fit_score(_vals, "", "Themen wie Sicherheit (safety first), verlassliches "
                                      "Engineering und Nachhaltigkeit entsprechen meiner Arbeitsweise. "
                                      "Ownership heisst fuer mich: klar kommunizieren.")
    _fitEN, _ = _eng.values_fit_score(_vals, "I believe in reliable engineering, open communication "
                                      "and sustainability. Safety first thinking, full ownership and "
                                      "accountability.", "")
    grade("C30 E1 values-fit German folding (EN baseline unchanged)",
          _fitDE is not None and _fitDE >= 0.6 and _fitEN == 1.0,
          f"German cover fit={_fitDE}, English baseline fit={_fitEN}")

    _cvA = ("X - Data Engineer\nPROFILE\nData engineer with 7 years of experience.\n"
            "EXPERIENCE\nFinCo - Data Engineer (2019-present)\n- Built pipelines.\n"
            "DataBridge - Junior ETL Developer (2017-2019)\n- SQL reports.\n")
    _cvB = "Y - Junior Data Engineer, 1.5 years of experience, eager to grow.\nEXPERIENCE\nShop - Junior Data Engineer (2025-present)\n"
    _senA, _ = _eng.estimate_seniority(_cvA, 7.0)
    _senB, _ = _eng.estimate_seniority(_cvB, 1.5)
    grade("C31 E2 seniority current-role rule (past junior skipped, current kept)",
          _senA != "junior" and _senB == "junior",
          f"past-title CV -> {_senA}; current-junior CV -> {_senB}")

    _quality_fields = all("claim_quality" in rq for c in cands for rq in c["requirements"])
    grade("C32 D4+D6 claim_quality persisted on all requirement rows + compare-tie branch shipped",
          _quality_fields and 'not in ("A", "B")' in ENGINE.read_text(),
          f"claim_quality on {sum(len(c['requirements']) for c in cands)} rows; "
          f"demos sample: {sorted({rq['claim_quality'] for c in cands for rq in c['requirements']})}")

    # ---- tuned-evidence probes -------------------------------------------
    _tmp_tuned = TMP / "tuned_gate"
    _tmp_tuned.mkdir(parents=True, exist_ok=True)
    _good = _tmp_tuned / "good.json"
    _good.write_text(json.dumps({
        "schema": "attune.tuned-evidence/1", "method": "gate", "created": "2026-10-03",
        "overrides": [
            {"candidate": "james_okafor", "skill": "SQL", "claim_quality": "qualified_low",
             "confidence": 0.9, "rationale": "gate probe"},
            {"candidate": "james_okafor", "skill": "Python", "claim_quality": "qualified_low",
             "confidence": 0.5, "rationale": "below conf floor - must be ignored"},
        ]}))
    _t = _eng.load_tuned_evidence(_good)
    grade("C33 tuned-evidence loader (schema + validation)",
          len(_t["overrides"]) == 2 and _t["metadata"].get("method") == "gate",
          f"rows={len(_t['overrides'])} meta_keys={sorted(_t['metadata'])}")
    _reqSQL = {"skill": "SQL", "aliases": ["postgresql"]}
    _evH = _eng.evidence_for(_reqSQL, "Wrote SQL reports and dashboards.", "")
    _evT = _eng.evidence_for(_reqSQL, "Wrote SQL reports and dashboards.", "",
                             quality_override="qualified_low")
    _sH, _sT = _eng.evidence_score(_evH, False), _eng.evidence_score(_evT, False)
    grade("C34 override application + confidence gate + caps",
          _evH["claim_quality"] == "direct" and _evT["claim_quality"] == "qualified_low"
          and _sT <= 0.35 and _sH > _sT
          and _eng.TUNE_MIN_CONFIDENCE == 0.60,
          f"heuristic={_sH} tuned={_sT} (conf floor {_eng.TUNE_MIN_CONFIDENCE})")
    _bad = _tmp_tuned / "bad.json"
    _bad.write_text(json.dumps({"schema": "nope/1", "overrides": []}))
    _raised = False
    try:
        _eng.load_tuned_evidence(_bad)
    except ValueError:
        _raised = True
    grade("C35 tuned-evidence fail-fast on bad schema", _raised,
          "ValueError raised for wrong schema")

    # ---- bench baselines probes ------------------------------------------
    import importlib.util as _ilu
    _bspec = _ilu.spec_from_file_location("bench_baselines", ROOT / "bench" / "baselines.py")
    _bmod = _ilu.module_from_spec(_bspec)
    _bspec.loader.exec_module(_bmod)
    _probe_prof = {"company": "ProbeCo", "job": "Senior Data Engineer",
                   "categories": {"technical_skills": [
                       {"skill": "Python", "weight": 3.0, "must_have": True, "aliases": []},
                       {"skill": "Apache Airflow", "weight": 2.0, "must_have": True, "aliases": ["Airflow"]},
                       {"skill": "Kubernetes", "weight": 1.0, "must_have": False, "aliases": ["k8s"]}]}}
    _texts = {"good": "Built Python pipelines with Apache Airflow and Kubernetes clusters.",
              "partial": "Python developer, no orchestrator experience.",
              "empty": "Sales representative, completely unrelated background."}
    _ba = _bmod.boolean_ats_scores(_probe_prof, _texts)
    _tf = _bmod.tfidf_scores(_probe_prof, _texts)
    _bm = _bmod.bm25_scores(_probe_prof, _texts)
    grade("C36 bench boolean-ats must-have veto + coverage",
          _ba["empty"] == 0.0 and _ba["partial"] == 0.0
          and _ba["good"] > 1.0 and abs(_ba["good"] - 3.0) < 1e-9,
          f"good={_ba['good']:.3f} partial={_ba['partial']} empty={_ba['empty']}")
    grade("C37 bench tfidf ordering + determinism",
          max(_tf, key=_tf.get) == "good" and _tf["good"] > _tf["partial"] > _tf["empty"]
          and _tf["empty"] == 0.0 and _bmod.tfidf_scores(_probe_prof, _texts) == _tf,
          f"good={_tf['good']:.3f} partial={_tf['partial']:.3f} empty={_tf['empty']:.3f}")
    grade("C38 bench bm25 ordering + determinism",
          max(_bm, key=_bm.get) == "good" and _bm["good"] > _bm["partial"] > _bm["empty"]
          and _bmod.bm25_scores(_probe_prof, _texts) == _bm,
          f"good={_bm['good']:.3f} partial={_bm['partial']:.3f} empty={_bm['empty']:.3f}")
else:
    grade("C1 results.json", False, "engine failed - functional checks skipped")

# --------------------------------------------------------------------------- #
# D. report generation + PDF validation
# --------------------------------------------------------------------------- #
if proc.returncode == 0 and res_path.exists():
    rcmd = [sys.executable, str(REPORTER), "--run-dir", str(run_dir), "--pseudonymous", "1"]
    rproc = subprocess.run(rcmd, capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    grade("D1 make_report exits 0", rproc.returncode == 0,
          f"rc={rproc.returncode} {rproc.stdout.strip()[-120:]}" + (f" err={rproc.stderr[-200:]}" if rproc.returncode else ""))
    exports = run_dir / "exports"
    manifest = json.loads((exports / "manifest.json").read_text())
    all_ok, details = True, []
    try:
        from pypdf import PdfReader
        for entry in manifest["files"]:
            p = exports / entry["file"]
            head = p.read_bytes()[:5]
            reader = PdfReader(str(p))
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            ok = head == b"%PDF-" and len(reader.pages) >= 1 and h == entry["sha256"]
            all_ok &= ok
            details.append(f"{entry['file']}({len(reader.pages)}p)")
    except Exception as exc:  # noqa: BLE001
        all_ok = False
        details.append(f"{type(exc).__name__}: {exc}")
    grade("D2 PDFs valid + manifest sha256 match", all_ok,
          f"{len(manifest['files'])} files: {', '.join(details[:4])}...")

# --------------------------------------------------------------------------- #
summary = {"GREEN": 0, "AMBER": 0, "RED": 0}
for g, _, _ in results:
    summary[g] += 1
print(f"\nSUMMARY: {summary['GREEN']} green / {summary['AMBER']} amber / {summary['RED']} red")
sys.exit(1 if summary["RED"] else 0)
