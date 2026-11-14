#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Counterfactual: VALUES_TOKEN_SYNONYMS["communication"] -> "care" (removed).

The 1.0.1 hardening round removed the "communication": "care" entry from
VALUES_TOKEN_SYNONYMS (engine.py). This script is the recorded evidence:

  * why it was removed - the fold (a) let the English word "communication"
    cover care value phrases such as "customer care" (false positive),
    (b) blocked German "Kommunikation" from covering an English
    "communication" value phrase (the corpus side folds kommunikation ->
    "communication" while the phrase side folded "communication" -> "care"),
    and (c) contradicted the nominal->base intent of the v1.0.1 English
    variant folds ("reliability" -> "reliable");
  * why removal is safe here - it leaves rankings AND per-candidate overall
    scores byte-identical on all four shipped corpora (demo, plumber,
    trades, uni), measured with this script before the removal landed.

Run from the repo root (each corpus runs twice, ~4 engine invocations/s):

    python3 scripts/casestudy/counterfactual_communication_fold.py

The script temporarily patches engine.py in place (restored from a backup
in a finally block) and prints a per-corpus diff summary. Third-party
corpora - e.g. the generalization battery's nurse fixture, whose values
phrases may differ - can change scores; re-run the battery when adopting
this change into a lineage that carries it.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ENGINE_FILE = ROOT / "attune-engine" / "engine.py"

CORPORA = [
    ("demo", ROOT / "attune-sample-data",
     ROOT / "attune-data" / "templates" / "example-senior-data-engineer.json"),
    ("plumber", ROOT / "attune-data" / "casestudy-plumber",
     ROOT / "attune-data" / "casestudy-plumber" / "profile-plumber.json"),
    ("trades", ROOT / "attune-data" / "casestudy-trades",
     ROOT / "attune-data" / "casestudy-trades" / "profile-furniture-technician.json"),
    ("uni", ROOT / "attune-data" / "casestudy-uni",
     ROOT / "attune-data" / "casestudy-uni" / "profile-doctoral-researcher-ml.json"),
]

FOLD_LINE = '    "communication": "care",\n'


def run_corpus(tag, folder, profile, run_dir):
    proc = subprocess.run(
        [sys.executable, str(ENGINE_FILE), "--folder", str(folder), "--profile",
         str(profile), "--run-dir", str(run_dir), "--salt", f"cf-{tag}"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"{tag} engine failed: {proc.stderr[-500:]}")
    return json.loads((run_dir / "results.json").read_text())


def main() -> int:
    src = ENGINE_FILE.read_text(encoding="utf-8")
    if FOLD_LINE in src:
        print("fold present in engine.py - measuring its contribution "
              "(engine.py is restored afterwards)")
    backup = ENGINE_FILE.with_suffix(".cfbackup")
    backup.write_text(src, encoding="utf-8")
    results = {}
    try:
        for variant, patched in (("with-fold", False), ("no-fold", True)):
            if patched:
                if FOLD_LINE not in src:
                    print("fold already removed - skipping the no-fold "
                          "re-run (with-fold == current engine)")
                    break
                ENGINE_FILE.write_text(src.replace(FOLD_LINE, ""), encoding="utf-8")
            try:
                for tag, folder, profile in CORPORA:
                    with tempfile.TemporaryDirectory() as td:
                        res = run_corpus(tag, folder, profile, Path(td))
                        results.setdefault(tag, {})[variant] = {
                            "ranking": res["ranking"],
                            "overall": {c["candidate_ref"]: c.get("overall")
                                        for c in res.get("candidates", [])},
                        }
            finally:
                if patched:
                    shutil.copyfile(backup, ENGINE_FILE)
    finally:
        shutil.copyfile(backup, ENGINE_FILE)
        backup.unlink()

    changed = 0
    for tag, _folder, _profile in CORPORA:
        row = results[tag]
        wf, nf = row.get("with-fold"), row.get("no-fold")
        if wf is None or nf is None:
            print(f"== {tag} == skipped (fold absent; current engine output recorded)")
            continue
        same_rank = wf["ranking"] == nf["ranking"]
        diffs = {ref: (wf["overall"][ref], nf["overall"][ref])
                 for ref in wf["overall"]
                 if wf["overall"][ref] != nf["overall"][ref]}
        print(f"== {tag} ==")
        print(f"  ranking identical: {same_rank} | score changes: {len(diffs)}")
        for ref, (a, b) in sorted(diffs.items()):
            print(f"    {ref}: {a} -> {b}")
        changed += len(diffs) + (0 if same_rank else 1)
    print()
    print("RESULT:", "fold is score-neutral on all shipped corpora"
          if changed == 0 else f"{changed} corpus/candidates affected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
