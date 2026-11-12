<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->
# University case study — Doctoral Researcher (PhD) in Machine Learning

A reusable bilingual (DE/EN) screening fixture built to exercise Job-Attune
on realistic university hiring data: 12 fictional applicants, 22 PDF
documents, planted mistags, decoy filenames and a combined letter+CV PDF.

The fixture is maintained under the current 1.0.1 release; the iteration
notes below preserve the version labels the observations were recorded
under.

**Grounding.** The job profile's requirements are modelled on the published
eligibility criteria of the TU Berlin Machine Learning Group
(https://web.ml.tu-berlin.de/jobs, retrieved 2026-11-11): Master's in
computer science *or physics*; proven programming experience (Python,
PyTorch/NumPy/JAX, C++/Rust/Julia); Git; English proficiency; excellent
communication; publications desirable but not required. The hiring
university ("Universitaet Alt-Moabit") and all applicants are fictional.

## Reproduce

```bash
# main run (native tier, spine auto)
python3 attune-engine/engine.py \
  --folder attune-data/casestudy-uni/candidates \
  --profile attune-data/casestudy-uni/profile-doctoral-researcher-ml.json \
  --run-dir attune-data/runs/casestudy-uni-native

# determinism re-run (the salt defaults to the run-directory name,
# so pass the original one explicitly)
python3 attune-engine/engine.py --folder attune-data/casestudy-uni/candidates \
  --profile attune-data/casestudy-uni/profile-doctoral-researcher-ml.json \
  --run-dir attune-data/runs/casestudy-uni-native-determinism \
  --salt casestudy-uni-native

# report export
python3 attune-engine/make_report.py --run-dir attune-data/runs/casestudy-uni-native
```

The pilot loop also used a local study harness (`scripts/casestudy/`, an
internal workspace that is not part of the shipped tree); its frozen outputs
are the two profiles committed here and the run directories named below.

## Files

| Path | Contents |
|---|---|
| `profile-doctoral-researcher-ml.json` | Final profile (v2): German alias coverage |
| `profile-doctoral-researcher-ml-pilot.json` | Pilot profile (v1) that exposed the alias gaps |
| `candidates/` | 12 applicant packets, one sub-folder each |
| `ground_truth.json` | True document roles, language, planted challenge per candidate |

## Iterations (documented pilot loop)

1. **v1 profile (pilot)** — German applicants sank to the bottom: "MSc
   Informatik" matched no degree alias, "kommunikation"/"zusammenarbeit"
   matched no soft-skill alias → must-have failures for purely linguistic
   reasons. Preserved as `profile-doctoral-researcher-ml-pilot.json` +
   `attune-data/runs/casestudy-uni-run1-alias-gaps/`.
2. **v2 aliases** — German aliases added to the profile (data, not code);
   must-haves recovered (6/6), scores roughly doubled. Remaining gap:
   values_fit = 0.0 for German letters (English values text, no German
   kernel language pack).
3. **E1 values fold (1.3.1 lineage)** — `VALUES_TOKEN_SYNONYMS` extended
   with academic German value vocabulary so German applications are scored
   on equal footing; English corpora are unaffected (release gate green).

Run directories preserve every iteration (`casestudy-uni-run1-alias-gaps`,
`-run2-values-gap`, `-native`, `-native-determinism`, `-wasm`). Current
engine regression values for the tuned fixtures are recorded in the root
`CHANGELOG.md`.
