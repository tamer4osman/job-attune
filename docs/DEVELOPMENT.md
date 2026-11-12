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
                                 (omnidecide-c C11 via the layered resolver),
                                 alias/claim-quality machinery
  extraction + classification    PDF text layer -> cv/cover texts per candidate
  evidence stage                 per-requirement alias regexes -> evidence_score
                                 (none/partial/good/strong claim quality)
  aggregate_categories()         PURE aggregation core (uniform/req_share/global
                                 + zero_weight_factor + must_have_gate) -
                                 unit-testable, no I/O
  aggregate_stage()              orchestration: must-have pre-pass, category
                                 averages, values fit, kernel evaluate_score
  ranking + compare + choice     kernel-driven; near-tie order, rank-conflict
                                 escalation to review queue
  outputs                        canonical results.json + atomic progress.json
attune-engine/ckernel.py    kernel resolver: keeps the `import ckernel`
                                 seam, selects the tier per $ATTUNE_KERNEL
                                 (auto | native | wasm) + one audit stderr line
attune-engine/ckernel_native.py  Tier 1 (default): ctypes bridge to
                                 libomnidecide.so (omnidecide-c C11 kernel) -
                                 same class/payload contract the engine was
                                 written against
attune-engine/wasm_kernel.py     Tier 2 (fallback): wasmtime bridge to the
                                 vendored omnidecide.wasm - byte-identical
                                 decisions with no C toolchain
attune-engine/floors.py     vendored floors contract
                                 (data in data/floors_v1.json)
attune-engine/make_report.py  ReportLab PDFs (invariant mode) + manifest
attune-engine/floors_attune.json  floors contract (v1.0, frozen)
bench/run_bench.py               bench cell runner (double-pass + sha256)
bench/baselines.py               BooleanATS / TF-IDF / BM25 (candidate-blind)
scripts/check_python_side.py     45-check release gate (Python side)
scripts/smoke_test.py            fast health check: server + guard + all API
                                 routes + engine/reports + browser pass
scripts/e2e_check.py             deep UI walk in headless Chromium
scripts/design_check.py          design regression: fonts, palette, pills,
                                 overflow (Agenflow-style skin)
.fallowrc.json                  entry points for the fallow static analysis
                                 (dev-only; see QA pipeline #6)
scripts/attune_app/         sample generator
server.py + web/             stdlib-only Python web server + vanilla JS UI
vendor/omnidecide-c/           omnidecide-c 2.0.0 C11 kernel - DO NOT EDIT
                                 (build: libomnidecide.so, see SETUP.md)
vendor/omnidecide-wasm/        official WASM dist of the same kernel
                                 (fallback tier, DO NOT EDIT)
```

Hard rule: `vendor/omnidecide-c/`, `attune-engine/floors.py` and
`floors_attune.json` are **frozen contracts** (floors v1.0; the kernel
identity pins in every manifest). Changing either is a cross-repo
decision with its own calibration evidence, not a code task. The kernel
integration followed this rule: it shipped with a 36-case kernel A/B battery
and full-engine leaf-identical replay proving zero scoring change (see
docs/VERIFICATION-1.8.0.md).

## Environment

```bash
pip install -r requirements.txt    # reportlab + pypdf (engine: stdlib only)
python3 scripts/attune_app/make_samples.py   # demo corpus, if missing

# decision kernel tier - pick one (docs/LAYERED-KERNEL.md):
bash scripts/build-kernel.sh       # Tier 1 native: one-time build, full speed
pip install wasmtime               # Tier 2 portable fallback: zero build
```

The engine itself is stdlib-only (the resolver and both tier bridges
included); reportlab/pypdf are needed for the reporter and the PDF checks.
For the kernel, either build the native library once (a C11 compiler, full
speed) or `pip install wasmtime` for the portable WASM fallback - both tiers
return byte-identical decisions (docs/LAYERED-KERNEL.md).
Python 3.10+ (CI runs 3.12). On the native tier the spine features
(docs/SPINE-FEATURES.md) engage automatically; the 13-check spine battery
lives at `scripts/verify_spine_features.py` (evidence:
`verification/spine_features.txt`), the replay auditor at
`scripts/replay_audit.py` and the calibration report at
`scripts/calibrate_report.py`.

## The seven QA pipelines

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

### 2. Regression lock — scoring-lineage protection

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

### 3. UI end-to-end check — `scripts/e2e_check.py`

```bash
python3 server.py &            # the app under test
python3 scripts/e2e_check.py   # needs: pip install playwright + chromium
```

Drives the real UI in headless Chromium against the local server: scan the
demo folder, load the example profile, start a run, wait for completion,
verify all six result tabs render, open the candidate dossier, record a
review decision, generate and download the PDF exports, then reset the
wizard. 23 assertions, and the whole flow must produce **zero console
errors**. CI runs the same script (see the `ui` job in
`.github/workflows/ci.yml`).

### 4. Fast smoke test — `scripts/smoke_test.py`

```bash
python3 scripts/smoke_test.py            # full pass (~10 s)
python3 scripts/smoke_test.py --quick    # static + guard + API only
python3 scripts/smoke_test.py --api-only  # skip the browser phase
```

Self-contained health check for day-to-day work: boots its own `server.py`
on a scratch port and tears it down again. 54 assertions cover the boot,
every static asset, path-traversal containment, the loopback guard
(403 without `X-Attune-Client`, 403 on cross-site), all 13 API routes with
their error shapes, a full engine run + PDF export per shipped corpus
(sample-6, trades14, logistics14) with throughput numbers, and a browser
pass (scan → profile → run → results) with zero JS errors. Run it before
any commit that touches `server.py` or `web/`; run `e2e_check.py` (above)
for the full-depth UI walk before a release.

The `--keep` flag retains the run directories it created for inspection;
by default it cleans them up again.

### 5. Design regression check — `scripts/design_check.py`

```bash
python3 scripts/design_check.py [port]   # boots nothing; needs a live server
```

Guards the Agenflow-inspired skin (v1.1.0): 22 assertions verify the
self-hosted fonts actually load (Boldonse / DM Sans / Playfair Display
from `web/fonts/`, zero external hosts — the app must work air-gapped),
the cream / ink / orange / forest palette is applied (body background,
header, sticker badge, active step, footer), pill shapes and 18px card
radii are in place, nothing overflows horizontally, and the results
view + candidate dialog render in the new palette with zero JS errors.
Run it after any change to `web/css/app.css`, `web/fonts/` or the chart
color constants.

### 6. Frontend static analysis — `fallow` (CI gate, needs Node)

```bash
npx fallow@3.38.1 dead-code --ci
npx fallow@3.38.1 health --baseline .codebase-intel/fallow-health-baseline.json \
    --fail-on-issues --fail-on-stale-baseline
```

[fallow](https://fallow.tools) is a TS/JS codebase analyzer. It runs as a
required gate in `.github/workflows/codebase-intel.yml` (dead code,
duplication and architecture hard-gated; complexity ratcheted against
`.codebase-intel/fallow-health-baseline.json`). The shipped app still
needs **no Node.js** — the repo just carries `.fallowrc.json`, a 3-line
config that declares the entry points (`web/js/app.js` plus the
root-absolute `index.html` / `app.css` links its HTML plugin cannot
resolve on its own). Current state after the v1.1.0 cleanup pass: 0 dead
files, 0 dead exports, 0 duplication, maintainability 88.2; the 33
remaining complexity findings are baselined so new hotspots fail the
build while refactors ratchet the number down. The remaining deduction
is "unit size": the six view builders are large because they render
data-driven DOM section by section; the two former hotspots
(`openCandidateDialog` at cyclomatic 52 / 258 lines and `PositionReport`
at 34 / 214 lines) were split into per-section builders in that pass,
verified DOM-identical by a before/after Playwright snapshot diff. Run it
whenever you add or restructure modules under `web/js/`.

### 7. Codebase intelligence, Python + C — `scripts/codebase_intel.py`

```bash
python3 scripts/codebase_intel.py python   # ruff, vulture, pylint, pip-audit, lizard
python3 scripts/codebase_intel.py c        # cppcheck, flawfinder, lizard, jscpd
```

The per-language fallow equivalents (see [CODEBASE-INTEL.md](CODEBASE-INTEL.md)
for the full capability map): 19 checks, hard gates for dead code,
duplication, hygiene rules, cppcheck warnings and known CVEs; ratchets
against `.codebase-intel/ratchet-baselines.json` for the complexity and
clone metrics of the frozen engine and C kernel. After an accepted
refactor re-save the baseline (`--update-baseline`) and commit it with
your change — CI fails on a stale baseline so improvements are always
locked in.

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
python3 scripts/smoke_test.py                  # 54/54 fast health check
python3 scripts/e2e_check.py                   # full UI walk in headless Chromium
python3 scripts/design_check.py 3000           # 22/22 style checks (server up)
#    + regression lock vs stored lineage runs (3/3 PASS expected for
#      scoring-neutral releases)
# 5. Update README/SETUP/docs version references (search for the previous
#    version string to catch strays)
# 6. Package the source archive: copy the tree without dist/,
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
The `must_have_gate` option (v1.3.3) extends the same framework: `hard`
(default) keeps the historical flat 40/100 ceiling; `balanced` scales the
ceiling by the met weight share of the must-have block
(`0.40 + 0.60 * met_share`) — a profile-level policy choice, not a scoring
change; see `docs/ENGINE-CLI.md` and
`verification/case_study_plumber_1.3.3.txt`.
