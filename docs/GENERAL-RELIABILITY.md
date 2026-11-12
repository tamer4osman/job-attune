# General reliability - cross-occupation protocol and results

Question this document answers: can the engine handle *all* professional and
technical job titles, not just the ones it was tuned on? Perfect accuracy is
not achievable and per-client profile vocabulary remains the calibration
surface; the claim tested here is narrower and stronger: the MECHANISMS are
title-agnostic and a cold-start profile that passes the lint gate produces
trustworthy rankings on professions never seen before.

## Protocol (v1 round, engine 1.3.3, findings)

Four professions never used by any prior corpus or profile: registered nurse
(professional/healthcare), tax accountant (professional/finance),
electrician (technical/trades), baker (technical/food production). Profiles
were written once from generic occupational vocabulary; expected rankings and
mechanism expectations were preregistered with sha256 sidecars before any
engine run; nothing was tuned after the runs.

Results and root causes were recorded in the round-1 evidence bundle
(`genbattery_v1.txt` + `genbattery_v1_summary.json`, internal study files not
part of the shipped tree). Headline: mechanisms all
held (classification, negation guard, gating, pinning/replay, determinism,
cross-tier identity, negative controls); profile vocabulary was the binding
constraint (three counterfactual-confirmed alias defects) and two
language-shape effects suppressed scores (sentence-wide claim-quality
markers; values folds without care/finance German).

## Fixes shipped in 1.0.1 (engine-level, title-agnostic)

1. Clause-scoped claim-quality windows (`_claim_quality`).
2. PDF line-wrap tolerant multi-word alias matching (`alias_regex`).
3. Cross-lingual value-token packs with compound and plural tolerance
   (`VALUES_TOKEN_SYNONYMS`, `values_fit_score`).
4. Profile vocabulary lint (`attune-engine/profile_lint.py`, rules R0-R7),
   run before preregistration; ERROR findings block the release of a profile.

## Protocol (v2 round, engine 1.0.1)

Same six professions: the four v1 corpora with byte-identical profiles
(isolates the engine-level gains), plus two NEW professions at true cold
start - Kfz-Mechatroniker (technical trades) and Medizinische Fachangestellte
(healthcare administration) - whose profiles passed the lint gate BEFORE
preregistration, and whose corpora include a third-language probe (an
ASCII-folded Polish application packet). Expected orders frozen with sha256
sidecars before any engine run; no profile or vocabulary iteration after runs.

## Results (Spearman vs preregistered order)

| job         | v1 hard | v2 hard | v2 balanced |
|-------------|---------|---------|-------------|
| nurse       | 0.371   | 0.543   | 0.657       |
| accountant  | 0.771   | 0.714   | 0.829       |
| electrician | 0.943   | 0.943   | 0.943       |
| baker       | 0.771   | 0.771   | 0.771       |
| kfz (new)   | -       | 0.771   | 0.771       |
| mfa (new)   | -       | 0.886   | 0.886       |
| **mean**    | 0.714   | **0.771** | **0.809** |

Regression on the three tuned corpora (1.3.3 -> 1.0.1, unchanged profiles):
plumber 0.748 -> 0.748 (order identical); trades 0.741 -> 0.860; university
design-strength 0.582 -> 0.862. The trades and university gains are the
line-wrap fix recovering candidates the engine had falsely capped, and the
removal of a cross-language marker leak (English '(fluent)' scoping a German
claim). Kernel binaries are byte-identical to 1.3.3.

Mechanism checks: 37/45 as formulated; every FAIL is root-caused in the
round-2 evidence bundle (`genbattery_v2.txt`, internal study file not part of
the shipped tree) - the nurse
switcher check exposes exactly the CF1 profile artifact the lint now flags,
the switcher formulation passes 5/6 in its zero-gap principle form, and the
mfa F1 10/12 is the content classifier honestly abstaining on Polish while
filename routing still classifies and reads the documents.

## Recommendations for deployment

- Run `profile_lint.py` on every new client profile; fix ERROR findings
  before the profile is used.
- For mixed-language corpora, prefer `must_have_gate: "balanced"`
  (documented profile option); keep `hard` where compliance requires strict
  gating. The trades opt-in test was declined by the mechanical rule
  (0.846 < 0.860), so the option is per-corpus, decided by measurement.
- Third-language alias coverage (beyond German/English) is per-client
  profile vocabulary; the mechanisms (routing, reading, gating, auditing)
  are language-independent and degrade honestly (abstain, route by filename,
  rank on what is actually evidenced).
