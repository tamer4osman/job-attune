<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->
# Codebase Intelligence Gates

[fallow](https://fallow.tools) is a TS/JS codebase analyzer: one graph of
the repository reporting dead code, duplication, complexity hotspots,
architecture drift and dependency hygiene. This repo wires it into CI as a
required gate for the JavaScript side — and pairs it with a
fallow-equivalent analyzer stack for every other language in the tree
(Python, C), so no language ships without the same class of protection.

Wired in `.github/workflows/codebase-intel.yml` (runs on every push and
PR, plus a weekly schedule so `pip-audit` can catch newly published CVEs):

| Job | Language | Tool chain |
|---|---|---|
| `fallow` | JavaScript (`web/`) | `npx fallow@3.38.1` |
| `python-intel` | Python | `ruff`, `vulture`, `pylint`, `pip-audit`, `lizard` |
| `c-intel` | C (`vendor/omnidecide-c`) | `cppcheck`, `flawfinder`, `lizard`, `jscpd` |

The build/test gates (compile with `-Werror`, 45-check release gate,
Playwright UI walkthrough, golden-corpus replay) stay in `ci.yml`; this
workflow adds the *static-analysis* layer on top.

## Capability map

What fallow reports for JS, and which tool reports the same thing for
Python and C:

| fallow capability | JavaScript | Python | C |
|---|---|---|---|
| dead code (unused files/exports/vars) | `fallow dead-code` | `vulture` (≥60% confidence + whitelist), `ruff` F/RUF059 | `cppcheck` unusedFunction classes* |
| duplication | `fallow dupes` | `pylint duplicate-code` (≥10 similar lines) | `jscpd` (≥110-token clones) |
| complexity / health | `fallow health` | `lizard` CCN bands | `lizard` CCN bands |
| architecture (cycles, boundaries) | `fallow architecture` | — (single-package tree; cycles would need import analysis Python's stdlib layout doesn't reward) | — (single translation unit per symbol family, enforced by the kernel's link graph) |
| dependency audit | `fallow audit` | `pip-audit` on `requirements.txt` | — (no third-party C deps) |
| security candidates | `fallow security` | — | `flawfinder` |

\* reported under the cppcheck `style` umbrella that the ratchet tracks;
the hard cppcheck gate covers the `error`/`warning`/`performance`/
`portability` severities.

## Hard gates vs ratchets

Two kinds of gates run, and the difference matters:

**Hard gates** fail on *any* finding. These are green today and must stay
green: a new finding is always a regression someone has to look at.

- fallow `dead-code`, `dupes`, `architecture` (`--ci` = SARIF +
  `--fail-on-issues`)
- `ruff` (curated rule set, `ruff.toml`), `vulture`, `pylint
  duplicate-code`, `pip-audit`
- `cppcheck` warning/performance/portability (accepted exceptions are
  listed inline in `.codebase-intel/cppcheck-suppressions.txt`)
- `flawfinder` at risk level 5

**Ratchets** fail only on *growth* against a committed baseline, mirroring
`fallow health --baseline --fail-on-stale-baseline`. The Python engine and
the C kernel are large, frozen, heavily tested code where complexity is a
known quantity — the gate's job is to make sure it never gets *worse*, and
that every accepted improvement is locked in:

- fallow health: 33 known findings in
  `.codebase-intel/fallow-health-baseline.json`; a *new* over-threshold
  function fails, and once you fix one, the stale entry fails the build
  until you re-save (`fallow baselines prune`, or `fallow health
  --save-baseline .codebase-intel/fallow-health-baseline.json`).
- `lizard` CCN bands, `cppcheck` style count, `flawfinder` level-4 count,
  `jscpd` clone counts: baselines in
  `.codebase-intel/ratchet-baselines.json`, gated by
  `scripts/codebase_intel.py`. Improvements print
  `re-run with --update-baseline and commit` and fail CI (strict mode)
  until the baseline is re-saved — the shrink-only contract.

## Running locally

```bash
# JavaScript (needs Node.js; nothing is installed into the repo)
npx fallow@3.38.1 dead-code --ci
npx fallow@3.38.1 health --baseline .codebase-intel/fallow-health-baseline.json \
    --fail-on-issues --fail-on-stale-baseline

# Python (pip install ruff==0.17.3 vulture==2.16 pylint==4.1.3 \
#             lizard==1.24.3 pip-audit==2.10.1)
python3 scripts/codebase_intel.py python

# C (pip install flawfinder==2.0.20 lizard==1.24.3; cppcheck 2.17.1 on PATH
#     or via CPPCHECK=...; jscpd via Node)
python3 scripts/codebase_intel.py c

# after an accepted improvement, lock it in:
python3 scripts/codebase_intel.py python c --update-baseline   # then commit
```

Missing analyzers are AMBER (skip with a warning) when you run the script
by hand and RED under `CODEBASE_INTEL_STRICT=1`, which is what CI sets —
CI never silently skips a gate.

## The support files

| File | Purpose |
|---|---|
| `.fallowrc.json` | fallow config: entry points + pointer to the health baseline |
| `.codebase-intel/fallow-health-baseline.json` | fallow health ratchet (37 entries) |
| `.codebase-intel/ratchet-baselines.json` | Python + C ratchet baselines |
| `.codebase-intel/vulture-whitelist.py` | framework hooks and API-parity names vulture cannot see used |
| `.codebase-intel/cppcheck-suppressions.txt` | the two documented cppcheck exceptions (with reasons) |
| `ruff.toml` | the curated ruff rule set and what is deliberately not selected |
| `scripts/codebase_intel.py` | Python + C gate orchestrator (19 checks) |

Tool versions are pinned in the workflow to the versions the baselines
were measured with. Bump a pin and its baseline together: analyzers
count findings differently across versions, and an unpinned analyzer
makes the ratchet flap.

## What the gates already caught

Wiring the gates up found real debt on day one, all fixed in the same
change: a dead helper (`band_color`) and an unused module constant
(`CLIENT_HEADER`, now actually used by the loopback guard) in the report
layer; five unused locals and eight unused unpacking targets across the
engine, server and QA scripts; six stale `# noqa` directives; a dead
comprehension in the release gate; two unsorted import blocks; and 9.7 KB
of QA scratch output (`scripts/tmp_pycheck/`) that had been committed by
accident. The v1.1.0 cleanup pass had already brought fallow itself to
0 dead files / 0 dead exports / 0 duplication — the ratchets keep it
there.
