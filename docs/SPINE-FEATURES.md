<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->

# Spine features — kernel 2.0.0 capabilities in Job Attune

Since v1.3.0 Job Attune uses the **integration spine** of omnidecide-c
2.0.0 (`include/odk_spine.h`) — the capability layer the 1.x kernel did not
have. The spine adds three things to the app, none of which changes a
score: content-based document-tag verification (F1), decision pinning with
a replay auditor (F6), and a review-outcome calibration loop (F4). The
scheme data itself is registered through the kernel's extension API (F7)
from `attune-engine/data/spine_schemes.json` — the kernel ships with zero
application vocabulary, all domain knowledge is data, never code.

## What each feature does

| Feature | Kernel API | What Job Attune gains |
|---|---|---|
| **Content tag verification** | `odk_spine_classify` (F1) | Every readable document's filename-derived role (CV / cover letter) is cross-checked against its content by a deterministic Tier A classifier. `results.json` records `content_tag` per file; a confident disagreement raises a non-blocking `tag_conflict` review item instead of silently scoring a mistagged document. |
| **Decision pins + replay audit** | `odk_spine_pin` (F6) | Every kernel evaluation of the first pipeline pass is pinned: request bytes, decision, confidence, kernel version, schema fingerprint and the registered customization state. Pins land in `<run-dir>/spine_pins.jsonl`; `scripts/replay_audit.py` re-derives every pinned decision on a fresh kernel and must report `exact` for all of them. |
| **Calibration loop** | `odk_spine_observation_ingest` + `odk_spine_calibrate` (F4) | Human sign-offs in `review_decisions.jsonl` become decision+outcome observation pairs; `scripts/calibrate_report.py` computes the live confidence-vs-agreement calibration report (ten bins, per primitive) — the deployment-level counterpart of the frozen floors contract. |

## Selection policy — `$ATTUNE_SPINE`

| Policy | Behavior |
|---|---|
| `auto` *(default)* | Engage the spine whenever the **native** kernel tier is active. |
| `off` | Disable every spine feature; `results.json.spine.status` records the explicit opt-out. |

The spine is **native-tier only**: the WASM fallback dist exports the
evaluate surface (`odkw_*`), not the spine. When the engine runs on the
WASM tier, the spine block records
`"status": "unavailable"` with the reason and the run proceeds exactly as
in v1.2.0 — the layered kernel contract (docs/LAYERED-KERNEL.md) is
untouched.

## Why this cannot change a score

- Scoring runs through the same `ckernel` seam as before; the spine never
  sits in that path. `resolve_spine()` gates on the backend *after* the
  kernel tier is chosen, and every spine call is additive bookkeeping.
- Classification only annotates (`files[].content_tag`) and escalates to
  the **human** review queue — the pipeline never re-tags on its own, so
  the text a document contributes to scoring is unchanged.
- Pins re-evaluate the exact request on the same deterministic kernel —
  a second identical computation, not a different one.
- Verified empirically by the spine battery: the canonical
  scoring payloads of a spine-on and a spine-off run are byte-identical
  once the annotations and the self-referential pass hashes are set aside,
  and the two-pass determinism guarantee holds with pinning active.

## New run artifacts

| Artifact | Contents |
|---|---|
| `results.json` → `spine` block | Feature status/policy/backend, schema fingerprint, classify/tag-conflict/mixed-document/pin counters, pins file name + sha256, or the unavailability reason |
| `results.json` → `candidates[].files[].content_tag` | `{label, confidence, role, agrees, tier, matched_terms}` per readable document, plus `mixed_hint` when BOTH role schemes score above the 0.5 prior |
| `results.json` → `review_queue[]` | new non-blocking kinds `tag_conflict` (content contradicts the filename; review floor 0.5 = the Tier A no-rule prior — a real cv/cover conflict expresses ~0.53, v1.3.2) and `mixed_document` (single file holds letter AND CV) |
| `<run-dir>/spine_pins.jsonl` | One DecisionPin per kernel evaluation (JSONL, schema field order) |

## New tools

```bash
# replay-audit a run: every pinned decision must re-derive as 'exact'
python3 scripts/replay_audit.py --run-dir attune-data/runs/<run-id>

# calibration report over human sign-offs (one or many runs)
python3 scripts/calibrate_report.py --run-dir attune-data/runs/<run-id>

# full spine verification battery (13 checks)
python3 scripts/verify_spine_features.py
```

## Design notes

- **Schemes are data**: `attune-engine/data/spine_schemes.json` registers
  the two Tier A document-role schemes (EN + DE lexical rules; confidence
  = 0.9 all-terms / 0.5 + 0.4 × matched-terms any-rule / 0.5 no-rule).
  Extend it by editing the JSON — never the kernel.
- **A pin failure is never fatal**: pinning is audit integrity, so a
  failed pin increments `spine.pin_errors` and surfaces in the manifest
  instead of aborting a finished run.
- **Timestamps are caller-supplied** (epoch ms), consistent with the
  spine's no-wall-clock rule; pins carry wall-clock time but live outside
  the hashed pipeline payload.
- **Future capability, deliberately not enabled**: the kernel's
  experimental feature set 1 (negation/number-match score features,
  `vendor/omnidecide-c/docs/FEATURES.md`) would change decisions and
  requires its own calibration study before any release could ship it.
  The same applies to spine-side domain vocabulary registration (F7
  vocabularies) beyond the document-role schemes above.
