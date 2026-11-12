<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->
# Manual-labor case study - Plumber / Sanitary & Heating Technician (SHK)

A bilingual (DE/EN) screening fixture for a manual-labor trade: 12 fictional
applicants, 24 PDF documents (16 German), planted mistags, a single mixed
application document, an extra certificates document, and two negative
controls (a trade switcher and a sales-only profile).

The fixture is maintained under the current 1.0.1 release; the notes below
preserve the version labels the observations were recorded under.

**Grounding.** Requirements are modelled on published criteria for
comparable positions, retrieved 2026-11-11: German Anlagenmechaniker SHK
(sanitary, heating and climate) postings on the Bundesagentur fuer Arbeit
job board (completed SHK vocational training, drinking-water and drainage
installation, heating systems, on-call rotation, Fuehrerschein Klasse B),
and standard English-language service-plumber postings (installation and
repair of water supply lines, drains and fixtures, water heaters, leak
diagnosis, customer-facing service calls). All applicants are fictional.

## Head-to-head protocol

`expert/expert_rubric.md` and `expert/expert_ranking.json` were committed
BEFORE any engine run on this profile; `expert/comparison.json` holds the
comparison metrics recorded during the original pilot loop (Spearman,
overlaps, per-candidate deltas). `preregistration.sha256` freezes the rubric,
ranking, ground truth and pilot profile; the release gate (C38) re-verifies
those hashes on every run. The corpus and the expert ranking were never
modified after tool output was seen. Current-engine regression values for
all three tuned fixtures are recorded in the root `CHANGELOG.md`.

The profile opts into `weights.must_have_gate = "balanced"` and
`category_weighting = "req_share"`, mirroring the weighted-criteria expert
rubric. Both are profile-level policy choices, not engine defaults; see
`docs/ENGINE-CLI.md`.

## Reproduce

```bash
# main run (native tier, spine auto)
python3 attune-engine/engine.py \
  --folder attune-data/casestudy-plumber/candidates \
  --profile attune-data/casestudy-plumber/profile-plumber.json \
  --run-dir attune-data/runs/casestudy-plumber-native

# determinism re-run (the salt defaults to the run-directory name,
# so pass the original one explicitly)
python3 attune-engine/engine.py --folder attune-data/casestudy-plumber/candidates \
  --profile attune-data/casestudy-plumber/profile-plumber.json \
  --run-dir attune-data/runs/casestudy-plumber-native-determinism \
  --salt casestudy-plumber-native

# report export
python3 attune-engine/make_report.py --run-dir attune-data/runs/casestudy-plumber-native
```

The pilot loop also used a local study harness (`scripts/casestudy/`, an
internal workspace that is not part of the shipped tree). Its frozen outputs
are committed here: the pilot profile, the expert artifacts and
`expert/comparison.json`.

## Files

| Path | Contents |
|---|---|
| `profile-plumber.json` | Final profile (v2): balanced gate, rubric-weighted categories, DE/EN alias coverage |
| `profile-plumber-pilot.json` | Pilot profile (v1) that exposed the alias gaps; hash-frozen in `preregistration.sha256` |
| `candidates/` | 12 applicant packets, one sub-folder each |
| `ground_truth.json` | True document roles, language, strength and planted challenge per candidate |
| `preregistration.sha256` | Frozen hashes of the rubric, ranking, ground truth and pilot profile |
| `expert/` | Committed expert rubric, ranking, and comparison metrics |

## Iterations (documented pilot loop)

1. **v1 profile (pilot)** - alias gaps on German trade vocabulary and
   compound job titles; pilot run preserved as
   `attune-data/runs/casestudy-plumber-run1-alias-gaps/`.
2. **v2 aliases and gate policy** - data-only alias expansion plus the
   balanced must-have gate and rubric-weighted categories; candidate
   documents untouched, engine defaults unchanged.
3. **Line-wrap-tolerant matching** - whitespace-tolerant multi-word alias
   matching removes the split-title misses recorded by the counterfactual
   run (`casestudy-plumber-counterfactual-tolerant`).

Run directories preserve every iteration (`casestudy-plumber-run1-alias-gaps`,
`-native`, `-native-determinism`, `-counterfactual-tolerant`).
`expert/comparison.json` is the frozen evidence artifact.
