# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Job Attune bench runner - one benchmark cell.

A cell = (corpus, system). This script runs ALL FOUR systems on ONE corpus:
  1. attune-engine         (subprocess, two passes for determinism)
  2. boolean-ats               (in-process, two passes)
  3. tfidf                     (in-process, two passes)
  4. bm25                      (in-process, two passes)

Metrics against the frozen pre-registered human ranking (when provided):
  spearman          rank correlation (average-rank ties handling)
  mae               mean |system_rank - human_rank|
  top3_overlap      |system top3 ∩ human top3| / 3
  bottom3_overlap   |system bottom3 ∩ human bottom3| / 3

When no human ranking exists (demo corpus), baselines are scored against the
engine's own order (agreement diagnostic), and the engine cell reports null
metrics (self-reference).

Output: one JSON file per cell (path chosen with --out)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bench"))

import baselines  # noqa: E402

ENGINE = ROOT / "attune-engine" / "engine.py"


# --------------------------------------------------------------------------- #
# Ranking + metrics (stdlib only)
# --------------------------------------------------------------------------- #

def rank_scores(scores: dict) -> list:
    """[(id, rank)] - deterministic: descending score, ties by id."""
    order = sorted(scores, key=lambda f: (-scores[f], f))
    return [(f, i + 1) for i, f in enumerate(order)]


def _average_ranks(order_ids: list) -> dict:
    """ids are already a strict order (tie-broken) -> plain 1..n ranks."""
    return {f: i + 1 for i, f in enumerate(order_ids)}


def spearman(order_a: list, order_b: list) -> float:
    """Spearman rho between two strict orders (average-rank formula)."""
    common = [f for f in order_a if f in set(order_b)]
    if len(common) < 2:
        return None
    ra, rb = _average_ranks(order_a), _average_ranks(order_b)
    n = len(common)
    d2 = sum((ra[f] - rb[f]) ** 2 for f in common)
    return 1.0 - (6.0 * d2) / (n * (n * n - 1.0))


def mae(order_a: list, order_b: list) -> float:
    common = [f for f in order_a if f in set(order_b)]
    if not common:
        return None
    ra, rb = _average_ranks(order_a), _average_ranks(order_b)
    return sum(abs(ra[f] - rb[f]) for f in common) / len(common)


def k_overlap(order_a: list, order_b: list, k: int, bottom: bool = False) -> float:
    sa = set((order_a[-k:] if bottom else order_a[:k]))
    sb = set((order_b[-k:] if bottom else order_b[:k]))
    return len(sa & sb) / float(k)


def load_human_order(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):  # my_ranking.json: [{rank, folder, ...}]
        return [e["folder"] for e in sorted(data, key=lambda e: e["rank"])]
    ranking = data.get("ranking") or []
    return [e["folder"] if isinstance(e, dict) else str(e) for e in ranking]


# --------------------------------------------------------------------------- #
# Engine + baseline runners
# --------------------------------------------------------------------------- #

def run_engine(corpus: Path, profile: Path, tuned: Path | None, salt: str, tag: str) -> dict:
    run_dir = ROOT / "attune-data" / "runs" / f"bench-{tag}"
    cmd = [sys.executable, str(ENGINE), "--folder", str(corpus), "--profile", str(profile),
           "--run-dir", str(run_dir), "--salt", salt]
    if tuned:
        cmd += ["--tuned-evidence", str(tuned)]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=900)
    if proc.returncode != 0:
        raise RuntimeError(f"engine run failed rc={proc.returncode}: {proc.stderr[-400:]}")
    res = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    cands = res.get("candidates", [])
    return {
        "engine_version": res.get("engine_version"),
        "n": len(cands),
        "elapsed_s": round(time.time() - t0, 3),
        "order": [c["folder_name"] for c in sorted(cands, key=lambda c: c["rank"])],
        "ranks": {c["folder_name"]: c["rank"] for c in cands},
        "scores": {c["folder_name"]: c.get("overall") for c in cands},
        "projection": json.dumps(
            [{"id": c["folder_name"], "rank": c["rank"], "overall": c.get("overall"),
              "band": c.get("band"), "shortlisted": c.get("shortlisted"),
              "must_missing": c.get("must_have_missing")} for c in sorted(cands, key=lambda c: c["folder_name"])],
            sort_keys=True),
    }


def run_baseline(fn, profile: dict, texts: dict) -> dict:
    scores = fn(profile, texts)
    ranked = rank_scores(scores)
    return {
        "order": [f for f, _ in ranked],
        "scores": {f: round(scores[f], 6) for f in sorted(scores)},
        "projection": json.dumps([{"id": f, "score": round(scores[f], 6)} for f in sorted(scores)], sort_keys=True),
    }


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description="Job Attune bench: one corpus, four systems")
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--tuned", default=None)
    ap.add_argument("--human", default=None, help="frozen human ranking JSON (optional)")
    ap.add_argument("--name", required=True, help="cell/corpus name, e.g. bench-c20")
    ap.add_argument("--salt", default=None, help="engine pseudonymisation salt (default: bench-<name>)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if not args.salt:
        args.salt = f"bench-{args.name}"

    corpus, profile_path = Path(args.corpus), Path(args.profile)
    tuned = Path(args.tuned) if args.tuned else None
    profile = json.loads(profile_path.read_text(encoding="utf-8"))

    texts = baselines.load_corpus_texts(corpus)
    human_order = load_human_order(Path(args.human)) if args.human else None

    cell = {"name": args.name, "corpus": str(corpus), "profile": profile_path.name,
            "tuned": bool(tuned), "n_candidates": len(texts),
            "human_reference": args.human or None, "systems": {}}

    # engine (two passes, determinism by projection hash)
    for tag in ("p1", "p2"):
        r = run_engine(corpus, profile_path, tuned, args.salt, f"{args.name}-{tag}")
        cell["systems"].setdefault("engine", {})[tag] = r
    e = cell["systems"]["engine"]
    e["deterministic"] = sha(e["p1"]["projection"]) == sha(e["p2"]["projection"])
    e["projection_sha256"] = sha(e["p1"]["projection"])
    e["order"] = e["p1"]["order"]
    e["engine_version"] = e["p1"]["engine_version"]
    if human_order:
        e["metrics_vs"] = "human"
        e["metrics"] = {
            "spearman": round(spearman(e["order"], human_order), 4),
            "mae": round(mae(e["order"], human_order), 3),
            "top3_overlap": round(k_overlap(e["order"], human_order, 3), 3),
            "bottom3_overlap": round(k_overlap(e["order"], human_order, 3, bottom=True), 3),
        }
    else:
        e["metrics_vs"] = "self"
        e["metrics"] = None  # engine is the reference on corpora without a human ranking

    # baselines (two passes each)
    for system, fn in (("boolean-ats", baselines.boolean_ats_scores),
                       ("tfidf", baselines.tfidf_scores),
                       ("bm25", baselines.bm25_scores)):
        a = run_baseline(fn, profile, texts)
        b = run_baseline(fn, profile, texts)
        entry = {"order": a["order"], "scores": a["scores"],
                 "deterministic": a["projection"] == b["projection"],
                 "projection_sha256": sha(a["projection"])}

        ref_label = None
        if human_order:
            ref_label = "human"
        else:
            ref_label = "engine"
        ref_order = human_order if human_order else e["order"]
        if system == "engine":
            entry["metrics_vs"] = ref_label
            if human_order:
                entry["metrics"] = {
                    "spearman": round(spearman(e["order"], human_order), 4),
                    "mae": round(mae(e["order"], human_order), 3),
                    "top3_overlap": round(k_overlap(e["order"], human_order, 3), 3),
                    "bottom3_overlap": round(k_overlap(e["order"], human_order, 3, bottom=True), 3),
                }
            else:
                entry["metrics"] = None  # self-reference
        else:
            entry["metrics_vs"] = ref_label
            entry["metrics"] = {
                "spearman": round(spearman(a["order"], ref_order), 4),
                "mae": round(mae(a["order"], ref_order), 3),
                "top3_overlap": round(k_overlap(a["order"], ref_order, 3), 3),
                "bottom3_overlap": round(k_overlap(a["order"], ref_order, 3, bottom=True), 3),
            }
        cell["systems"][system] = entry

    # human order sanity: same candidate set?
    if human_order is not None:
        cell["human_set_matches_corpus"] = sorted(human_order) == sorted(texts)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(cell, indent=2, sort_keys=True), encoding="utf-8")

    print(f"[cell {args.name}] n={len(texts)} human={bool(human_order)} "
          f"engine_det={cell['systems']['engine']['deterministic']} "
          f"engine_rho={(cell['systems']['engine']['metrics'] or {}).get('spearman')}")
    for s in ("boolean-ats", "tfidf", "bm25"):
        m = cell["systems"][s]["metrics"]
        print(f"  {s:12s} rho={m['spearman']} mae={m['mae']} top3={m['top3_overlap']} "
              f"det={cell['systems'][s]['deterministic']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
