<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->
# Kernel Migration Verification — v1.8.0 (omnidecide-c)

> **Historical record (kept for audit).** This engineering note predates the
> public v1.0.0 release; the version numbers below are internal development
> numbers from before the re-versioning. It documents the migration from the
> Python OmniDecide 3.3.1 embedded engine to the omnidecide-c C11 kernel.
> The product was named **ScreenPilot** at the time of this verification and
> was renamed **Job Attune** for the initial public release, which is why the
> former name and its paths appear throughout this document. The Python
> kernel is no longer shipped; the commands referencing
> `download/omnidecide/` below no longer apply. The migration evidence itself
> remains the record of why the C kernel is trusted as the sole kernel.

This note records the evidence that the v1.8.0 kernel migration (Python
OmniDecide 3.3.1 embedded engine -> omnidecide-c 1.0.0 C11 kernel) is
scoring-neutral and fully functional. Reproduce everything with the commands
in each section (run from the repository root).

## What changed

| Piece | Before (<=1.7.1) | After (1.8.0) |
|---|---|---|
| Decision kernel | `download/omnidecide/omnidecide/models/kernel.py` (pure Python) | `download/omnidecide-c/` C11 kernel via `screenpilot-engine/ckernel.py` (ctypes bridge) |
| Kernel default | Python | **omnidecide-c** (`SCREENPILOT_KERNEL=python` rolls back) |
| Floors contract | frozen `floors_v1` from the Python tree | unchanged - the Python tree stays as floors source |
| Manifest pin | `omnidecide_version: "3.3.1"` | `omnidecide_version: "omnidecide-c 1.0.0"` (rollback: `"3.3.1"`) |
| Engine version | 1.7.1 | 1.8.0 |

The bridge re-exposes the exact `DeterministicDecisionKernel` class, method
signatures, five-key payload contract and error semantics the engine was
written against; `engine.py` only changed its import block, manifest pin and
version.

## Evidence chain

### 1. The C kernel itself is sound (upstream gates)

```
cd download/omnidecide-c
make test            # 373 checks, 0 failures
make golden-check    # 2013 cases, all byte-identical
make version-check   # OK (version 1.0.0)
```

### 2. Kernel-level A/B battery — 36/36 identical

`scripts`-side battery (29 payload cases + 7 error paths) across all six
primitives with engine-shaped inputs: engine rubric dicts, shortlist/reject
choice contexts, compare tie branches, rank over candidate labels, extract
with top_k clamping (0 and 99), empty/unicode/German CV texts, 8-12k-char
contexts, and every documented error path. Result: **every payload identical
(primitive, result, confidence, probability, distribution) and every error
raises the same exception with the same message.** Both kernels report
backend `embedded-fallback`.

### 3. Full-engine A/B replay — 0 scoring diffs on all shipped corpora

For each corpus (demo 6, logistics14, trades14) the engine ran twice with the
same salt and run-dir basename, once per kernel, and results.json was
deep-diffed under the regression-lock allowlist (version pins, wall-clock
fields, absolute paths, manifest self-hashes):

- **0 unexpected diffs** on every corpus
- rankings identical; review queues identical; all scores, confidences and
  distributions identical
- the **top-level two-pass determinism sha256 matches across kernels** on all
  three corpora - i.e. the canonical scoring output is byte-for-byte the same
- the C kernel runs the full pipeline ~25-45% faster wall-clock (e.g. demo
  1.38s vs 1.79s; logistics14 1.60s vs 2.33s for both passes)

### 4. Release gate — 45/45 green under both kernels

```
python3 scripts/check_python_side.py
# SUMMARY: 45 green / 0 amber / 0 red   (default, omnidecide-c)
SCREENPILOT_KERNEL=python python3 scripts/check_python_side.py
# SUMMARY: 45 green / 0 amber / 0 red   (rollback, Python 3.3.1)
```

C11 now pins the manifest kernel id to the engine's own `ACTIVE_KERNEL_ID`
so the gate stays truthful in either mode; D1/D2 re-validated the 7-PDF
export (batch-report 17 pages + 6 dossiers, sha256 manifest match). The PDF
methodology footer reads `Engine 1.8.0 - Kernel omnidecide-c 1.0.0 - floors
data v1.0 - deterministic replay: PASS` (rollback: `OmniDecide 3.3.1`).

### 5. Bench accuracy — matches the published record

`bench/run_bench.py` with study salt `task32-study` against the frozen
pre-registered human rankings:

| Corpus | engine rho (C kernel) | recorded reference | deterministic |
|---|---|---|---|
| logistics14 | **0.8022** | 0.802 | yes |
| trades14 | **0.8769** | 0.877 | yes |

On these two synthetic gate-heavy holdout cells TF-IDF/BM25 lead (rho 0.8374
/ 0.9385) - exactly the honest-reading situation documented in the README
(the engine's advantage is on the real-CV corpora; the shipped holdouts are
the synthetic ones where coverage-sum rubrics favour veto-free baselines).
The A/B replay proves the engine's own ordering is unchanged by the kernel
swap, so the published real-corpus numbers carry over.

### 6. Web application — end-to-end

`bun install && bun run db:generate && bun run build` succeeds; with the dev
server up, `POST /api/run` (sample corpus) completed with the C kernel
(`engine 1.8.0`, `omnidecide-c 1.0.0`, determinism PASS, ranking identical),
`GET /api/run/results` served the full dossier payload, and `POST /api/report`
exported the 7 PDFs with a matching sha256 manifest. The UI needs no
changes: it spawns `python3 engine.py` and renders manifest fields
dynamically (governance panel shows the kernel pin).

## Known differences (documented, none reachable by the engine)

- The bridge does not wire the image evidence channel (the engine scores
  extracted PDF text only); passing a non-None image raises TypeError.
- `use_cuda` is accepted and ignored - the C kernel has a single
  deterministic execution path (`backend` stays `embedded-fallback`).
- Ultra-edge Unicode-lowercase cases (e.g. KELVIN SIGN folding to `k`) differ
  between the Python `.lower()` tokenizer and the C ASCII-mode tokenizer;
  they cannot appear in the engine's `[a-z0-9]` evidence vocabulary in any
  shipped corpus, and the A/B replay confirms zero effect end to end.
