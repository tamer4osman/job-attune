<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->
# Developer Guide

Everything a developer needs to work on Job Attune productively: how the
codebase is organised, which quality gates protect it, how to extend the
benchmark, and how to cut a release without breaking the determinism and
audit guarantees.

## Code map

```
attune-engine/engine.py     ~2,000 lines, the whole scoring pipeline:
  module head                    ENGINE_VERSION, REFERENCE_YEAR, vendored
                                 floors loader (floors.py), kernel binding
                                 (omnidecide-c C11, the only kernel),
                                 alias/claim-quality machinery
  extraction + classification    PDF text layer -> cv/cover texts per candidate
  evidence stage                 per-requirement alias regexes -> evidence_score
                                 (none/partial/good/strong claim quality)
  aggregate_categories()         PURE aggregation core (uniform/req_share/global
                                 + zero_weight_factor) - unit-testable, no I/O
  aggregate_stage()              orchestration: must-have pre-pass, category
                                 averages, values fit, kernel evaluate_score
  ranking + compare + choice     kernel-driven; near-tie order, rank-conflict
                                 escalation to review queue
  outputs                        canonical results.json + atomic progress.json
attune-engine/ckernel.py    ctypes bridge to libomnidecide.so (omnidecide-c
                                 C11 kernel): same class/payload contract the
                                 engine was written against
attune-engine/floors.py     vendored floors contract
                                 (data in data/floors_v1.json)
attune-engine/make_report.py  ReportLab PDFs (invariant mode) + manifest
attune-engine/floors_attune.json  floors contract (v1.0, frozen)
bench/run_bench.py               bench cell runner (double-pass + sha256)
bench/baselines.py               BooleanATS / TF-IDF / BM25 (candidate-blind)
scripts/check_python_side.py     45-check release gate (Python side)
scripts/attune_app/         JS check pipelines (Fallow), sample generator
src/                             Next.js UI + API routes + middleware
download/omnidecide-c/           omnidecide-c 1.0.0 C11 kernel - DO NOT EDIT
                                 (build: libomnidecide.so, see SETUP.md)
```

Hard rule: `download/omnidecide-c/`, `attune-engine/floors.py` and
`floors_attune.json` are **frozen contracts** (floors v1.0; the kernel
identity pins in every manifest). Changing either is a cross-repo
decision with its own calibration evidence, not a code task. The kernel
integration followed this rule: it shipped with a 36-case kernel A/B battery
and full-engine leaf-identical replay proving zero scoring change (see
docs/VERIFICATION-1.8.0.md).

## Environment

```bash
pip install -r requirements.txt    # reportlab + pypdf only
bun install                        # JS deps (or npm install)
npm install -g fallow              # optional: JS/TS check pipelines
python3 scripts/attune_app/make_samples.py   # demo corpus, if missing

# omnidecide-c kernel (one-time; see SETUP.md):
cd download/omnidecide-c
mkdir -p build
cc -std=c11 -ffp-contract=off -O2 -fPIC -shared -Iinclude -Isrc \
   src/*.c -lm -o build/libomnidecide.so
```

The engine itself is stdlib-only (ctypes bridge included); reportlab/pypdf
are needed for the reporter and the PDF checks; a C11 compiler is needed once
to build the decision kernel. Python 3.10+ (CI runs 3.12).

## The three QA pipelines

### 1. Python release gate — `scripts/check_python_side.py`

```bash
python3 scripts/check_python_side.py
# exit 0 required; SUMMARY line must read "45 green / 0 amber / 0 red"
```

45 checks in four groups:

- **A. Static** — AST unused-import scan on engine files; vendored floors
  contract + pinned calibration data.
- **B. Floors contract** — floors load via the vendored module, all six
  primitives present, values clamped to [0, 1], match the calibration values.
- **C. Functional** — full engine run on the demo corpus **twice**; sha256
  determinism; descending ranking; all six primitives load-bearing; noul
  escalation present; PII persistence probes; enrichment, review-readiness,
  accuracy-remediation (C27–C32), tuned-evidence (C33–C35) and bench-baseline
  (C36–C38) probes.
- **D. Report** — `make_report.py` export run; every PDF parses (pypdf),
  page counts sane, manifest sha256 hashes match recomputed file hashes.

Run it before every push. It is the definition of "the tree is healthy".

### 2. JS/TS check pipelines — `scripts/attune_app/js_check_pipelines.py`

```bash
python3 scripts/attune_app/js_check_pipelines.py
# OVERALL must not be RED (0 red). Raw envelopes: scripts/attune_app/checks_out/
```

Seven Fallow-powered pipelines (dead code, circular deps, unresolved imports,
duplication, complexity, styling drift, feature flags), each graded
red/amber/green with file:line evidence and ownership-zone classification
(app = Job Attune code, scaffold = shadcn kit, infra = config). Release
rule: **0 red**. Amber findings are reviewed, not auto-fixed; scaffold-zone
findings (unused shadcn files) are accepted by design.

### 3. Regression lock — scoring-lineage protection

The lock replays **stored reference-lineage run inputs** through the current
engine and diffs every content leaf against the stored results, under an
explicit allowlist:

| Allowed diff class | Why |
|---|---|
| wall-clock stamps | runs record generation time |
| version pins | manifest engine version moves with releases |
| determinism self-hashes | hashes of the run's own outputs change with version |
| run label / run_id | storage metadata, not scoring |
| additive blocks | e.g. additive provenance blocks added by a release |

Anything else matching = scoring changed = release blocked until either the
change is reverted or the allowlist amendment is **documented in the
CHANGELOG** with its evidence. This is how the aggregation framework shipped a
refactor with *zero* scoring change — the lock proved it, not the release
notes.

## Adding a bench corpus

A bench cell = corpus + job profile + frozen human ranking. Protocol
(mandatory for any corpus used in claims):

1. Create `bench/corpora/<name>/` with `candidates/<folder>/cv.pdf` (one
   folder per candidate), `profile.json` (job profile in the standard
   schema), `manifest.json`.
2. Write the human ranking **before** running the engine: `human_ranking.json`
   as `{"ranking": ["folder-a", "folder-b", ...]}` — complete order, ties
   expressed by your chosen convention, frozen thereafter.
3. Freeze the pre-registration: `sha256sum profile.json human_ranking.json >
   preregistration.sha256`. The ranking must never change after an engine run
   touched the corpus.
4. Run the cell (double-pass determinism is automatic):

```bash
python3 bench/run_bench.py \
  --corpus bench/corpora/<name>/candidates \
  --profile bench/corpora/<name>/profile.json \
  --human bench/corpora/<name>/human_ranking.json \
  --name bench-<name> --salt task32-study \
  --out /tmp/bench-<name>.json
```

5. Record results in `bench/README.md` (numbers + one-line mechanism note).
   Report inconvenient cells openly — the harness exists to find them before
   a customer does.

Synthetic CVs for holdouts are generated as text-layer PDFs (reportlab) so
all systems rank the same extracted bytes; keep that property if you add
corpora, or extraction differences will contaminate the comparison.

## Determinism rules for contributors

- No wall-clock reads in score paths — date math goes through the pinned
  `REFERENCE_YEAR` (`--reference-year` for replays).
- Persisted JSON is canonical: sorted keys, no floats where rounding is
  specified (`round2`), no timestamps inside score paths.
- ReportLab runs in invariant mode; never add non-deterministic content
  (timestamps, random ids, hostnames) to PDFs.
- Near-tie ordering is resolved deterministically by candidate ref under the
  run salt; do not introduce iteration-order-dependent tie-breaking (use
  `sorted(...)` with explicit keys, never `set`/`dict` iteration order).
- The pseudonymisation salt defaults to the run-dir name; replaying a stored
  run requires the same run-dir name or an explicit `--salt`.

## PII & redaction rules

Raw CV text is never persisted anywhere. New output fields must (a) derive
from structured evidence, (b) pass the gate's PII probes (emails, phones,
local paths), and (c) reference candidates by 10-hex ref, never by name.
Folder names are scrubbed from review-queue details. If your feature needs
free text, length-cap it and route it through the existing scrubbers.

## Release checklist

```bash
# 1. Code + docs ready; version decided (semver: scoring/API change = minor,
#    fix/docs = patch; scoring changes need calibration evidence first)
# 2. Bump ENGINE_VERSION in attune-engine/engine.py
# 3. CHANGELOG.md entry (what changed, why, evidence pointers)
# 4. Gates:
python3 scripts/check_python_side.py          # 45/45 green
python3 scripts/attune_app/js_check_pipelines.py   # 0 red
#    + regression lock vs stored lineage runs (3/3 PASS expected for
#      scoring-neutral releases)
# 5. Update README/SETUP/docs version references (search for the previous
#    version string to catch strays)
# 6. Package the source archive: copy the tree without node_modules/, .next/,
#    build/, db/, logs; verify required members + absence of dev artifacts
# 7. Prove relocatability: unzip to a FOREIGN path, run the 45-gate there
# 8. Refresh the download page and verify served bytes == posted sha256
```

## Working with the aggregation framework

`aggregate_categories()` is pure and unit-testable — prefer adding tests
against it directly over end-to-end probes. If you experiment with forms,
follow the calibration discipline: preregister a frozen search space and a
selection rule, run the grid engine-native, and do not ship a default flip
without the same rigor (publish wins AND losses in the CHANGELOG).
