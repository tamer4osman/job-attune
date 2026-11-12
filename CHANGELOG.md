<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->
# Changelog

All notable changes to the Job Attune engine, UI and tooling.
Engine version is the project's release version; every run manifest records
the engine, decision-kernel and floors versions that produced it.

## [1.0.1] - 2026-11-12

General-reliability round: turns the cold-start generalization battery's
root-caused findings into title-agnostic engine mechanisms. Goal per the
product owner: reliability a recruiter can trust for ALL professional and
technical job titles and languages, while per-client profile vocabulary
remains the acknowledged calibration surface.

### Added

- **Profile vocabulary lint** (`attune-engine/profile_lint.py`, v1.0.1):
  deterministic checklist run at profile-creation time, BEFORE preregistration
  or any engine run. Rules R0-R7 encode the three counterfactual-confirmed
  cold-start failure modes (R1 over-broad credential aliases, R2 rigid
  credential-string aliases, R3 order-fragile multi-word aliases without bare
  head nouns) plus structural checks (R4 must-have alias coverage across
  languages, R5 literal alternations the matcher can never hit, R6 duplicates,
  R7 values_text convention). Validated against the battery: flags exactly the
  three planted defects (nurse 'state examination', accountant 'accounting
  degree', baker 'gesellenbrief baecker') and the two unmatchable ' or '
  skill phrases; the tuned plumber/trades/uni profiles carry zero R1/R5
  errors. Exit 1 on any ERROR severity finding.
- `docs/GENERAL-RELIABILITY.md` - protocol and results summary for the
  generalization battery v1 (four professions) and v2 (six professions).

### Changed

- **Clause-scoped claim-quality windows** (`_claim_quality`, v1.0.1): the
  +/-45/40-char marker windows are clipped to the comma/dash-separated CLAUSE
  containing the hit instead of the whole sentence, so 'medication
  administration, basic wound care' no longer caps medication administration
  with the 'basic' that scopes wound care. Parentheses stay attached ('Python
  (basic scripts)' keeps its downgrade); hyphenated compounds are never split.
- **PDF line-wrap tolerant alias matching** (`alias_regex`, v1.0.1): runs of
  whitespace inside a multi-word alias match any whitespace run in the
  document. PDF extraction reflows paragraphs, so 'full patient care' arrives
  as 'full patient\ncare' and silently matched NOTHING - a title- and
  language-agnostic false-negative class. This one fix restored the
  university corpus's designed-top candidate (anna_kowalska, falsely capped
  since 1.3.1 by an 'English C1' gap created by a line wrap) and the trades
  corpus's david_osei.
- **Cross-lingual value-token packs + tolerance** (v1.0.1): the German->English
  VALUES_TOKEN_SYNONYMS fold extends to healthcare/care, office/finance and
  service-attitude vocabulary (Einfuehlung, Wuerde, Pflege, Verschwiegenheit,
  Genauigkeit, Fristen, Mandant, ...); corpus-side folding is compound-tolerant
  (head-final German compounds fold via embedded keys, 'Grundpflege' -> care);
  the phrase side is normalized through the same dictionary ('reliability' ->
  'reliable'); plural forms (+s/+es) are tolerated on both sides. German
  packets no longer score values_fit 0.0 on unseen value domains.
- `ENGINE_VERSION` 1.3.3 -> 1.0.1.
- **Slim release artifacts** (packaging): the source zip now ships
  runtime-essential files only - 371 entries / 1.6 MB (was 587 / 4.8 MB).
  Dropped: kernel golden vectors, regression/demo run outputs (the server
  recreates `attune-data/runs/` at startup), documentation screenshots and
  diagrams, benchmark harness, verification-round artifacts, CI workflows,
  vendor dev/QA assets (tests, e2e, examples, tools, schema) and CHANGELOG.
  Nothing load-bearing changed: server, engine, web UI, sample data,
  templates, the prebuilt kernel and the kernel build sources all stay.
- **Slim standalone runtime** (`scripts/standalone/package.sh`): the packaged
  CPython runtime is stripped of DWARF debug info (~200 MB in libpython
  alone) and trimmed of Tcl/Tk + Tix + IDLE, lib2to3, ensurepip wheels,
  C headers, pkg-config, terminfo/man and build-only config dirs; the Linux
  x64 archive drops 74 MB -> 26 MB. Launcher contract and engine behavior
  unchanged (boot + engine smoke re-verified on the stripped runtime).
- **Code-quality pass across all languages**: ruff clean (2 vendor findings
  fixed in `tools/gen_types.py`); dead code removed (unused
  `DOMAIN_ANCHOR_MIN_LEN`, unused `norm_sha`, an always-true `or True`
  branch, stale `pdf_inspector.py` debug constants pointing at a local
  `D:/Projects` path - now argument-driven); fallow dead-code/dupes/health
  on the web frontend (maintainability 86.5, zero duplication, the 2 vendor
  e2e files intentionally out of the web entry graph); shellcheck clean;
  flawfinder level>=4 = 0 hits; lizard complexity within the ratcheted
  baselines. Stale version references corrected (START-HERE.txt 1.1.0 ->
  1.0.1, Dockerfile/SETUP.md mount examples 1.3.0/1.0.0 -> 1.0.1).

### Verification (generalization battery v2 + full regression)

- Battery v2 (six professions - nurse, tax accountant, electrician, baker,
  Kfz-Mechatroniker, Medizinische Fachangestellte - zero profile tuning after
  preregistration; the two new professions passed the lint gate first):
  Spearman vs preregistered order, hard gate: mean 0.714 -> **0.771**
  (nurse 0.371 -> 0.543, mfa 0.886 at true cold start with a third-language
  probe); balanced gate mean 0.757 -> **0.809**. Mechanism checks 37/45 as
  formulated; every remaining FAIL is root-caused (nurse = the documented CF1
  profile artifact the lint now flags; switcher checks = the standard-6-slot
  formulation, the reframed zero-gap principle passes 5/6 with the nurse
  failure being exactly that artifact; mfa F1 10/12 = the Polish probe's
  documents correctly routed via filename fallback while the content
  classifier honestly abstains). Replay pins 696/696 'exact'; determinism
  PASS on all runs; native/WASM rankings byte-identical.
- Regression on the three tuned corpora, 1.3.3 vs 1.0.1, unchanged profiles:
  plumber order identical, rho 0.748 -> 0.748; trades rho 0.741 -> **0.860**
  (david_osei line-wrap recovery, marco_bianchi cross-language marker-leak
  correction: English '(fluent)' no longer leaks into the German claim, his
  honest A2 declaration now correctly gates the German must-have); university
  design-strength rho 0.582 -> **0.862** (anna_kowalska, the designed-top
  candidate, recovers from the line-wrap false gap). Trades balanced-gate
  opt-in tested and DECLINED by the mechanical rule (0.846 < 0.860 hard).
- Kernel binaries unchanged: native lib and WASM module sha256 identical to
  1.3.3; the 39-case kernel battery contract is untouched by construction.
- Cross-platform release pipeline validated and hardened (v1.0.1): the three
  standalone archives (Linux x64 / macOS arm64 / Windows x64) build in
  `.github/workflows/release.yml` via `scripts/standalone/package.sh`, gated
  by an engine smoke on every runner plus a Linux boot smoke. Fixed for the
  Windows leg: `package.sh` now normalizes MSYS-style paths to drive-letter
  form (`cygpath -m`) before any path reaches native Windows Python (the
  kernel env var and staging heredocs previously passed `/d/a/...`-style
  paths that Windows Python cannot resolve). Fixed stale `src/` kernel paths
  in `ci.yml` (engine/ui jobs) and `scripts/codebase_intel.py` `C_DIRS` to
  the real `odk-core`/`odk-brain`/`odk-spine` layout, and re-ratcheted the C
  baseline over the vendored 2.0.0 kernel (lizard 60/15/136, flawfinder 16,
  jscpd 84/1578/4.16%); `cppcheck_style` keeps its pre-2.0.0 value until the
  one documented re-ratchet (`scripts/codebase_intel.py c --update-baseline`).
  Linux leg proven end-to-end from this tree: archive built, kernel
  reproducible byte-for-byte (sha256 `bc4159b9…`), bundled-runtime engine
  output byte-identical to the canonical tree at equal salt, packaged server
  answered `/api/template` (200); rankings identical across gcc -O0/-O2/-O3.
- Known limitations (documented, not hidden): content classification
  abstains ('unsure') on languages outside its de/en vocabulary - filename
  routing still classifies and reads the documents; third-language alias
  coverage remains per-client profile work; the hard-gate mid-table cap
  remains available and balanced remains the recommendation for mixed-language
  corpora.

## [1.3.3] - 2026-11-12

Balanced-gate round: ships the structural fix for the divergence the plumber
fix round documented but refused to tune away ("the hard must-have cap cannot
express the expert rubric's experience-vs-qualification / language-as-enabler
trade-offs", `verification/case_study_plumber_1.3.2.txt` §[9]).

### Added

- **Balanced must-have gate** (`weights.must_have_gate = "hard" | "balanced"`,
  default `hard`): for candidates with unresolved must-haves, the score ceiling
  interpolates between the historical hard 40/100 and full credit by the MET
  weight share of the must-have block, `cap = 0.40 + 0.60 * met_share`. The
  gate's verdict semantics (evidence >= 0.6), review-queue flags, shortlist
  exclusion and gap lists are unchanged - only the ceiling moves, and a
  candidate whose evidence is below the ceiling is still scored by evidence
  alone. Balanced runs add `gate_ceiling` / `gate_binding` per candidate;
  hard-mode payloads stay byte-stable with pre-1.3.3 runs. Documented in
  `docs/ENGINE-CLI.md` (aggregation profile keys).
- `scripts/casestudy/plumber_balanced_verification.py` - regenerates
  `verification/case_study_plumber_1.3.3.txt` from the on-disk runs (gate
  table, expert-vs-tool comparison, old-corpus regression, engine gates).

### Changed

- **Plumber case-study profile alignment** (disclosed in `study_note`; the
  only profile that opts in): `category_weighting=req_share` mirrors the
  committed expert rubric's weighted-criteria structure
  (A30/B15/C12/D15/E8/F12/G8) and `must_have_gate=balanced` expresses the
  rubric's "language as enabler, not checkbox" trade-off. Candidate documents
  untouched; every other profile keeps `uniform` + `hard`.
- `ENGINE_VERSION` 1.3.2 -> 1.3.3; the `aggregation` provenance block records
  the gate mode (new `must_have_gate` key - the only in-payload difference on
  default runs, see the regression note below).

### Verification (plumber/SHK corpus, expert ranking committed before any run)

- Expert-vs-tool Spearman 0.65 (v1.3.2 hard) -> **0.748** (v1.3.3 balanced);
  abdul_rahimi (A2 German, trade-strong) #9 -> #5 against expert #4, the
  electrician control holds #11 and the negative control holds #12, the
  shortlist set is unchanged (5 gap-free candidates).
- **Old-corpus regression (the fix must not move previous job offers):**
  trades, university and logistics14 corpora re-run under the 1.3.3 engine
  with their unchanged profiles are candidate-level byte-identical with the
  1.3.2 baselines (only diff: the new `aggregation.must_have_gate='hard'`
  provenance key and the determinism hashes that cover it).
- QA gates: `kernel_ab_battery` 39/39, `verify_spine_features` 13/13,
  `smoke_test` all green, `check_python_side` 45/45,
  `verify-layered-kernel` PASS; cross-tier ranking/overalls identical, spine
  pins 232/232 replay `exact`, calibration error 0.041 (12 sign-offs).
- Residual divergence documented, not tuned away: packet-quality scoring
  (bogdan), proven-volume depth (felix), minor-repairs vocabulary in the
  frozen alias table (julia), Spanish qualification aliases (anton),
  top-3 internal order. See `verification/case_study_plumber_1.3.3.txt` §[5].

## [1.3.2] - 2026-11-12

Fix round for the ten issues the plumber/SHK manual-labor case study raised
(`verification/case_study_plumber.txt` §10); re-verified on the same frozen
corpus plus the trades and university corpora
(`verification/case_study_plumber_1.3.2.txt`).

### Fixed

- **I1/I8 negation & disclaimer guard** (evidence matching): an alias hit
  whose own sentence negates the requirement — "... and I am honest: I have
  not done them yet", "Mir ist klar, dass mir die Ausbildung ... fehlt.",
  "German (none)" — is no longer evidence. Multilingual sentence-scoped cue
  list with contrast pivots (`sondern`/`but`), "not only / nicht nur"
  exceptions, parenthetical ownership (`English (native), German (none)` no
  longer negates the English claim) and mid-word window-cut protection
  (`Notdienst` was being cut to `Not`). Suppressed hits persist per
  requirement as `negated_hits`; snippet support now requires a positive
  hit. The electrician with zero plumbing experience no longer ranks #2 of
  12 on the strength of his own disclaimer.
- **I2 tag-conflict review floor** (`spine_kernel.TAG_MIN_CONFIDENCE` 0.6 →
  0.5, at the Tier A no-rule prior): a real cv/cover conflict expresses
  ~0.53 on the binary scheme pair, so planted mistags now reach the human
  queue (both `petra_lindner` mistags raise `tag_conflict` items).
- **I3 language-fair scoring**: claim-quality marker vocabulary is
  multilingual (`Muttersprache`, `verhandlungssicher`, `Firmenwagen`,
  `eigene Werkzeugausstattung`, ...); CEFR A1/A2 self-ratings are
  low-proficiency claims (a planted language gap stays a gap); token
  coverage takes the best matched ALIAS phrase into account
  (`Fuehrerschein Klasse B` covers `class B driving licence`); the most
  informative declaration wins over bare mentions; `LEVEL_BANDS` gained the
  German level vocabulary for the profile language table
  (`Muttersprache`, `gute Kenntnisse`, `Grundkenntnisse`, ...).
- **I4 values fold** extended with trades/service vocabulary (de+en):
  `Handwerk`/`workmanship` → craftsmanship, `saubere Arbeit` → quality,
  `Kundennaehe`/`Kundendialog` → customer, `Kundenservice`/`Dienstleistung`
  → service, `Teamgeist`/`team` → teamwork, `Arbeitsschutz` → safety,
  `Sorgfalt` → care, `communication` → care (values context only).
- **I5 compound-tolerant alias matching**: a single-word alias of ≥ 5
  letters may continue into a German compound or plural
  (`heizung` → `Heizungsservice`, `trinkwasser` →
  `Trinkwasserinstallation`, 18-letter continuation cap); short aliases
  stay strict (`gas` ≠ `gasket`); `Deutschland` is excluded as a proper
  noun for the `deutsch` alias.
- **I7 binary-credential semantics**: claim-quality windows are clipped to
  the sentence containing the hit (`Driving licence class B.` no longer
  inherits `qualified_low` from `Spanish (basic).` on the reflowed line
  above), and requirements may declare `claim_quality_exempt: true` — a
  verbatim credential hit is evidence regardless of surrounding claim
  context (a reviewer tuned override still wins). Set on the plumber
  profile's `class B driving licence` requirement.
- **I9 must-have gate** is verdict-based: a must-have passes only on
  verdict `met` (evidence ≥ 0.6, level ≥ good). Partial evidence (0.4-0.6)
  — e.g. a disclaimer that merely names the missing qualification — no
  longer clears the gate; the 40/100 anti-keyword-stuffing cap is unchanged.
- **I10 file hygiene** (`attune-data/casestudy-trades/expert/`): the
  committed expert ranking file was restored (it had been overwritten with
  comparison output; totals recovered from the frozen verification table,
  restoration note inside) and `trades_comparison.py` now fails fast with an
  operator-readable message if the input file is overwritten again.
- **I11 layered-kernel verifier** (`scripts/kernel_results_diff.py`, found
  while re-verifying): the cross-tier allowlist predates the spine block.
  `$.spine` is provenance (native-tier only, degrades on WASM by design)
  and, once F1 is active, the raw `pass1_sha256` legitimately differs
  across tiers (native-only `content_tag` annotations + spine-only review
  items). The cross-tier gate now compares a spine-normalized scoring view;
  `verify-layered-kernel.sh` is green again.
- **I6** (aliases amplified overmatch) needed no separate change: it was a
  consequence of I1/I3 and is re-measured below.

### Changed

- `review_queue` may contain the new non-blocking kind `mixed_document`
  (single file classifies as BOTH cv and cover above the 0.5 prior — likely
  a combined letter+CV packet); `content_tag` may carry `mixed_hint`.
- Career-switcher aspiration cues extended (`open to retraining into X`,
  `Umschulung`, `Umqualifizierung`); German HIGHPROF cues added
  (`festangestellt`, `taeglich`, `beruflich`, ...).
- `ENGINE_VERSION` 1.3.1 -> 1.3.2.

### Verified

- Plumber/SHK corpus, same salt and frozen corpus: determinism PASS,
  235/235 pins replay `exact`, cross-tier ranking + overalls byte-identical,
  calibration error 0.041 (12 sign-offs), F1 accuracy 22/22 unchanged.
  Negative/positive name-level controls all behave as designed: the
  electrician (no plumbing) and the negative control hold the last two
  ranks; trade-strong candidates hold the top.
- Expert-vs-tool agreement (committed-before-run protocol): Spearman 0.448
  -> 0.65 on the plumber corpus and 0.434 -> 0.769 on the trades corpus.
  The remaining plumber divergence is structural (the hard must-have cap
  cannot express the expert rubric's experience-vs-qualification trade-off)
  and is documented, not tuned away.
- QA gates: `kernel_ab_battery` 39/39, `verify_spine_features` 13/13,
  `smoke_test` 54/54, `verify-layered-kernel` PASS, university corpus
  re-run green.

## [1.3.1] - 2026-11-11

### Changed

- `VALUES_TOKEN_SYNONYMS` (E1 multilingual values fold) extended with
  academic-context German vocabulary (`wissenschaftliche Integritaet`,
  `offene Wissenschaft`, `akademische Exzellenz`, `interdisziplinaere
  Zusammenarbeit`, `verantwortungsvolle Betreuung und Lehre`, ...). Found by
  screening a bilingual (DE/EN) university doctoral-hiring corpus: German
  applications scored 0.0 values_fit against an English values text because
  the fold table only carried the demo corpus's industry vocabulary.
- `ENGINE_VERSION` 1.3.0 -> 1.3.1.

### Fixed

- `make_report.py`: the batch-report cover title and candidate-dossier title
  had no explicit `leading`, so any position name long enough to wrap to a
  second line drew its lines on top of each other and collided with the
  subtitle (the short demo titles never exposed it). Found by the university
  case study ("Doctoral Researcher (PhD) in Machine Learning"); leading is
  now set explicitly on the display styles (38/18/27 pt).

### Verified

- University case study (`attune-data/casestudy-uni/`,
  `verification/case_study_university.txt`): 12 applicants / 22 documents,
  planted mistags, decoy filenames and a mixed letter+CV PDF. Spine F1
  content classification 21/21 against ground truth; 4/4 confident
  filename/content disagreements flagged; 100% of pins replay `exact`;
  determinism holds; WASM tier ranks identically with the spine recorded
  `unavailable`. 45-check QA gate stays green after the fold change
  (demo corpus is English and unaffected by the added folds).

## [1.3.0] - 2026-11-11

### Added

- **Spine feature layer** (`docs/SPINE-FEATURES.md`): Job Attune now uses
  the integration spine of the vendored omnidecide-c 2.0.0 kernel
  (`odk_spine.h`) — capabilities the 1.x kernel did not have. Native tier
  only, gated by `$ATTUNE_SPINE` (default `auto`, or `off`); the WASM
  fallback tier records a machine-readable unavailability reason and runs
  exactly as in 1.2.0. New `attune-engine/spine_kernel.py` (ctypes spine
  bridge), new `attune-engine/data/spine_schemes.json` (the document-role
  schemes as DATA, registered through the kernel's extension API):
  - **Content tag verification (F1)** — every readable document's
    filename-derived role is cross-checked against its content by the
    deterministic Tier A classifier (`odk_spine_classify`). Results carry a
    `content_tag` annotation per file; a confident disagreement raises a
    non-blocking `tag_conflict` review item for the human queue — the
    pipeline never re-tags on its own.
  - **Decision pins + replay audit (F6)** — every kernel evaluation of the
    first pipeline pass is pinned via `odk_spine_pin` (exact request bytes,
    decision, confidence, kernel version, schema fingerprint, registered
    customizations) into `<run-dir>/spine_pins.jsonl`. New
    `scripts/replay_audit.py` re-derives every pinned decision on a fresh
    kernel via `odk_spine_evaluate_request` and must report `exact`.
  - **Calibration loop (F4)** — new `scripts/calibrate_report.py` turns
    human sign-offs (`review_decisions.jsonl`) into decision+outcome
    observation pairs and computes the live confidence-vs-agreement
    calibration report (`odk_spine_calibrate`, ten bins) — the
    deployment-level counterpart of the frozen floors contract.
- New `scripts/verify_spine_features.py` + release evidence
  `verification/spine_features.txt` (13 checks: pins + replay audit,
  spine-on/off scoring identity, WASM degradation, mis-tag fixture,
  calibration loop).

### Changed

- `attune-engine/ckernel_native.py`: optional decision-pin hook — each
  evaluate method now also builds the exact request document
  (`{primitive, instruction, options?, context, top_k?}`) and, when a
  recorder is attached (pinned pass only), hands it to the spine; with no
  recorder the bridge behaves exactly as before.
- `ENGINE_VERSION` 1.2.0 -> 1.3.0; `results.json` gains the `spine`
  provenance block (status, schema fingerprint, counters, pins file hash),
  written outside the hashed pipeline payload.

### Verified

- 13/13 spine checks: **125/125 pins replay `exact`** (all six primitives)
  on a fresh kernel; canonical scoring payloads byte-identical between
  spine-on and spine-off runs (the spine never changes a score); forced
  WASM run ranks identically to native; the 45-check QA gate stays
  **45 green / 0 amber / 0 red**.

## [1.2.0] - 2026-11-11

### Added

- **Layered decision kernel** (`docs/LAYERED-KERNEL.md`):
  `attune-engine/ckernel.py` is now a resolver that keeps the
  `import ckernel` seam intact while choosing between two interchangeable
  tiers of the same omnidecide-c 2.0.0 engine:
  - **Native tier** (default, full speed): the ctypes bridge, now at
    `attune-engine/ckernel_native.py`, loading
    `vendor/omnidecide-c/build/libomnidecide.so` (+ `.dylib` / `.dll`);
    one-time build via the new `scripts/build-kernel.sh`.
  - **WASM fallback tier**: new `attune-engine/wasm_kernel.py` running the
    vendored official omnidecide-wasm dist
    (`vendor/omnidecide-wasm/dist/omnidecide.wasm`, kernel 2.0.0 snapshot,
    Emscripten 7.0.0) through `wasmtime` - byte-identical decisions with no
    C toolchain anywhere. Selected automatically only when no native
    library can be loaded; `ATTUNE_KERNEL=native` pins the fast path and
    fails loudly, `ATTUNE_KERNEL=wasm` pins portable mode.
  - Provenance in every run log: one stderr line records backend, kernel
    id, library/module, runtime API level (odk_spine_* presence proves a
    2.x binary) and the fallback reason.
- Release verification bundle `verification/`: tier-vs-tier A/B battery
  (39 cases: all six primitives, payloads + error paths, EN/DE/ZH,
  13.7k-char contexts), full-engine cross-tier replay with allowlisted
  results diff, and an 8-thread concurrency probe.
- Dockerfile fullstack image now also carries the WASM fallback tier
  (wasmtime wheel + vendored dist) next to the baked native kernel.

### Changed

- Vendored omnidecide-c upgraded **1.0.0 -> 2.0.0** (upstream keeps the
  full 1.x C API and replays 1.x decisions byte-identically - see
  `vendor/omnidecide-c/docs/UPGRADE-2.0.md`); the kernel build line now
  compiles the odk-core/odk-brain/odk-spine source layout.
- `ENGINE_VERSION` 1.0.0 -> 1.2.0; standalone-packager manifest gate
  updated to `omnidecide-c 2.0.0`.

## [Unreleased]

### Added

- `npx fallow` is now a **required CI gate**, and every other language in
  the tree has a fallow-equivalent analyzer stack behind the same gate:
  new workflow `.github/workflows/codebase-intel.yml` (jobs `fallow`,
  `python-intel`, `c-intel`, read-only permissions, plus a weekly schedule
  so `pip-audit` catches newly published CVEs):
  - **JavaScript** — `npx fallow@3.38.1` (version-pinned):
    `dead-code`, `dupes` and `architecture` run as hard gates (`--ci` =
    SARIF + `--fail-on-issues`); `health` runs as a ratchet against the
    committed baseline `.codebase-intel/fallow-health-baseline.json`
    (`--fail-on-issues --fail-on-stale-baseline`): a new over-threshold
    function fails the build, and fixing one requires locking the win in
    via `fallow baselines prune`. SARIF reports are attached as workflow
    artifacts and a rendered summary lands in `$GITHUB_STEP_SUMMARY`.
  - **Python** — `scripts/codebase_intel.py python` (19 checks total with
    the C side): `ruff` (curated rule set in the new `ruff.toml`: E4/E7/E9,
    F, I, RUF059, RUF100 — unused imports/variables, undefined names,
    unused unpacking targets, stale `# noqa` directives, import order),
    `vulture` dead code (whitelist for framework hooks in
    `.codebase-intel/vulture-whitelist.py`), `pylint duplicate-code`
    (≥10 similar lines) and `pip-audit` CVEs as hard gates; `lizard` CCN
    bands as a ratchet against `.codebase-intel/ratchet-baselines.json`.
  - **C kernel** — `scripts/codebase_intel.py c`: `cppcheck` 2.17.1
    (pinned .deb; two documented exceptions in
    `.codebase-intel/cppcheck-suppressions.txt`) and `flawfinder`
    (level-5) as hard gates; cppcheck style count, flawfinder level-4
    count, `lizard` CCN bands and `jscpd` clone counts as ratchets.
  - Ratchet contract mirrors fallow's shrink-only semantics: growth
    fails, and under `CODEBASE_INTEL_STRICT=1` (set in CI) an improvement
    also fails until the baseline is re-saved with `--update-baseline`.
    Tool versions are pinned to the ones the baselines were measured
    with. Full capability map and local-run instructions:
    **docs/CODEBASE-INTEL.md** (new), referenced from README and
    docs/DEVELOPMENT.md (QA pipeline #7; #6 updated from "dev-only").
- Repo hygiene: `scripts/tmp_pycheck/` (QA scratch output regenerated by
  every release-gate run) is no longer committed — untracked and
  gitignored.

### Fixed

- Real dead code the new Python gates surfaced, all verified against the
  full QA suite afterwards: `band_color()` in `make_report.py` (defined,
  never called) deleted; the loopback-guard constant `CLIENT_HEADER` in
  `server.py` is now actually used by the header check instead of a
  string literal; five unused locals and eight unused unpacking targets
  across the engine, server and QA scripts removed; six stale `# noqa`
  directives dropped (their reasons survive as plain comments); a dead
  comprehension in the release gate; two unsorted import blocks.

### Changed

- Frontend cleanup pass driven by [fallow](https://fallow.tools) (TS/JS
  codebase intelligence, run per its docs as a one-off audit; the shipped
  app still needs no Node.js — see the CI wiring above for how fallow
  itself now runs). Health score moved from
  84 B to **90 A**, dead exports 12.8% → 0%, dead files → 0%, code
  duplication 0.3% → 0%, maintainability index 85.6 → 88.2:
  - Removed the `export` keyword from six module-internal helpers that had
    no external consumers (`API_CLIENT_HEADER`, `emptyCategories`, `TEAL`,
    `refreshAllGovernance`, `statCards`, plus `fmt1` which was imported by
    the candidate dialog but never called and is now deleted outright).
  - `run-monitor.js` no longer carries a byte-identical local copy of the
    DOM `append()` helper; it imports it from `ui.js` like every other
    view (the one clone group fallow found).
  - Split the two complexity hotspots into per-section builders with zero
    behavior change: `openCandidateDialog` (cyclomatic 52, 258 lines,
    CRAP 2756) is now eight focused functions (`overallAssessment`,
    `profileCard`, `interviewPrompts`, `skillsInventory`,
    `categoryBreakdown`, `requirementEvidence`, `decisionAndFiles`,
    `signOffBox`), and `PositionReport` (cyclomatic 34, 214 lines) is now
    six section builders assembled through the null-skipping `append()`.
    Verified **DOM-identical**: a Playwright harness snapshotted the
    overview / position report / ranking / candidate dialog / candidates
    views before and after; after masking run-dependent values (run ids,
    salted candidate refs, timestamps) and the engine's two ref-sorted
    orderings, all five snapshots are byte-for-byte equal. The remaining
    fallow deduction is "unit size" of the data-driven view builders,
    accepted as-is.
- Added `.fallowrc.json` declaring the three entry points (`web/js/app.js`
  plus the root-absolute `index.html` / `app.css` asset links fallow's
  HTML plugin cannot resolve on its own), and documented the check as QA
  pipeline #6 in docs/DEVELOPMENT.md (now a CI gate, see above).
  Re-verified after the changes:
  45-check release gate, 54-check smoke test, 23-assertion e2e walk and
  the 22-assertion design check all pass.

## [1.1.0] - 2026-11-01

### Added

- Docker images via a multi-stage, multi-target `Dockerfile` (see the new
  SETUP.md Docker section):
  - `docker build --target engine -t job-attune-engine .` — QA/dev image for
    the Python engine (243 MB). The repo is bind-mounted at `/app` at run
    time and the default CMD is the full 45-check QA gate, which passes
    45 green / 0 amber / 0 red inside the container. The C kernel is compiled
    once at image-build time with the repo's flags (`-std=c11
    -ffp-contract=off`) and exposed through `OMNIDECIDE_C_LIB`, so results
    stay bit-identical to the host build (determinism pass1 = pass2).
  - `docker build -t job-attune-full .` (default target) — full-stack image:
    the stdlib-only Python server (`server.py` + `web/`, no Node.js, no
    build stage) plus the Python engine, compiled kernel, demo candidates
    and profile templates baked in. Start
    with `docker run -d -p 127.0.0.1:3000:3000 job-attune-full`. Smoke-tested
    end-to-end through the app's own API: template load, folder scan
    (6 candidates), a screening run that finished in 0.4 s (6 screened /
    2 shortlisted), and 7 PDF exports (17-page batch report + 6 candidate
    dossiers) validated with pypdf and downloaded over HTTP.
- `scripts/smoke_test.py` — new 54-check fast health check (~10 s,
  self-contained): boots its own `server.py` on a scratch port, verifies
  every static asset and path-traversal containment, the loopback guard
  (403 without `X-Attune-Client`, 403 on cross-site), all 13 API routes
  with their error shapes, a full engine run + PDF export on every shipped
  corpus (sample-6, trades14, logistics14) with throughput numbers, and a
  Chromium pass (scan -> profile -> run -> results) with zero JS errors.
  Modes: `--quick` (static + guard + API), `--api-only` (no browser),
  `--keep` (retain the run dirs it created). Complements the existing
  45-check release gate and the 23-assertion `e2e_check.py` UI walk;
  documented in README (quality gates), SETUP.md and docs/DEVELOPMENT.md
  (QA pipeline #4 + release checklist).
- The fullstack image bakes the kernel version header at
  `/app/vendor/omnidecide-c/include/omnidecide.h` (copied from the exact
  `kernel-build` source tree), so `ckernel.py` reports the version of the
  actually-baked library (`omnidecide-c 1.0.0`) in run manifests instead of
  `unknown`.
- Standalone end-user distributions for Windows, macOS and Linux, built by
  the new Release workflow (`.github/workflows/release.yml`) and by
  `scripts/standalone/package.sh` - the same script CI calls, so local
  builds are identical. Every archive bundles the compiled C11 kernel for
  that platform, the vanilla web app (stdlib-only Python server + static
  frontend), the Python engine with the demo corpus and profile templates,
  and a CPython 3.12 runtime with reportlab/pypdf preinstalled (no Node.js
  at all) - unpack, run
  `start.bat` / `start.command` / `./start.sh`, open
  http://127.0.0.1:3000, no prerequisites (see START-HERE.txt inside each
  archive). Packaging gates itself per platform before archiving: the
  kernel is compiled with the bit-identical flags, the bundled Python must
  run the real engine against the demo corpus (manifest must record
  `omnidecide-c 1.0.0`), and on Linux the finished archive is extracted and
  must answer an API request through the shipped launcher. Tag builds
  (`v*`) attach the archives plus sha256 checksums to the GitHub Release;
  manual runs upload them as workflow artifacts. Verified end-to-end on
  Linux: boot, scan, full screening run, and PDF export all driven through
  the packaged app's own HTTP API.


### Changed

- Moved the vendored C11 kernel from `download/omnidecide-c/` to
  `vendor/omnidecide-c/` — the old path was a leftover from the original
  machine layout, not a deliberate location. Every reference moved with it
  (README, SETUP, docs, NOTICE, Dockerfile, CI workflow, `.gitignore`,
  `.dockerignore`, and the engine's default `OMNIDECIDE_C_LIB` resolution in
  `attune-engine/ckernel.py`). Existing checkouts need one kernel rebuild at
  the new path:

      cd vendor/omnidecide-c
      mkdir -p build
      cc -std=c11 -ffp-contract=off -O2 -fPIC -shared -Iinclude -Isrc \
         src/*.c -lm -o build/libomnidecide.so

- `next.config.ts` now pins `outputFileTracingRoot` to the project
  directory, making the standalone build layout deterministic
  (`.next/standalone/server.js`) even when the repo is checked out inside
  a parent directory that looks like a workspace root — without the pin,
  Next 16 can nest the output under a workspace-name folder and the
  standalone/Docker packaging assumptions break.

- **The UI stack is now pure HTML, CSS and vanilla JavaScript - Next.js,
  React, Tailwind, Radix UI, Recharts, TypeScript, Bun/Node and the whole
  npm dependency tree are gone.** One stdlib-only Python file
  (`server.py`) now serves the static frontend from `web/` and implements
  the exact same guarded `/api` contract the Next.js routes provided
  (browse, scan, run, run/status, run/results, report, audit, template),
  including the loopback guard: every `/api` request must carry
  `X-Attune-Client` and cross-site browser requests are rejected. What the
  port keeps: the four-step wizard, all six result tabs, the candidate
  dossier dialog, review sign-offs, PDF export and template management.
  Radix components were re-implemented by hand (focus-trapped dialogs,
  keyboard-navigable tabs, collapsibles, switches, sliders, native
  selects); the overview charts are hand-drawn SVG with hover tooltips and
  resize handling; the icon set is generated from lucide-static 0.525.0
  (ISC - the version lucide-react used) by the new
  `scripts/fetch_icons.py`. Verified end-to-end in Chromium via
  Playwright: scan -> profile -> run -> all tabs -> candidate dialog ->
  review decision -> PDF download -> reset, with zero console errors.
- `Dockerfile`: the `fullstack` target no longer needs a Bun/Node build
  stage or a Node runtime - it runs `python3 server.py` directly (smaller,
  faster image, one runtime to patch).
- Standalone bundles now ship a single CPython runtime (no Node.js),
  launched by the updated `start.sh` / `start.bat` / `start.command`;
  `scripts/standalone/package.sh` stages `server.py` + `web/` instead of
  the Next.js standalone build.
- **Restyled the UI in the Agenflow visual language** (no paid assets - all
  additions are free/open): warm cream paper background with soft mint and
  periwinkle radial washes, deep-ink borders and text, forest-green header
  logo tile and footer, orange pill buttons with uppercase display type,
  rotated sticker badges, pastel band palettes (mint / lavender / gold /
  raspberry) and 18px card radii. Typography: Boldonse (display, OFL),
  DM Sans (body, OFL) and Playfair Display italic (labels, OFL) - all
  self-hosted under `web/fonts/` (~150 KB, with the OFL 1.1 text) so the
  app stays fully functional offline with zero external requests. Charts,
  rank medals and the logo were recolored to the same palette; the CSS
  class contract is unchanged (view JS untouched except three color
  constants). NOTICE now carries the font attributions. Verified by the
  new `scripts/design_check.py` (22 assertions: fonts loaded from
  `web/fonts/`, zero external hosts, cream/ink/orange/forest palette
  active, pill shapes, no overflow) plus the full 54-check smoke test and
  the 23-check e2e walk - all green with zero JS errors; doc screenshots
  regenerated from the styled app.
- Docs updated across the board (README, SETUP, ARCHITECTURE, API,
  DEVELOPMENT, ENGINE-CLI, START-HERE) to describe the vanilla stack.


### Fixed

- `docker build -t job-attune-full .` failed on a fresh clone: the UI build
  stage COPYed `next-env.d.ts`, a generated, gitignored file that does not
  exist after a clean checkout (`next build` regenerates it). The file is no
  longer copied and is excluded from the build context, so fresh clones and
  warmed-up developer trees build the image identically. (The engine-target
  image was unaffected; CI never built the fullstack target, which is why
  this slipped through.)
- Removed `typescript.ignoreBuildErrors` from `next.config.ts`: it silently
  disabled type checking during `next build`, which is the only type gate on
  the Docker build path (CI runs a separate `tsc --noEmit`; the image does
  not). Type errors now fail the build everywhere — the tree passes with
  zero errors, verified by the full gate suite below.
- Fixed a regression from the kernel move in this same batch:
  `attune-engine/ckernel.py` assembled its default kernel tree from two
  separate path segments (`"download" / "omnidecide-c"`), which the
  reference sweep missed — without `OMNIDECIDE_C_LIB` set the engine could
  not find the kernel or read its version, so the documented quickstart
  broke. Default resolution and the version header now point at
  `vendor/omnidecide-c/`; the 45-check gate passes with no environment
  overrides at all (the way the documented UI flow runs).
- The kernel loader is now platform-aware: without `OMNIDECIDE_C_LIB` it
  looks for `omnidecide.dll` on Windows and `libomnidecide.dylib` on macOS
  instead of only `libomnidecide.so`, matching what the standalone packager
  builds on those platforms.
- `scripts/attune_app/js_check_pipelines.py` no longer writes its default
  report into a stray `download/` folder; it lands in
  `local-js-checks-report.md` at the repo root (ignored via `/local-*`).


### Removed

- Deleted the unused Prisma scaffold: the four `db:*` scripts,
  `@prisma/client` + `prisma` dev/runtime packages, `src/lib/db.ts` and
  `prisma/` — Job Attune stores all data on the filesystem and never
  imported the database client.
- Deleted 30 unused shadcn/ui components from `src/components/ui/`
  (accordion, alert-dialog, aspect-ratio, avatar, breadcrumb, calendar,
  carousel, chart, checkbox, command, context-menu, drawer,
  dropdown-menu, form, hover-card, input-otp, menubar, navigation-menu,
  pagination, popover, radio-group, resizable, sheet, sidebar, skeleton,
  sonner, table, toggle, toggle-group, tooltip) plus the orphaned
  `src/hooks/use-mobile.ts`. The 18 components reachable from the app
  remain.
- Slimmed npm dependencies: runtime 47 → 20, devDependencies: `bun-types`
  replaced by the canonical `@types/node` (needed for the Node API types
  the API routes and `src/lib/attune-server.ts` rely on). Dropped runtime
  deps: 15 radix packages, `cmdk`, `embla-carousel-react`, `input-otp`,
  `next-intl`, `next-themes`, `react-day-picker`, `react-hook-form`,
  `react-resizable-panels`, `sonner` and `vaul`. `bun.lock` regenerated.
  Scripts are unchanged (`dev` / `build` / `start` / `lint`).


- `src/` (Next.js app), `package.json`, `bun.lock`, `next.config.ts`,
  `tsconfig.json`, `postcss.config.mjs`, `components.json`,
  `eslint.config.mjs` and `scripts/attune_app/js_check_pipelines.py` (its
  Fallow-based checks targeted the removed `src/` tree; the 45-check
  Python QA gate is unaffected and still the release gate).

## [1.0.0] - 2026-10-28

**Initial public release.** First stable, production-ready version —
published by Tamer Osman (https://github.com/tamer4osman) under the
Apache License 2.0 (see LICENSE and NOTICE). v1.0.0 supersedes all
pre-release development builds; version numbering starts here.

Job Attune ("Hire for aptitude") is GDPR-safe, local-first resume screening: a Next.js UI
driving a deterministic Python scoring engine on the omnidecide-c 1.0.0
C11 decision kernel, turning a folder of applicant PDFs into a ranked,
fully auditable shortlist. This release ships the feature set proven
stable across the full internal QA programme (45-check gate, kernel A/B
battery, bench harness, ten-language battery).

### Engine & kernel

- Deterministic, stdlib-only scoring pipeline over the vendored
  **omnidecide-c 1.0.0** C11 kernel (`vendor/omnidecide-c/`) through the
  ctypes bridge `attune-engine/ckernel.py` — the only kernel. All six
  decision primitives (extract, score, rank, compare, choice, noul) are
  load-bearing, gated by the calibrated confidence-floors contract
  (`attune-engine/floors.py` + `data/floors_v1.json`, floors v1.0).
- Two-pass determinism enforced on every run (canonical sha256 of both
  passes must match); runs are byte-reproducible (pinned reference year,
  canonical JSON, invariant ReportLab configuration).
- Escalation-first governance: low-confidence extraction, unreadable
  documents and rank conflicts land in a human review queue (append-only
  JSONL with sign-off); PII is redacted and candidates pseudonymised in
  all outputs.
- Tunable aggregation forms (`uniform` / `req_share` / `global` plus the
  zero-evidence weight factor) as opt-in profile keys with fail-fast
  validation and per-run provenance blocks.

### Multilingual

- **Unicode text mode is the kernel default** — scoring-identical on
  pure-ASCII input (verified byte-for-byte on all shipped corpora) and
  required for non-Latin scripts to contribute kernel evidence. Documented
  rollback lever: `ATTUNE_TEXT_MODE=ascii` restores the byte-frozen
  ASCII behavior.
- Ten opt-in language packs (`und en zh hi es ar fr bn pt id ur auto`)
  via `ATTUNE_LANGUAGE`; every run manifest records the effective
  `kernel_text_mode` / `kernel_language` for auditability.
- Measured on the ten-language reference corpus: Spearman rho
  0.833–0.929 (mean 0.888), rank-1 candidate correct in all ten languages,
  zero fabricated evidence (all snippets verbatim-verified) — no
  non-English penalty versus the English baseline.

### Accuracy evidence

- Candidate-blind bench vs Boolean ATS / TF-IDF / BM25 on frozen
  human-referenced corpora (see `bench/README.md`): corpus20 rho **0.931**,
  real40 **0.640**, logistics14 **0.802**, trades14 **0.877**; all twelve
  recorded cells deterministic across double passes.
- Kernel scoring-neutrality proven by a 36-case kernel A/B battery plus
  full-engine leaf-identical replay; the pre-release migration evidence is
  preserved as a historical record in `docs/VERIFICATION-1.8.0.md`.
- 45-check release gate (`scripts/check_python_side.py`): static analysis,
  floors contract, two-pass determinism, enrichment and redaction probes,
  bench baselines, 7-PDF export validation.

### App & tooling

- Next.js 16 UI (ranking board, candidate dossiers, governance view, run
  monitor) plus 7 local HTTP API endpoints, loopback-bound with
  CSRF/rebinding protection; engine-only CLI mode for scripted, air-gapped
  operation.
- Folder paths resolve against the project root in every deployment mode
  (`next dev` and the standalone production server alike), matching the
  documented contract for relative paths.
- PDF reporter: batch position report + per-candidate dossiers with a
  sha256 manifest; deterministic content (no wall-clock text).
- Demo corpus (6 candidates including an unreadable image-only scan) with
  its generator; JS/TS static-health pipelines (Fallow).
- README redesigned as the project's front door: branded hero with badge
  row, screenshot gallery from the real demo-corpus run, ATS/LLM comparison
  matrix, feature grid, receipts table (claim - proof - verify command),
  FAQ; new tuning-fork logo mark (`public/logo.svg`, also the favicon).

### Licensing

- Job Attune is licensed under the **Apache License 2.0** (LICENSE,
  NOTICE; SPDX headers on all first-party files). Author, owner and
  copyright holder: Tamer Osman (https://github.com/tamer4osman).
- The embedded omnidecide-c kernel is Apache-2.0 as well
  (`vendor/omnidecide-c/LICENSE`); its bundled Unicode Character Database
  data carries the Unicode License v3
  (`vendor/omnidecide-c/THIRD_PARTY_NOTICES.md`).
