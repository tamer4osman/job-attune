<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->

<p align="center">
  <img src="web/logo.svg" width="132" alt="Job Attune logo" />
</p>

<h1 align="center">Job Attune</h1>

<h3 align="center">Hire for aptitude.</h3>

<p align="center">
  <strong>GDPR-safe, local-first resume screening.</strong><br/>
  A deterministic engine that turns a folder of applicant PDFs into a ranked,
  fully auditable shortlist — with pseudonymous reports and a reproducible
  decision manifest for every run.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache_2.0-334155?style=for-the-badge" alt="License: Apache-2.0"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Release-v1.0.1-059669?style=for-the-badge" alt="Release v1.0.1"></a>
  <a href="vendor/omnidecide-c/README.md"><img src="https://img.shields.io/badge/Kernel-omnidecide--c_2.0.0-334155?style=for-the-badge" alt="Kernel: omnidecide-c 2.0.0"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/Languages-10_packs-059669?style=for-the-badge" alt="10 language packs"></a>
  <br/>
  <a href="docs/VERIFICATION-1.8.0.md"><img src="https://img.shields.io/badge/Determinism-verified-16a34a?style=for-the-badge" alt="Determinism: verified"></a>
  <a href="docs/ARCHITECTURE.md"><img src="https://img.shields.io/badge/Data-local--only-059669?style=for-the-badge" alt="Data: local-only"></a>
  <a href="scripts/check_python_side.py"><img src="https://img.shields.io/badge/QA-45_checks_green-16a34a?style=for-the-badge" alt="QA: 45 checks green"></a>
  <a href="docs/CODEBASE-INTEL.md"><img src="https://img.shields.io/badge/Codebase_intel-3_languages-334155?style=for-the-badge" alt="Codebase intelligence: 3 languages"></a>
  <a href="docs/ENGINE-CLI.md"><img src="https://img.shields.io/badge/Engine-stdlib--only-334155?style=for-the-badge" alt="Engine: stdlib-only"></a>
</p>

<p align="center"><sub>
  <a href="#why-job-attune">Why</a> ·
  <a href="#screenshots">Screenshots</a> ·
  <a href="#features">Features</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#measured-accuracy">Accuracy</a> ·
  <a href="#receipts-not-promises">Receipts</a> ·
  <a href="#quickstart">Quickstart</a> ·
  <a href="#documentation">Docs</a> ·
  <a href="#faq">FAQ</a> ·
  <a href="#license">License</a>
</sub></p>

<p align="center">
  <img src="docs/screenshots/overview.png" width="92%" alt="Job Attune overview screen: cohort statistics, score histogram and category averages from a real run of the shipped demo corpus" />
</p>

<p align="center"><sub>No cloud · No accounts · No API keys · No model calls — one command, then it runs on your machine.</sub></p>

---

## Why Job Attune?

*at·tune (v.) — bring into accord; bring into harmony.*

Resume screening software is broken in two familiar ways. Keyword ATS
filters punish aptitude: one missing keyword vetoes a strong candidate, and
the best person for the role never reaches a human. Cloud "AI" screeners fix
the rigidity but introduce a worse trade: opaque scores you cannot explain in
an audit, different answers for the same CV, and candidate files leaving your
machine for someone else's model.

Job Attune is the third way. **Deterministic math instead of keywords; evidence
instead of vibes; humans keep the last word.** The same folder of CVs produces
the same ranking every single time — byte for byte — and every score carries
the CV evidence that produced it. The engine never auto-rejects anything:
whatever it cannot read confidently escalates to a human review queue. And
there is no cloud, no account and no API key anywhere in the pipeline: the
decision kernel is a pure C11 computation library with no network code, so
there is no data-egress path to audit away.

| What matters in screening | Keyword ATS | LLM screener | Job Attune |
|---|:---:|:---:|:---:|
| Same inputs → same ranking, every time | ❌ | ❌ | ✅ |
| Every score backed by quoted CV evidence | ❌ | ⚠️ unverifiable | ✅ |
| Candidate files stay on your machine | ⚠️ varies | ❌ usually cloud | ✅ always |
| Decisions you can defend in an audit | ❌ | ⚠️ | ✅ |
| Runs air-gapped — no keys, no metering | ⚠️ rare | ❌ | ✅ |
| Unclear cases escalate to a human | ⚠️ | ⚠️ | ✅ always |

## Screenshots

All screenshots come from a **real run of the shipped demo corpus**
(`attune-sample-data/candidates` — 6 candidates / 10 PDFs, ranked in 0.8 s)
against the `example-senior-data-engineer` job profile. This is the exact run
the 45-check QA gate replays on every release, not a mockup.

| | |
|---|---|
| ![Job Attune overview](docs/screenshots/overview.png) | ![Job Attune position report](docs/screenshots/position-report.png) |
| *Overview: cohort statistics, score histogram, category averages* | *Position report: verdict, head-to-head, differentiators* |
| ![Job Attune ranking](docs/screenshots/ranking.png) | ![Job Attune candidate dossier](docs/screenshots/candidate-detail.png) |
| *Ranking board: banded scores with must-have flags* | *Candidate dossier: evidence-backed requirements and profile card* |

![Job Attune review queue](docs/screenshots/review.png)

*Review queue: low-confidence extractions, unreadable documents and rank
conflicts wait for human sign-off — the engine never auto-rejects.*

## Features

| | |
|---|---|
| **Deterministic replay** — identical inputs produce byte-identical results *and* PDFs; a two-pass sha256 equality check runs on every single run, not just in tests. | **Evidence-first scoring** — every requirement score carries the CV evidence that produced it, so a ranking is never a black box. |
| **Calibrated confidence floors** — all six decision primitives (extract, score, rank, compare, choice, noul) stay load-bearing behind the floors contract (floors v1.0), tuned on pre-registered corpora. | **Escalation-first review queue** — low-confidence extractions, unreadable documents and rank conflicts land in an append-only queue with human sign-off; the engine never auto-rejects. |
| **Pseudonymous by default** — candidates are sha256 refs in every output; PII-redaction probes run on every regression pass. | **Local-only by design** — the UI binds to `127.0.0.1`, its APIs are CSRF/rebinding-guarded, and the kernel contains no network code — there is no egress path. |
| **Ten language packs** — `und en zh hi es ar fr bn pt id ur`, opt-in via `ATTUNE_LANGUAGE`; every run manifest records the effective language for auditability. | **Reproducible PDF reports** — batch report + per-candidate dossiers with a sha256 manifest, pinned reference year, canonical JSON. |
| **Air-gap engine-only mode** — no UI needed: stdlib-only Python over the vendored C11 kernel runs anywhere Python does; the WASM fallback tier (`pip install wasmtime`) runs the same kernel with no C build. | **Tunable, never silent** — aggregation forms (`uniform` / `req_share` / `global`) and the zero-evidence weight are opt-in profile keys with fail-fast validation; every run records its exact math in a provenance block. |
| **Spine features (kernel 2.0.0)** — content-based CV/cover-tag verification flags mistagged documents to the human queue; `ATTUNE_SPINE=off` disables the layer, the WASM tier degrades cleanly ([docs/SPINE-FEATURES.md](docs/SPINE-FEATURES.md)). | **Replay-auditable decisions** — on the native tier every kernel evaluation is pinned (request bytes, decision, confidence) and re-derives as `exact` on a fresh kernel; human sign-offs calibrate into live confidence bins. |

## How it works

<p align="center">
  <img src="docs/diagrams/workflow.png" width="72%" alt="Job Attune workflow: scan and classify, score with evidence, escalate unclear cases, report and archive" />
</p>

The pipeline in four moves:

1. **Scan & classify.** Point Job Attune at a folder of applicant PDFs (one
   subfolder per candidate). Every document is tagged CV or cover letter
   (filename aliases, EN + DE), and raw text is never persisted.
2. **Score with evidence.** Extraction → evidence scoring → aggregation →
   ranking runs on the [omnidecide-c 2.0.0](vendor/omnidecide-c/) C11
   decision kernel behind a layered resolver - native ctypes tier first,
   WASM fallback tier when no native library can be loaded
   ([docs/LAYERED-KERNEL.md](docs/LAYERED-KERNEL.md)) - gated by the
   calibrated [floors contract](attune-engine/floors.py). Candidates are
   pseudonymous refs throughout.
3. **Escalate what is unclear.** The `noul` primitive routes low-confidence
   extractions, unreadable files and rank conflicts into the review queue
   instead of guessing — an audit-friendly definition of "I don't know."
4. **Report & archive.** A batch report, per-candidate dossiers and a
   `results.json` with a full provenance block land in the run directory; the
   manifest pins the engine, kernel and floors versions that produced them —
   and on the native tier every kernel decision is pinned for replay audit,
   each document's role tag is content-verified, and human sign-offs feed a
   live calibration report ([docs/SPINE-FEATURES.md](docs/SPINE-FEATURES.md)).

Component-level detail, data contracts, the redaction pipeline and the
security model live in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Measured accuracy

Spearman rho against **pre-registered, frozen human rankings**, recorded with
the candidate-blind harness under study salt `task32-study`. The harness itself
has been retired; the tables below are preserved as historical reference, and
the shipped case-study fixtures under [attune-data/](attune-data/) (frozen
corpora, expert rankings, preregistration hashes, reproduction commands) are
the current way to run the same protocol on a corpus you can inspect:

| System | corpus20 (synthetic) | real40 (authentic CVs) | logistics14 | trades14 |
|---|---|---|---|---|
| **Job Attune engine** | **0.931** | **0.640** | 0.802 | 0.877 |
| BM25 | 0.917 | 0.574 | 0.837 | 0.912 |
| TF-IDF | 0.848 | 0.444 | 0.802 | 0.939 |
| Boolean ATS (keyword veto) | 0.725 | 0.510 | 0.657 | 0.152 |

Honest reading: the engine leads every system on the real-CV corpora
(corpus20 +0.014..+0.206 rho, real40 +0.066..+0.196). On the synthetic
gate-heavy holdout cells the coverage-sum rubric favours veto-free TF-IDF/BM25
— reported openly, because hiring decisions should rest on the full picture.
All twelve recorded cells are deterministic across double passes.

The same rigor holds across languages: on the ten-language reference corpus
(`en zh hi es ar fr bn pt id ur`) the engine scores Spearman rho 0.833–0.929
(mean 0.888) and puts the rank-1 candidate first in all ten languages.

<p align="center">
  <img src="docs/diagrams/bench-spearman.png" width="82%" alt="Spearman rho benchmark chart: Job Attune engine vs BM25, TF-IDF and Boolean ATS across four corpora" />
</p>

## Receipts, not promises

Every claim above is a command or a document you can check — no trust
required.

| Claim | How it is proven | Verify it yourself |
|---|---|---|
| Identical inputs → byte-identical outputs | Two-pass sha256 equality enforced on every run; PDFs render through a pinned, invariant ReportLab config | `python3 scripts/check_python_side.py` (45 checks; exit 0 = release-ready) |
| Scoring is stable across releases | 3-case regression lock against the frozen reference scoring lineage | Protocol in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| The C11 kernel changes no scores | 36-case kernel A/B battery + full-engine leaf-identical replay | [docs/VERIFICATION-1.8.0.md](docs/VERIFICATION-1.8.0.md) |
| No PII leaks into outputs | PII-redaction probes over all enriched outputs on every regression run | Probe lines in the 45-check gate output |
| Benchmarks are candidate-blind & pre-registered | Frozen corpora, pinned human rankings, sha256 preregistration | [docs/GENERAL-RELIABILITY.md](docs/GENERAL-RELIABILITY.md) + [attune-data/](attune-data/) |
| Nothing phones home | The kernel is pure C11 computation — no sockets, no HTTP; the UI binds to `127.0.0.1` only | Read it: [vendor/omnidecide-c/](vendor/omnidecide-c/) |
| Every language ships behind static-analysis gates | `fallow` (JS), ruff/vulture/pylint/pip-audit/lizard (Python), cppcheck/flawfinder/lizard/jscpd (C) — hard gates plus shrink-only complexity ratchets, wired in `codebase-intel.yml` | [docs/CODEBASE-INTEL.md](docs/CODEBASE-INTEL.md) |
| Every decision is attributable | Each run manifest records engine, kernel and floors versions plus the aggregation provenance block | Open any run directory under `attune-data/runs/` |

Release discipline follows the same rule: scoring behaviour changes require a
green gate, a green regression lock (or a documented allowlist amendment) and
a CHANGELOG entry — engine and UI are tracked together under the engine
version, so historical runs stay attributable forever.

## Quickstart

**Prebuilt standalone** (nothing to install - recommended for end users):

Download the archive for your OS from
[Releases](https://github.com/tamer4osman/job-attune/releases)
(`job-attune-standalone-<platform>.zip` / `.tar.gz`), verify it against
the shipped `.sha256`, unpack, and run:

- **Windows** (10+, x64) — double-click `start.bat`
- **macOS** (12+, Apple Silicon) — double-click `start.command`
- **Linux** (glibc 2.28+, x64) — run `./start.sh`

Each bundle carries the compiled C11 kernel, the app, and its own CPython
3.12 runtime (with reportlab/pypdf preinstalled) — the unpacked archive runs
offline with no tooling on the machine.

**Install as an app** (PWA - the same UI as a standalone window, no extra
download): with Job Attune running, open `http://127.0.0.1:3000` and use the
browser's install action — Chrome/Edge: install icon in the address bar;
Safari: *File → Add to Dock*; Android/iOS: *Install app* / *Add to Home
Screen*. The app shell opens offline and instantly; screening always talks
to the live local server ([docs/PWA.md](docs/PWA.md)).

Prefer real installers? The **Desktop (Electron)** workflow packages
`.exe` / `.dmg` / `.AppImage` build artifacts around the same standalone
bundle ([electron/README.md](electron/README.md)).

**With the UI** (vanilla HTML/CSS/JS + stdlib Python server, no Node.js,
no build step):

```bash
pip install -r requirements.txt   # reportlab + pypdf (engine: stdlib only)
bash scripts/build-kernel.sh      # one-time native kernel build (full speed)
python3 server.py                 # -> http://127.0.0.1:3000
```

No C compiler on the machine? Skip the build and `pip install wasmtime`
instead — the engine then runs the vendored WASM fallback tier
automatically: byte-identical decisions with zero build, ≈ +10% per run
([docs/LAYERED-KERNEL.md](docs/LAYERED-KERNEL.md)).

Then: enter `attune-sample-data/candidates` in the folder picker, **Scan**,
confirm the CV / cover-letter tags, and **Start run**. PDF exports land in
`attune-data/runs/<run-id>/exports/`.

**With Docker** (no local Python setup):

```bash
docker build -t job-attune-full .                              # full stack + baked engine/templates
docker run -d -p 127.0.0.1:3000:3000 job-attune-full           # -> http://127.0.0.1:3000
docker build --target engine -t job-attune-engine .            # QA-gate / scripted engine image
```

The prebuilt stack bundles the compiled kernel, engine, demo corpus and
templates; run directories stay host-mounted
(`-v ./attune-data/runs:/app/attune-data/runs`). QA-gate container usage and
port overrides live in [SETUP.md](SETUP.md).

**Engine-only** (no UI, air-gap friendly — works anywhere Python does):

```bash
python3 attune-engine/engine.py \
  --folder attune-sample-data/candidates \
  --profile attune-data/templates/example-senior-data-engineer.json \
  --run-dir /tmp/my-run
```

The kernel tier resolves automatically: the native library if present, the
vendored WASM fallback otherwise (`pip install wasmtime`; pin with
`ATTUNE_KERNEL=native|wasm` — [docs/LAYERED-KERNEL.md](docs/LAYERED-KERNEL.md)).
On the native tier the spine features engage automatically (content tag
verification, decision pins — [docs/SPINE-FEATURES.md](docs/SPINE-FEATURES.md));
`ATTUNE_SPINE=off` turns them off.

The demo corpus (6 candidates, 10 PDFs, including an unreadable image-only
scan) is regenerated with
`python3 scripts/attune_app/make_samples.py`. The condensed setup card is
[SETUP.md](SETUP.md).

## Documentation

| Doc | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, run lifecycle, data contracts, redaction pipeline, security model, diagrams |
| [docs/LAYERED-KERNEL.md](docs/LAYERED-KERNEL.md) | The layered decision kernel: native tier, WASM fallback tier, `$ATTUNE_KERNEL` policy |
| [docs/SPINE-FEATURES.md](docs/SPINE-FEATURES.md) | Kernel 2.0.0 spine features: content tag verification, decision pins + replay audit, calibration loop, `$ATTUNE_SPINE` policy |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Developer guide: QA pipelines, regression lock, adding benchmark fixtures, release checklist |
| [docs/CODEBASE-INTEL.md](docs/CODEBASE-INTEL.md) | Codebase-intelligence gates: fallow + the Python/C analyzer stack, capability map, ratchet contract |
| [docs/MARKETING.md](docs/MARKETING.md) | Sales playbook: positioning, comparison matrix, statistics, workflows, objection handling |
| [docs/API.md](docs/API.md) | HTTP API reference (13 routes) incl. loopback-guard auth rules |
| [docs/PWA.md](docs/PWA.md) | The installable web app: manifest + service worker, offline shell vs. network-only `/api`, icons, update protocol |
| [electron/README.md](electron/README.md) | Desktop shell (Electron): architecture, local + CI packaging, unsigned-build caveats |
| [docs/ENGINE-CLI.md](docs/ENGINE-CLI.md) | Engine + reporter CLI reference, aggregation profile keys, run-directory contract |
| [attune-data/](attune-data/) | Case-study fixtures: frozen corpora, expert rankings, preregistration hashes and reproduction commands (plumber, trades, university) |
| [CHANGELOG.md](CHANGELOG.md) | Version history (v1.0.1 — general-reliability round: profile vocabulary lint R0-R7, clause-scoped claim quality, PDF line-wrap tolerant alias matching, cross-lingual value-token packs; cold-start battery over six professions, mean Spearman 0.771 hard / 0.809 balanced; v1.3.3 — balanced must-have gate: profile-opt-in weight-proportional ceiling; v1.3.2 — plumber case-study fix round: negation guard, multilingual claim quality, compound matching; v1.3.1 — academic German values fold; v1.3.0 — spine features: content tag verification, decision pins, calibration loop) |
| [docs/GENERAL-RELIABILITY.md](docs/GENERAL-RELIABILITY.md) | Cross-occupation generalization protocol + results: preregistered cold-start battery (nurse, accountant, electrician, baker, Kfz-Mechatroniker, MFA), mechanism checks, regression on tuned corpora, per-client lint workflow |
| [attune-data/casestudy-uni/README.md](attune-data/casestudy-uni/README.md) | University case study: bilingual doctoral-hiring fixture (12 applicants / 22 PDFs), pilot iterations, reproduction commands |
| [vendor/omnidecide-c/README.md](vendor/omnidecide-c/README.md) | The C11 decision kernel the engine runs on (native tier) |
| [SETUP.md](SETUP.md) | Condensed setup card (also shipped in the source zip) |

<details>
<summary><strong>Repository layout</strong></summary>

```
server.py                   stdlib-only web server: static UI + all /api routes
web/                        vanilla frontend (HTML/CSS/JS, no build step) +
                            PWA layer (manifest.webmanifest, sw.js, icons/)
electron/                   optional desktop shell: Electron main +
                            electron-builder config around the standalone bundle
attune-engine/              engine.py, ckernel.py (kernel resolver), floors.py
                            (vendored floors contract), ckernel_native.py +
                            wasm_kernel.py (tier bridges), spine_kernel.py
                            (kernel 2.0.0 spine: tagging, pins, calibration),
                            make_report.py, floors_attune.json, data/
                            (floors_v1.json + spine_schemes.json)
vendor/omnidecide-c/      omnidecide-c 2.0.0 C11 kernel (native tier)
vendor/omnidecide-wasm/   official WASM dist of the same kernel (fallback tier)
attune-data/                templates (runs/ is created at runtime) + shipped
                            case-study fixtures (casestudy-plumber, -trades,
                            -uni: frozen corpora, expert rankings,
                            preregistration hashes, reproduction commands)
attune-sample-data/         demo corpus: 6 candidates, 10 PDFs
scripts/                    QA gates, codebase-intel orchestrator, sample
                            generator, icon fetcher, standalone packager
                            (scripts/standalone/), PWA gate (check_pwa.py)
                            + icon generator (make_icons.py)
.codebase-intel/            analyzer baselines + suppressions (fallow health,
                            ratchets, vulture whitelist, cppcheck exceptions)
ruff.toml                   curated ruff rule set for the Python side
docs/                       architecture, API, CLI, developer guide, marketing,
                            screenshots, diagrams
Dockerfile                  multi-target build: full-stack image (default) +
                            engine/QA-gate image (--target engine)
```

</details>

<details>
<summary><strong>Quality gates</strong></summary>

```bash
python3 scripts/check_python_side.py
# 45-check release gate: static analysis, floors contract, two-pass engine
# determinism, enrichment fields, PII-redaction probes, fixture integrity,
# 7-PDF export validation. Exit 0 = release-ready.

python3 scripts/smoke_test.py
# 54-check fast health check (self-contained, ~10 s): boots its own server,
# every static asset + traversal containment, the loopback guard, all 13
# API routes with error shapes, engine + PDF export on every shipped
# corpus, and a Chromium pass with zero JS errors. --quick / --api-only
# for shorter runs.

python3 scripts/verify_spine_features.py
# 13-check spine battery: pins + replay audit (all 'exact'), spine-on/off
# scoring identity, WASM degradation, mis-tag fixture detection, the
# calibration loop. Prints per-check evidence; protocol notes in
# docs/SPINE-FEATURES.md.

# regression lock vs the stored reference scoring runs (protocol in
# docs/DEVELOPMENT.md): stored lineage runs must replay with zero
# unexpected diffs for any scoring-neutral release

# codebase-intelligence gates (CI wiring: codebase-intel.yml; capability
# map: docs/CODEBASE-INTEL.md). fallow needs Node.js locally; the Python
# and C gates need their analyzers pip/apt-installed:
npx fallow@3.38.1 dead-code --ci
python3 scripts/codebase_intel.py python   # ruff, vulture, pylint, pip-audit, lizard
python3 scripts/codebase_intel.py c        # cppcheck, flawfinder, lizard, jscpd
# 19 + 4 checks: hard gates for dead code, duplication, hygiene, CVEs and
# C warnings; shrink-only ratchets for complexity and clone metrics.
```

</details>

## FAQ

<details>
<summary><strong>Is this "AI"?</strong></summary>

No — and that is the point. There is no model, no training, no inference
service and no cloud call anywhere in the pipeline. Scoring is a deterministic
computation: tuned evidence extraction over the CV text, aggregated on a pure
C11 decision kernel with calibrated confidence floors. That is precisely why
the same folder of CVs produces the same ranking every time, and why every
score can be traced to quoted evidence instead of a probability you have to
take on faith.

</details>

<details>
<summary><strong>Where does candidate data go?</strong></summary>

Nowhere. The UI binds to `127.0.0.1`, the kernel contains no network code, raw
CV text is never persisted, and every output refers to candidates by
pseudonymous sha256 refs. It runs air-gapped: pull the network cable and the
pipeline behaves identically.

</details>

<details>
<summary><strong>Same CVs in — same ranking out, really?</strong></summary>

Byte for byte, including the PDF exports. Every run double-executes the
scoring pipeline and requires sha256 equality between the passes before
anything is written; the release gate replays frozen reference runs with
zero-diff. See [Receipts, not promises](#receipts-not-promises) for the exact
commands.

</details>

<details>
<summary><strong>What happens with an ambiguous or unreadable CV?</strong></summary>

It escalates instead of guessing. Low-confidence extractions, unreadable
documents (the demo corpus includes an image-only scan on purpose) and rank
conflicts land in an append-only review queue that requires human sign-off.
The engine has no auto-reject path at all.

</details>

<details>
<summary><strong>Which languages does it read?</strong></summary>

Ten opt-in language packs — `en zh hi es ar fr bn pt id ur`, plus the
`und` (undetermined, script-agnostic) default — selected via the
`ATTUNE_LANGUAGE` environment variable. Every run manifest records the
effective language and text mode. On the ten-language reference corpus the
engine scores Spearman rho 0.833–0.929 and ranks the human-chosen first
candidate first in all ten languages.

</details>

<details>
<summary><strong>Is it GDPR-friendly?</strong></summary>

It is designed for data minimisation: local-only processing, pseudonymous
outputs, redaction probes on every regression run, and an audit manifest per
run. That is a strong starting position, but a DPIA and legal review for your
specific deployment remain your responsibility — this tool aids compliance,
it is not legal advice.

</details>

## License

Job Attune is released under the **Apache License 2.0** — see
[LICENSE](LICENSE) (full text) and [NOTICE](NOTICE) (copyright and
third-party attributions). Every source file carries an SPDX header; the
vendored kernel keeps its own Apache-2.0 license and Unicode-data notices
under `vendor/omnidecide-c/`.

<p align="center">
  <img src="web/logo.svg" width="72" alt="Job Attune logo" /><br/>
  <strong>Job Attune — Hire for aptitude.</strong><br/>
  <sub>Built by <a href="https://github.com/tamer4osman">Tamer Osman</a> ·
  © 2026 · Apache-2.0 ·
  <a href="https://www.linkedin.com/in/tamer4osman">LinkedIn</a></sub>
</p>
