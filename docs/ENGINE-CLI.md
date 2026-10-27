<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->
# Engine & Reporter CLI Reference

The engine and the PDF reporter are plain `python3` CLIs — the Next.js API
layer spawns them exactly as documented here, and they are fully usable from
a shell for scripted or air-gapped operation.

## `attune-engine/engine.py`

```
python3 attune-engine/engine.py --folder DIR --profile FILE --run-dir DIR
```

| Flag | Default | Description |
|---|---|---|
| `--folder` | *(required)* | Main folder with one sub-folder per candidate; each sub-folder holds the candidate's PDFs. |
| `--profile` | *(required)* | Job profile JSON path (requirements with weights/must-have flags/aliases, company summary, values, job description). |
| `--run-dir` | *(required)* | Output directory for this run (created if missing). |
| `--floors` | `<engine dir>/floors_attune.json` | Floors contract path. Values are validated on load; malformed data fails the run (fail-fast, no silent defaults). |
| `--salt` | run-dir name | Deterministic pseudonymisation salt. Same salt + same inputs = same candidate refs across runs. |
| `--reference-year` | `2026` (pinned `REFERENCE_YEAR`) | Year that "present"-open date ranges resolve against. Override to replay historical runs under their original wall-clock assumptions. |

### Aggregation profile keys (opt-in)

The job profile's `weights` block accepts two engine keys beyond the classic
`categories_total` / `values_fit` mix. Unknown values fail the run
(fail-fast); every run records the effective configuration in the
`aggregation` provenance block of `results.json`.

| Key | Default | Meaning |
|---|---|---|
| `weights.category_weighting` | `uniform` | `uniform` = unweighted mean of the six category averages (reference-lineage behaviour); `req_share` = category averages weighted by original requirement-weight share; `global` = single pooled evidence average |
| `weights.zero_weight_factor` | `1.0` | Float in [0, 1]; a requirement with `evidence_score == 0.0` contributes `weight * factor` to its category average |

```json
{
  "weights": {
    "categories_total": 0.85,
    "values_fit": 0.15,
    "category_weighting": "uniform",
    "zero_weight_factor": 1.0
  }
}
```

Calibration verdict (preregistered grid): the defaults above are the
calibrated optimum; change them only with corpus-level evidence (see
`docs/DEVELOPMENT.md`, bench harness).

Exit code `0` = run complete; non-zero = validation or processing failure
(including floors-contract violations and determinism-critical input errors).

### Outputs (run directory)

| File | Contents |
|---|---|
| `progress.json` | `{ "progress": { "stage", "pct", "message" } }`, written atomically per stage |
| `results.json` | Full outcome: per-candidate dossiers (profile card, skills inventory, interview prompts, verdict labels, score decomposition, tenure, cohort percentiles), ranking, comparison block, market gaps, bench strength, talent pool, review queue, statistics, run manifest |

The manifest block inside `results.json` records `engine` (1.0.0),
`omnidecide_version` (`omnidecide-c 1.0.0`, the only kernel), `floors_version`
(1.0), the aggregation
configuration, and `kernel_text_mode` /
`kernel_language` (the effective kernel text layer for the run) for
auditability.

### Multilingual kernel settings (C kernel)

The kernel runs in **Unicode text mode by default** - the only
mode in which non-Latin scripts contribute kernel evidence, and
scoring-identical on pure-ASCII input (verified byte-for-byte on the
shipped corpora).

```bash
# rollback lever (optional): restore the byte-frozen ASCII mode
ATTUNE_TEXT_MODE=ascii
# optional: enable the kernel's language pack for that job market
# (und en zh hi es ar fr bn pt id ur auto; default und = generic)
ATTUNE_LANGUAGE=zh
```

`unicode` (default) is the required mode for evidence written in non-Latin
scripts; language packs add per-language stopwords and script normalization
(see `download/omnidecide-c/docs/LANGUAGES.md`) and stay opt-in per job
market.

### Example (demo corpus)

```bash
python3 attune-engine/engine.py \
  --folder attune-sample-data/candidates \
  --profile attune-data/templates/example-senior-data-engineer.json \
  --run-dir /tmp/my-run
python3 -m json.tool /tmp/my-run/results.json | head -40
```

Two runs on the same inputs (and default salt) produce identical
`results.json` bytes — the QA gate enforces this via sha256.

## `attune-engine/make_report.py`

```
python3 attune-engine/make_report.py --run-dir DIR [--pseudonymous 1|0]
```

| Flag | Default | Description |
|---|---|---|
| `--run-dir` | *(required)* | A run directory with a complete `results.json`. |
| `--pseudonymous` | `1` | `1` = redact names/contacts from PDFs (candidate refs only). `0` = identify candidates (for internal use only). |

### Outputs (`<run-dir>/exports/`)

- `batch-report.pdf` — position-level report: verdict, ranking with tier and
  percentile leaders, requirement coverage matrix, review notes, market gaps,
  bench strength, talent pool (~17 pages on the demo corpus).
- `candidate-<ref>.pdf` — one pseudonymous dossier per candidate.
- `manifest.json` — `{ "files": [{ "kind", "ref", "file", "sha256" }] }`;
  hashes are recomputed and matched by the QA gate, and the download API
  will only serve files listed here.

PDFs render with ReportLab invariant mode: byte-identical output for
identical inputs, across machines.

## QA gate

```bash
python3 scripts/check_python_side.py
```

Runs the engine twice on the demo corpus (determinism sha256 check),
validates the vendored floors contract and its pinned calibration data,
pins the active decision-kernel version (omnidecide-c),
probes
all enrichment fields, tuned-evidence overrides and PII redaction, verifies
the bench baseline systems (C36-C38), then exports and validates 7 PDFs.
45 checks total; exit `0` = all green. This is the release gate for every
engine change.
