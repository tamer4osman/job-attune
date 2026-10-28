<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->
# Changelog

All notable changes to the Job Attune engine, UI and tooling.
Engine version is the project's release version; every run manifest records
the engine, decision-kernel and floors versions that produced it.

## [Unreleased]

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
  - `docker build -t job-attune-full .` (default target) — full-stack image
    (~700 MB): Next.js standalone server on Node 22 plus the Python engine,
    compiled kernel, demo candidates and profile templates baked in. Start
    with `docker run -d -p 127.0.0.1:3000:3000 job-attune-full`. Smoke-tested
    end-to-end through the app's own API: template load, folder scan
    (6 candidates), a screening run that finished in 0.4 s (6 screened /
    2 shortlisted), and 7 PDF exports (17-page batch report + 6 candidate
    dossiers) validated with pypdf and downloaded over HTTP.
- The fullstack image bakes the kernel version header at
  `/app/vendor/omnidecide-c/include/omnidecide.h` (copied from the exact
  `kernel-build` source tree), so `ckernel.py` reports the version of the
  actually-baked library (`omnidecide-c 1.0.0`) in run manifests instead of
  `unknown`.
- Standalone end-user distributions for Windows, macOS and Linux, built by
  the new Release workflow (`.github/workflows/release.yml`) and by
  `scripts/standalone/package.sh` - the same script CI calls, so local
  builds are identical. Every archive bundles the compiled C11 kernel for
  that platform, the Next.js standalone server, the Python engine with the
  demo corpus and profile templates, and complete Node.js 22 LTS +
  CPython 3.12 runtimes with reportlab/pypdf preinstalled - unpack, run
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
