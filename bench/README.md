<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->
# Job Attune Bench Harness

Candidate-blind baseline benchmarking for the Job Attune engine. Pure
standard library; shares the engine's tokenizer and PDF extraction so all
systems rank the same bytes of text.

## Systems

| System | Kind | Scoring |
|---|---|---|
| Job Attune engine | full pipeline | claim-quality evidence, floors, kernel aggregation |
| `boolean-ats` | baseline | must-have keyword veto; survivors ranked by nice-to-have coverage |
| `tfidf` | baseline | cosine similarity, sublinear tf, smoothed idf |
| `bm25` | baseline | Okapi BM25 (k1=1.5, b=0.75) |

Candidate-blind guarantee: baseline keywords come only from the job profile
(requirement skills, aliases, company, job title) - never from candidate
documents.

## Usage

```bash
# one cell = one corpus, four systems, determinism double-pass
python3 bench/run_bench.py \
  --corpus /path/to/corpus/folders \
  --profile attune-data/templates/example-senior-data-engineer.json \
  --human /path/to/frozen_ranking.json \
  --name bench-c20 --salt task32-study \
  --out /path/to/bench-c20.json
```

`--human` (optional) points at a frozen pre-registered ranking: either a list
of `{"rank", "folder"}` objects or `{"ranking": [...]}`. Metrics: Spearman
rho (average-rank), MAE, top-3 and bottom-3 overlap, all computed against the
human order. Without `--human`, baselines are scored against the engine order
(agreement diagnostic) and the engine cell reports null metrics.

## Determinism and salt

Every system runs twice per cell; the runner records sha256 over a canonical
score projection per pass. The engine's pseudonymisation salt affects
near-tie resolution (candidate refs feed tie-breaking), so reproducibility
claims must state the salt. The reference suite pins `task32-study` so
engine cells are directly comparable with the published record and with the
regression lock.

## Reference results (study salt)

| System | corpus20 rho | real-corpus (40) rho |
|---|---|---|
| Job Attune engine | 0.931 | 0.640 |
| BooleanATS | 0.725 | 0.510 |
| TF-IDF | 0.848 | 0.444 |
| BM25 | 0.917 | 0.574 |

All twelve cells deterministic (identical projection hashes across passes).
Corpora: 20 synthetic candidates / 34 documents with a frozen reviewer
ranking; 40 authentic career-center candidates / 66 documents with a frozen
pre-registered ranking; the 6-candidate shipping demo (no human reference).

## Aggregation forms (opt-in)

The engine's category->overall aggregation is a pure function with
preregistered variants (see docs/DEVELOPMENT.md). Set optional keys in the
profile's `weights`:

| Key | Values | Default |
|---|---|---|
| `category_weighting` | `uniform` (mean of category averages, the default behavior) / `req_share` (categories weighted by their requirement-weight share) / `global` (single pooled weighted average) | `uniform` |
| `zero_weight_factor` | float 0..1; a zero-evidence requirement contributes weight x factor | `1.0` |

Every run records the active form in results.json (`aggregation` block).
The calibration verdict kept the defaults: the optimal shape is
profile-dependent, so per-profile selection
requires holdout validation - `req_share` improved corpus20 to rho 0.9564
but degraded the real-CV pool. Measure before you switch.

## Holdout corpora (bench/corpora/)

`logistics14` and `trades14` are synthetic, manifest-labeled candidate pools
(14 CVs each) with rubric-based preregistered reference rankings frozen
(human_ranking.json + preregistration.sha256) before any engine run. Run a
cell with bench/run_bench.py --corpus bench/corpora/<cell>/candidates
--profile bench/corpora/<cell>/profile.json --human
bench/corpora/<cell>/human_ranking.json --name <cell>.
