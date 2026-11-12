#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Profile vocabulary lint - the profile-creation checklist (v1.0.1).

The cold-start generalization battery (four unseen professions, zero tuning)
confirmed that the engine's MECHANISMS are title-agnostic while profile
VOCABULARY is the one per-title artifact that decides cold-start quality.
Three failure modes were root-caused by single-edit counterfactuals:

  CF1 (nurse)    over-broad alias: the credential alias 'state examination'
                 matched a paramedic's state exam and falsely cleared a
                 must-have for a trade switcher.
  CF2 (accountant) rigid alias: 'accounting degree' missed the real-world
                 phrasing 'MSc Accounting and Finance'.
  CF3 (baker)    word-order alias: 'gesellenbrief baecker' missed
                 'Baeckerin, Gesellenbrief'; the one compound hit sat at
                 evidence 0.59 against the 0.6 gate.

This lint turns those findings into deterministic checks run at
profile-creation time, BEFORE any engine run, so vocabulary defects are
caught while they are still free to fix. It never edits a profile - it
reports findings with a concrete fix hint, and a profile passes when no
ERROR-severity finding remains.

Usage:
    python profile_lint.py <profile.json> [<profile2.json> ...]
    python profile_lint.py --json <profile.json>     (machine-readable)

Exit code 0 = no ERROR findings, 1 = at least one ERROR, 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# rule data
# ---------------------------------------------------------------------------

# R1: credential words that match almost any profession's documents. An alias
# built ONLY from these words is not anchored to the requirement's domain and
# will falsely clear the must-have for switchers (CF1).
GENERIC_CREDENTIAL_WORDS = {
    "state", "examination", "exam", "pruefung", "staatliche", "anerkennung",
    "certificate", "certified", "zeugnis", "zeugnisse", "abschluss",
    "degree", "qualification", "qualifications", "ausbildung", "training",
    "vocational", "diploma", "licence", "license", "urkunde",
}

# Degree/qualification suffixes whose exact-phrase aliases go rigid (CF2):
# real documents phrase the FIELD, not the full credential string
# ('MSc Accounting and Finance', 'Baeckerin, Gesellenbrief').
DEGREE_SUFFIX_WORDS = {
    "degree", "studium", "studiengang", "abschluss", "ausbildung",
    "qualification", "bachelor", "master", "msc", "bsc", "diplom",
}

# R5: alternatives inside one alias/skill phrase; alias_regex matches literal
# text, so " or "/" oder " never matches real documents
ALTERNATION_RE = re.compile(r"\b(?:or|oder|beziehungsweise|bzw\.?)\b", re.IGNORECASE)

STOPWORDS_LINT = {
    "and", "or", "der", "die", "das", "den", "dem", "des", "und", "oder",
    "the", "for", "mit", "nach", "zur", "zum", "im", "in", "of", "auf",
}

# Common English modifier nouns that legitimately appear only inside
# multi-word aliases (R3): they are polysemous on their own, so a bare
# companion alias would create false hits, not prevent them.
COMMON_MODIFIERS = {
    "vehicle", "patient", "client", "customer", "medical", "practice",
    "financial", "annual", "service", "public", "private", "general",
    "senior", "junior", "digital", "electric", "electrical", "workshop",
}

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------

def _tokens(phrase: str) -> list:
    return [t for t in re.findall(r"[a-z0-9]+", phrase.lower()) if len(t) > 1]


def _normal(alias: str) -> str:
    return " ".join(_tokens(alias))


def lint_profile(profile: dict) -> list:
    findings = []

    def add(rule: str, severity: str, where: str, detail: str, hint: str) -> None:
        findings.append({"rule": rule, "severity": severity, "where": where,
                         "detail": detail, "hint": hint})

    categories = profile.get("categories") or {}
    # R0 structural basics
    if not categories:
        add("R0-structure", "error", "profile", "no categories defined",
            "add at least one requirement category (technical_skills, ...)")
    seen_aliases: dict = {}
    must_haves: list = []
    for cat, reqs in categories.items():
        for req in reqs:
            skill = str(req.get("skill", "")).strip()
            where = f"{cat}:{skill or '<empty skill>'}"
            if not skill:
                add("R0-structure", "error", where, "requirement without skill text",
                    "every requirement needs a human-readable skill name")
            aliases = [str(a) for a in (req.get("aliases") or []) if str(a).strip()]
            if req.get("must_have"):
                must_haves.append((where, skill, aliases))
            # R1 over-broad credential alias (CF1)
            for a in aliases:
                toks = [t for t in _tokens(a) if t not in STOPWORDS_LINT]
                if toks and all(t in GENERIC_CREDENTIAL_WORDS for t in toks):
                    add("R1-overbroad", "error", where,
                        f"alias '{a}' consists only of generic credential words",
                        "anchor the alias to the domain, e.g. add the field noun "
                        "('pflegefachkraft', 'nursing licence'); a bare 'state "
                        "examination' matches other professions' exams and "
                        "falsely clears must-haves (battery CF1)")
            # R2 rigid degree alias (CF2)
            for a in aliases:
                toks = _tokens(a)
                if toks and toks[-1] in DEGREE_SUFFIX_WORDS and len(toks) >= 2:
                    head = toks[0]
                    add("R2-rigid", "warning", where,
                        f"alias '{a}' enumerates a full credential string",
                        f"also add the bare field noun ('{head}') so real-world "
                        "phrasings match ('MSc Accounting and Finance', battery CF2)")
            # R3 word-order compound (CF3): a multi-word alias built only from
            # long domain tokens is order- and inflection-fragile
            # ('gesellenbrief baecker' vs 'Baeckerin, Gesellenbrief') when one
            # of its tokens is not available as a bare single-word alias
            # (single words match compound-tolerantly via alias_regex)
            bare_tokens = {t for a in aliases if len(_tokens(a)) == 1
                           for t in _tokens(a)}
            for a in aliases:
                toks = [t for t in _tokens(a) if t not in STOPWORDS_LINT]
                if len(toks) < 2 or not all(len(t) >= 6 for t in toks):
                    continue
                # common English modifiers ('vehicle diagnostics') do not need
                # a bare companion; only domain-specific long tokens do (CF3)
                missing = [t for t in toks
                           if t not in bare_tokens and t not in COMMON_MODIFIERS]
                if missing:
                    add("R3-wordorder", "warning", where,
                        f"multi-word alias '{a}': token(s) {missing} not "
                        "available as bare single-word alias(es)",
                        f"add the bare head noun (e.g. '{missing[0]}') - German "
                        "documents inflect and reorder ('Baeckerin, Gesellenbrief', "
                        "battery CF3); single-word aliases match compounds")
            # R5 alternation inside one alias (engine matches literal text)
            for a in [skill] + aliases:
                if ALTERNATION_RE.search(a):
                    add("R5-alternation", "error", where,
                        f"phrase '{a}' contains an alternation ('or'/'oder')",
                        "split into one alias per alternative; alias_regex "
                        "matches the literal string, so 'baker or confectioner "
                        "vocational qualification' never matches real documents")
            # R6 duplicates
            for a in aliases:
                n = _normal(a)
                if n == _normal(skill):
                    add("R6-duplicate", "info", where,
                        f"alias '{a}' duplicates the skill phrase",
                        "remove the duplicate alias row")
                if n in seen_aliases and seen_aliases[n] != where:
                    add("R6-duplicate", "warning", where,
                        f"alias '{a}' also used by {seen_aliases[n]}",
                        "shared aliases blur per-requirement evidence; split or "
                        "specialize")
                seen_aliases.setdefault(n, where)
            # R4 must-have coverage
            if req.get("must_have"):
                if len(aliases) < 3:
                    add("R4-gate-coverage", "error", where,
                        f"must-have with only {len(aliases)} alias(es)",
                        "cold-start must-haves need >= 3 aliases covering the "
                        "common German AND English document phrasings")
                if cat.lower() != "languages":
                    de = any(re.search(r"(?i)^(ge|be|ver|zer|ent|an|auf|aus|ein)", t)
                             or t.endswith(("ung", "heit", "keit", "schaft", "brief",
                                            "suche", "diagnose", "abnahme",
                                            "pruefung", "zeugnis", "nahme", "pflege"))
                             for a in aliases for t in _tokens(a))
                    en = any(t in {"and", "with", "care", "management", "administration",
                                   "preparation", "communication", "service", "work"}
                             or len(t) >= 4 and t.isascii() and t not in STOPWORDS_LINT
                             for a in aliases for t in _tokens(a))
                    if not de or not en:
                        add("R4-gate-coverage", "warning", where,
                            "must-have aliases appear single-language",
                            "mixed-language corpora need both German and English "
                            "alias phrasings (battery: language fairness check)")
    # R7 values_text language convention
    values_text = str((profile.get("company") or {}).get("values_text", ""))
    if not values_text.strip():
        add("R7-values", "warning", "company.values_text",
            "no values_text defined (values_fit weight defaults to 15%)",
            "define 3-6 value phrases in English base form; German folds ship "
            "in the engine (v1.0.1), so English base forms match both languages")
    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: "list | None" = None) -> int:
    ap = argparse.ArgumentParser(description="Job-Attune profile vocabulary lint")
    ap.add_argument("profiles", nargs="+", help="profile JSON file(s)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    report = {}
    errors = 0
    for p in args.profiles:
        path = Path(p)
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            report[str(path)] = {"error": f"unreadable: {exc}"}
            errors += 1
            continue
        findings = lint_profile(profile)
        report[str(path)] = {"findings": findings}
        errors += sum(1 for f in findings if f["severity"] == "error")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for path, block in report.items():
            print(f"== {path}")
            if "error" in block:
                print(f"   ERROR: {block['error']}")
                continue
            findings = block["findings"]
            if not findings:
                print("   CLEAN - no findings")
                continue
            for f in sorted(findings, key=lambda f: (SEVERITY_ORDER[f["severity"]], f["rule"])):
                print(f"   [{f['severity'].upper():7s}] {f['rule']}: {f['where']}")
                print(f"             {f['detail']}")
                print(f"             hint: {f['hint']}")
            n_err = sum(1 for f in findings if f["severity"] == "error")
            print(f"   -> {len(findings)} finding(s), {n_err} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
