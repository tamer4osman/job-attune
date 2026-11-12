<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->
# Manual-labor case study - Furniture Technician (Assembly & Service)

A screening fixture built to compare Job-Attune's ranking against a human
expert's ranking on manual-labor hiring data: 12 fictional applicants, 25
PDFs (7 German documents), planted mistags, an extra certificates document,
and a corpus of transferable-trade vocabulary (plumber, mover, hotel
maintenance, gig assembler, career changer).

The fixture is maintained under the current 1.0.1 release; the iteration
notes below preserve the version labels the observations were recorded
under.

**Grounding.** Profile requirements are modelled on published criteria for
comparable positions, retrieved 2026-11-11: Havertys "Furniture Service
Technician" (jobs.havertys.com), Cushman & Wakefield "Workplace Services
Technician" (careers.cushmanwakefield.com), furniture installer postings
(reading assembly instructions and layout plans), and German "Kuechen- und
Moebelmonteur / Tischler" postings on the Bundesagentur fuer Arbeit job
board (10001-1003465780-S). The hiring company ("Kantholz
Einrichtungswerke GmbH") and all applicants are fictional.

## Head-to-head protocol

`expert/expert_rubric.md` and `expert/expert_ranking.json` were committed
BEFORE any engine run on this profile; `expert/comparison.json` holds the
comparison metrics recorded during the original pilot loop (Spearman,
overlaps, per-candidate deltas). The corpus and the expert ranking were never
modified after tool output was seen. Current-engine regression values for
all three tuned fixtures are recorded in the root `CHANGELOG.md`.

## Reproduce

```bash
# main run (native tier, spine auto)
python3 attune-engine/engine.py \
  --folder attune-data/casestudy-trades/candidates \
  --profile attune-data/casestudy-trades/profile-furniture-technician.json \
  --run-dir attune-data/runs/casestudy-trades-native

# determinism re-run (the salt defaults to the run-directory name,
# so pass the original one explicitly)
python3 attune-engine/engine.py --folder attune-data/casestudy-trades/candidates \
  --profile attune-data/casestudy-trades/profile-furniture-technician.json \
  --run-dir attune-data/runs/casestudy-trades-native-determinism \
  --salt casestudy-trades-native

# WASM fallback tier
ATTUNE_KERNEL=wasm python3 attune-engine/engine.py \
  --folder attune-data/casestudy-trades/candidates \
  --profile attune-data/casestudy-trades/profile-furniture-technician.json \
  --run-dir attune-data/runs/casestudy-trades-wasm --salt casestudy-trades-native

# report export
python3 attune-engine/make_report.py --run-dir attune-data/runs/casestudy-trades-native
```

The pilot loop also used a local study harness (`scripts/casestudy/`, an
internal workspace that is not part of the shipped tree). Its frozen outputs
are committed here: the pilot profile and `expert/comparison.json`.

## Files

| Path | Contents |
|---|---|
| `profile-furniture-technician.json` | Final profile (v2): DE plural/compound + EN client synonym coverage |
| `profile-furniture-technician-pilot.json` | Pilot profile (v1) that exposed the alias gaps |
| `candidates/` | 12 applicant packets, one sub-folder each |
| `ground_truth.json` | True document roles, language, planted challenge per candidate |
| `expert/` | Committed expert rubric, ranking, and comparison metrics |

## Iterations (documented pilot loop)

1. **v1 profile (pilot)** - German applicants sank for linguistic reasons
   (singular aliases vs plural/compound CV vocabulary; "built-in
   wardrobes"/"clients" missed the EN alias net): marco capped at 40,
   marcel/tobias at ranks 6-7. Preserved as
   `profile-furniture-technician-pilot.json` +
   `attune-data/runs/casestudy-trades-run1-alias-gaps/`.
2. **v2 aliases** - 19 aliases added across 6 requirements (data only,
   uniform for all candidates); marco recovered to #5, German packets gained
   mention credit. Residual bilingual penalty (English-biased
   `token_fraction`) remains and is documented.
3. **Counterfactual** - whitespace-tolerant multi-word alias matching moves
   david_osei 40.0 -> 74.7 (rank 10 -> 5), matching the expert view;
   recorded as the evidence base for the line-wrap-tolerant alias change
   that followed.

Run directories preserve every iteration (`casestudy-trades-run1-alias-gaps`,
`-native`, `-native-determinism`, `-wasm`, `-counterfactual-tolerant`).
`expert/comparison.json` is the frozen evidence artifact.
