#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Job Attune - GDPR-safe local resume screening engine.

Current version: see ENGINE_VERSION below; release history lives in
CHANGELOG.md at the repository root. This file is the whole scoring
pipeline (stdlib-only Python); the web UI is not needed for screening.

Consumes the omnidecide-c C11 decision kernel (vendored under
vendor/omnidecide-c/, reached through the ctypes bridge ckernel.py; the
floors contract ships as attune-engine/floors.py with its calibration
data in attune-engine/data/floors_v1.json) and turns a
folder of applicant PDFs into a deterministic, fully auditable screening
run:

    main_folder/                 (selected in the app)
      <candidate subfolder>/
        cv.pdf                   (aliases: resume, cv, lebenslauf, ...)
        cover_letter.pdf         (optional; aliases: cover, motivation, anschreiben, ...)

Module map (top to bottom, for navigation):
  constants + floors loader     ENGINE_VERSION, REFERENCE_YEAR, CATEGORY_KEYS,
                                aggregation_config(), floors contract load
  text machinery               tokenizer, alias regexes, redaction, claim
                                quality (none/partial/good/strong grading)
  write_progress               atomic stage/percent reporting to progress.json
  evidence_stage               per-requirement evidence extraction + scoring
                               (kernel 'extract') with tuned-evidence overrides
  aggregate_categories()       PURE aggregation core - no I/O, unit-testable
  aggregate_stage              category averages + values fit + must-have cap
  decision_stage               kernel 'choice' + 'compare' + 'rank' (tie-break,
                               rank-conflict escalation to the review queue)
  profile/cohort/review/       enrichment: profile cards, skills inventory,
  comparison stages            interview prompts, percentiles, market gaps
  main()                       CLI wiring, two-pass determinism harness

All six decision primitives are load-bearing (omnidecide-c port of the same
embedded engine: identical constants, identical payloads - see ckernel.py):
  noul    - readability gate per document (floor 0.98, blocking on failure)
  extract - evidence snippets per requirement x candidate (floor 0.37)
  score   - advisory per-category evidence rating (floor 0.80)
  choice  - shortlist decision per candidate (floor 0.73)
  compare - adjacent-pair tie-break when scores are within epsilon (floor 0.58)
  rank    - advisory order check over the top candidates (floor 0.12)

Escalations use the floors-as-data contract: should_escalate() +
escalation_record() with the app floors table (floors_attune.json),
loaded ONCE per run and passed explicitly (hot-path pattern).

Enrichment: after scoring, each candidate receives a profile_card
(experience, seniority, education, languages, certifications, quantified
achievements, career timeline, risk flags), a skills_inventory (lexicon scan
beyond the profile requirements) and interview_prompts; the run receives
cohort standing (percentiles/deltas per candidate) and a comparison block
(category leaders, skill-coverage matrix, differentiators, head-to-head,
position verdict) that drives the final report.

Accuracy remediation (validated on a 20-candidate benchmark against a
pre-registered independent review):
  D1 experience date ranges are summed as years (the 12x divisor is gone)
  D2 decimal experience statements ("6.5 years") parse exactly
  D3 overlapping employment ranges raise an employment_overlap risk flag
  D4 aspirational ("excited to learn X") and self-assessed basic claims are
     capped below the must-have bar, audited via claim_quality, and routed to
     interview prompts instead of being credited as experience
  E1 values-fit matching folds common German value terms onto English ones
  E2 seniority ignores keywords on closed (past) employment lines
  D6 a compare verdict outside {A, B} escalates as tie_unresolved

The whole pipeline runs twice; the canonical sha256 of both passes must match
(determinism guarantee, replay-ready audit trail). 100% local - no network.

Accuracy evidence: the candidate-blind bench harness (bench/) ranks this
engine against Boolean ATS / TF-IDF / BM25 on corpora with frozen human
reference rankings - protocol and numbers in bench/README.md. Scoring
behaviour is protected by the regression lock (stored reference-lineage
runs replayed with an explicit diff allowlist); scoring changes require
calibration evidence, not just unit tests (docs/DEVELOPMENT.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Decision-library resolution. One kernel ships with the tree:
#   vendor/omnidecide-c  the omnidecide-c C11 kernel, reached through
#                          the ctypes bridge in ckernel.py
# The floors contract is vendored at attune-engine/floors.py (data in
# data/floors_v1.json). Paths resolve relative to this file so the tree
# stays relocatable; OMNIDECIDE_C_LIB overrides the compiled C library
# location (see ckernel.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))  # ckernel.py + floors.py

from floors import (  # noqa: E402
    escalation_record,
    floors_version,
    load_floors,
    should_escalate,
)

import ckernel  # noqa: E402

# Kernel: the omnidecide-c C11 kernel is the only kernel (see CHANGELOG.md).
DeterministicDecisionKernel = ckernel.DeterministicDecisionKernel
ACTIVE_KERNEL_ID = ckernel.KERNEL_ID  # e.g. "omnidecide-c 1.0.0"

ENGINE_VERSION = "1.0.0"
# Pinned wall-clock anchor: open date ranges ("present") resolve to this year so
# runs stay byte-reproducible across calendar years. Override via --reference-year
# (audit: datetime.now().year leaking into deterministic fields).
REFERENCE_YEAR = 2026


def kernel_language_kwargs() -> dict:
    """Kernel text-layer configuration (Unicode is the default).

    The omnidecide-c kernel ships a Unicode text layer and ten language
    packs (docs/LANGUAGES.md upstream); the bridge exposes them through
    $ATTUNE_TEXT_MODE ("ascii" | "unicode") and $ATTUNE_LANGUAGE
    (ISO code; "und" = generic baseline). The default text mode is
    "unicode": it is scoring-identical on pure-ASCII input (verified
    byte-for-byte against the shipped corpora) and it is the only mode in
    which non-Latin scripts contribute kernel evidence (measured: in
    ASCII mode a clear Chinese decision scores an exact 0.50/0.50 tie).
    Set ATTUNE_TEXT_MODE=ascii to restore the byte-frozen ASCII
    behavior.
    """
    return {
        "text_mode": os.environ.get("ATTUNE_TEXT_MODE") or "unicode",
        "language": os.environ.get("ATTUNE_LANGUAGE") or "und",
    }

EMPTY_CHARS = 80                  # below: document effectively empty (blank/image-only)
SHORT_DOC_CHARS = 250             # readable but low-signal - flagged, not blocking
CATEGORY_KEYS = {
    "soft_skills": "Soft Skills",
    "technical_skills": "Technical Skills",
    "languages": "Languages",
    "degrees": "University Degrees",
    "certifications": "Professional Certifications",
    "bootcamps": "Training Bootcamps",
}
CATEGORY_WEIGHTING_FORMS = ("uniform", "req_share", "global")
AGGREGATION_DEFAULTS = {"category_weighting": "uniform", "zero_weight_factor": 1.0}


def aggregation_config(profile: dict) -> dict:
    """Single source of truth for the aggregation variant in effect.

    Read from profile['weights'] optional keys, falling back to the release
    defaults. Unknown forms and out-of-range factors fail fast."""
    weights = profile.get("weights") or {}
    form = weights.get("category_weighting", AGGREGATION_DEFAULTS["category_weighting"])
    if form not in CATEGORY_WEIGHTING_FORMS:
        raise ValueError(f"unknown category_weighting form: {form!r}")
    dz = float(weights.get("zero_weight_factor", AGGREGATION_DEFAULTS["zero_weight_factor"]))
    if not 0.0 <= dz <= 1.0:
        raise ValueError(f"zero_weight_factor out of range [0, 1]: {dz!r}")
    return {"category_weighting": form, "zero_weight_factor": dz}


CV_ALIASES = {"resume", "cv", "lebenslauf", "curriculumvitae", "curriculum", "vitae"}
COVER_ALIASES = {"cover", "coverletter", "letter", "motivation", "motivationsschreiben", "anschreiben"}
REQUIRED_FLOORS = {"noul", "extract", "score", "compare", "rank", "choice"}
EMAIL_RE = re.compile(r"[\w.+-]{1,64}@[\w-]{1,64}\.[\w.]{2,24}")  # bounded: no quadratic backtracking on hostile input
PHONE_RE = re.compile(r"\+?\d[\d\s/.-]{5,}\d")  # >=6 separator-joined digits -> phone-like
# Year / month-year tokens are masked before phone redaction (and restored
# afterwards) so employment dates in evidence snippets survive, while real
# phone numbers (>= 7 digits) are still replaced.
YEAR_TOKEN_RE = re.compile(r"\b(?:19[89]\d|20\d{2})\b|\b(?:0?[1-9]|1[0-2])\s*/\s*(?:19|20)\d{2}\b")
COMPARE_EPSILON = 2.0             # score points (0-100) for adjacent tie-break
RANK_TOP_N = 10                   # rank primitive advisory window
SNIPPET_MAX_CHARS = 240
CONTEXT_MAX_CHARS = 4000
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "are",
    "was", "were", "will", "would", "our", "their", "your", "you", "who", "whom",
    "which", "what", "where", "when", "how", "all", "any", "not", "but", "its",
    "it's", "into", "onto", "per", "via", "able", "about", "over", "under",
}
LEVEL_WORDS = ((0.8, "strong"), (0.6, "good"), (0.4, "partial"), (0.05, "weak"))
BANDS = ((75.0, "strong"), (60.0, "good"), (45.0, "potential"), (0.0, "weak"))

# claim-quality heuristics (D4): an alias hit surrounded by aspiration
# ("excited to learn X") or self-assessed low proficiency ("X (basic scripts)")
# is NOT credited as experience - its evidence score is capped below the 0.4
# must-have bar, the claim quality is persisted for audit, and an interview
# prompt asks for demonstrated depth instead.
ASPIRATION_RE = re.compile(
    r"\b(?:excited|eager|keen|hoping|hope|want|wants|plan|plans|would\s+like|"
    r"would\s+love|looking\s+forward|ready|willing)\b[^.;:!?]{0,40}\bto\b"
    r"[^.;:!?]{0,15}\b(?:learn|learning|grow|growing|develop|developing|"
    r"pick\s+up|gain)\b|\b(?:mochte|freue)\b[^.;:!?]{0,30}\b(?:lernen|"
    r"dazulernen)\b",
    re.IGNORECASE,
)
LOWPROF_RE = re.compile(
    r"\b(?:basic|basics|fundamentals|fundamental|familiar|beginner|novice|"
    r"limited|exposure|grundkenntnisse|basiskenntnisse)\b",
    re.IGNORECASE,
)
HIGHPROF_RE = re.compile(
    r"\b(?:strong|advanced|expert|fluent|extensive|deep|proficient|solid)\b",
    re.IGNORECASE,
)
CLAIM_CAPS = {"aspirational": 0.30, "qualified_low": 0.35}
QUALITY_PRECEDENCE = {"direct": 2, "qualified_low": 1, "aspirational": 0}

# tuned-evidence overlay (fine-tuning, soup-style): a reviewer-calibrated
# table reclassifies the claim quality of (candidate, requirement) pairs where
# the deterministic heuristic disagreed with human judgment on real documents.
# Overrides flow through the SAME evidence pipeline (CLAIM_CAPS + precedence),
# so every tuned score stays explainable: the persisted row records the tuned
# quality, confidence and rationale next to the heuristic input.
TUNED_SCHEMA = "attune.tuned-evidence/1"
TUNE_MIN_CONFIDENCE = 0.60  # below this the heuristic result is kept
TUNE_QUALITIES = {"direct", "qualified_low", "aspirational"}


def load_tuned_evidence(path) -> dict:
    """Load + validate a tuned-evidence JSON file (fail fast, like floors).

    Expected shape:
    {
      "schema": "attune.tuned-evidence/1",
      "overrides": [
        {"candidate": folder_name, "skill": requirement skill,
         "claim_quality": "direct|qualified_low|aspirational",
         "confidence": 0.0-1.0, "rationale": "why"}, ...]
    }
    Returns {"metadata": {...}, "overrides": {(candidate, skill): row}}.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != TUNED_SCHEMA:
        raise ValueError(f"tuned-evidence file must declare schema {TUNED_SCHEMA!r}")
    rows = data.get("overrides") or []
    if not isinstance(rows, list):
        raise ValueError("tuned-evidence 'overrides' must be a list")
    table: dict = {}
    for i, row in enumerate(rows):
        where = f"tuned override #{i}"
        cand, skill = str(row.get("candidate", "")).strip(), str(row.get("skill", "")).strip()
        quality = str(row.get("claim_quality", "")).strip()
        conf = row.get("confidence")
        if not cand or not skill:
            raise ValueError(f"{where}: 'candidate' and 'skill' are required")
        if quality not in TUNE_QUALITIES:
            raise ValueError(f"{where}: claim_quality must be one of {sorted(TUNE_QUALITIES)}")
        if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not 0.0 <= float(conf) <= 1.0:
            raise ValueError(f"{where}: confidence must be a number in [0, 1]")
        table[(cand, skill)] = {
            "claim_quality": quality,
            "confidence": float(conf),
            "rationale": str(row.get("rationale", "")),
        }
    meta = {k: data[k] for k in ("method", "created", "sources", "notes") if k in data}
    return {"metadata": meta, "overrides": table}

# multilingual values matching (E1): German CVs state company values in
# German ("Nachhaltigkeit", "Eigenverantwortung"). Common German value terms
# fold onto their English counterparts before coverage is computed; spellings
# reflect ASCII-folded PDF text (umlauts stripped by the producer).
VALUES_TOKEN_SYNONYMS = {
    "sicherheit": "safety", "sicher": "safety", "sicherheits": "safety",
    "zuverlassigkeit": "reliable", "zuverlaessigkeit": "reliable",
    "zuverlassig": "reliable", "zuverlaessig": "reliable",
    "verlasslich": "reliable", "verlassliches": "reliable",
    "verlassige": "reliable", "verlasslichem": "reliable",
    "nachhaltigkeit": "sustainability", "nachhaltig": "sustainability",
    "nachhaltige": "sustainability", "nachhaltigen": "sustainability",
    "offene": "open", "offen": "open", "offenen": "open",
    "kommunikation": "communication", "kommunizieren": "communication",
    "kommunikationsstarke": "communication", "kommunikativ": "communication",
    "eigenverantwortung": "ownership", "verantwortung": "accountability",
    "verantwortungsuebernahme": "accountability",
    "verantwortungsbewusstsein": "accountability",
    "teamfaehigkeit": "teamwork", "zusammenarbeit": "teamwork",
    "qualitaet": "quality", "lernbereitschaft": "learning",
    "wissensweitergabe": "mentoring", "wissensteilung": "mentoring",
}

# --------------------------------------------------------------------------- #
# applicant-profile enrichment (stage 6b) - deterministic regex heuristics
# --------------------------------------------------------------------------- #
# D2: decimal statements ("6.5 years", "1,5 Jahre") capture the full
# number - the integer-only pattern used to read "6.5 years" as "5 years"
YEARS_RE = re.compile(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*\+?\s*(?:years?|yrs?|jahre?)\b", re.IGNORECASE)
# E2: a CLOSED year range ("(2017-2019)") marks a past employment
# line; seniority keywords found only on such lines are history, not the
# current title
CLOSED_RANGE_RE = re.compile(r"(?:19[89]\d|20\d{2})\s*(?:-|\u2013|\u2014|to|bis)\s*(?:19[89]\d|20\d{2})", re.IGNORECASE)
YEAR_RANGE_RE = re.compile(r"(19[89]\d|20\d{2})\s*(?:-|\u2013|\u2014|to|bis)\s*\n?\s*(?:(19[89]\d|20\d{2})|(present|current(?:ly)?|heute|today|now|ongoing))", re.IGNORECASE)
MONTH_YEAR_RE = re.compile(r"\b(0?[1-9]|1[0-2])\s*/\s*((?:19|20)\d{2})\b")
BARE_YEAR_RE = re.compile(r"\b(?:19[89]\d|20\d{2})\b")
SENIORITY_KEYWORDS = [
    ("lead/principal", ("principal", "staff engineer", "head of", "director", "vp engineering", "tech lead", "lead engineer", "team lead")),
    ("senior", ("senior", "sr.")),
    ("junior", ("junior", "graduate", "intern", "working student", "praktikant", "trainee")),
]
DEGREE_FAMILIES = [
    ("doctorate", ("phd", "ph.d", "doctorate", "doktortitel", "dr. rer. nat", "doctor of philosophy")),
    ("master", ("master of science", "msc", "m.sc", "master of arts", "m.a.", "master of engineering", "m.eng", "master in", "master's", "masters degree", "diplom", "master of business")),
    ("bachelor", ("bachelor of science", "bsc", "b.sc", "bachelor of arts", "b.a.", "bachelor of engineering", "b.eng", "ba ", "bachelor's", "bachelors degree")),
    ("bootcamp", ("bootcamp", "boot camp")),
    ("apprenticeship", ("apprenticeship", "ausbildung", "vocational training", "associate degree")),
]
CANONICAL_LANGUAGES = ("english", "german", "french", "spanish", "italian", "dutch", "polish", "portuguese", "turkish", "russian", "ukrainian", "arabic", "hindi", "czech", "greek")
LANG_ALIASES = {"deutsch": "german", "franzosisch": "french", "francais": "french", "spanisch": "spanish", "espanol": "spanish", "italienisch": "italian", "polnisch": "polish", "niederlandisch": "dutch", "russisch": "russian", "tschechisch": "czech", "griechisch": "greek", "turkisch": "turkish", "englisch": "english"}
LEVEL_BANDS = [
    ("native", ("native", "bilingual", "mother tongue", "muttersprachler")),
    ("fluent", ("c2", "c1", "fluent", "proficient", "advanced", "professional")),
    ("intermediate", ("b2", "b1", "intermediate", "conversational", "good knowledge")),
    ("basic", ("a2", "a1", "basic", "beginner")),
]
ACHIEVEMENT_VERBS = ("increased", "decreased", "reduced", "improved", "saved", "grew", "automated", "migrated", "scaled", "optimized", "optimised", "cut", "boosted", "delivered", "launched", "built", "designed", "led", "introduced", "streamlined")
CERT_KEYWORDS = ("certified", "certification", "certificate", "zertifiziert", "associate", "specialty", "professional certificate")
SKILL_LEXICON = [
    ("Python", ("python", "python3", "pandas", "numpy")),
    ("SQL", ("sql", "postgresql", "postgres", "mysql", "sqlite")),
    ("Apache Airflow", ("airflow", "dags")),
    ("Apache Kafka", ("kafka")),
    ("Apache Spark", ("spark", "pyspark")),
    ("Docker", ("docker", "containerisation", "containerization", "containers")),
    ("Kubernetes", ("kubernetes", "k8s")),
    ("AWS", ("aws", "lambda", "redshift")),
    ("GCP", ("gcp", "google cloud", "bigquery")),
    ("Azure", ("azure")),
    ("Terraform", ("terraform", "infrastructure as code")),
    ("dbt", ("dbt")),
    ("Snowflake", ("snowflake")),
    ("Git", ("git", "github", "gitlab")),
    ("CI/CD", ("ci/cd", "jenkins", "github actions", "gitlab ci", "continuous integration")),
    ("Java", ("java", )),
    ("JavaScript/TypeScript", ("javascript", "typescript")),
    ("React", ("react", "next.js")),
    ("Rust", ("rust", )),
    ("C++", ("c++", )),
    ("Machine Learning", ("machine learning", "scikit", "ml models")),
    ("LLM/GenAI", ("llm", "large language model", "genai")),
    ("ETL/ELT pipelines", ("etl", "elt", "data pipelines", "datenpipelines", "streaming pipelines")),
    ("Data warehousing", ("data warehouse", "data warehouses", "dim_model", "dimensional model")),
    ("Excel", ("excel", )),
    ("Tableau", ("tableau", )),
    ("Power BI", ("power bi", "powerbi")),
    ("SAP", ("sap", )),
    ("Jira/Confluence", ("jira", "confluence")),
    ("Agile/Scrum", ("scrum", "agile", "kanban")),
    ("REST APIs", ("rest", "restful", "api design")),
    ("GraphQL", ("graphql", )),
    ("Monitoring/Observability", ("grafana", "prometheus", "datadog", "observability")),
]
ACHIEVEMENT_MAX = 3
INVENTORY_MAX = 24
PROMPT_MAX = 5


# --------------------------------------------------------------------------- #
# canonical JSON / hashing (mirrors OmniDecide replay conventions)
# --------------------------------------------------------------------------- #

def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def round2(value: float) -> float:
    return math.floor(float(value) * 100.0 + 0.5) / 100.0


def round1(value: float) -> float:
    """Half-up rounding to one decimal (same idiom as round2; round() is half-to-even)."""
    return math.floor(float(value) * 10.0 + 0.5) / 10.0


# --------------------------------------------------------------------------- #
# name / alias handling
# --------------------------------------------------------------------------- #

def fold_name(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", stripped.lower())


def classify_role(path: Path) -> str:
    stem = fold_name(path.stem)
    if stem in CV_ALIASES:
        return "cv"
    if stem in COVER_ALIASES:
        return "cover"
    for alias in sorted(COVER_ALIASES, key=len, reverse=True):
        if alias in stem:
            return "cover"
    for alias in sorted(CV_ALIASES, key=len, reverse=True):
        if alias in stem:
            return "cv"
    return "unclassified"


TOKEN_RE = re.compile(r"[a-z0-9+#\.]{2,}")


def tokenize(text: str) -> list:
    # strip edge dots so "communication." matches "communication" while
    # internal dots (node.js) survive
    toks = (raw.strip(".") for raw in TOKEN_RE.findall(text.lower()))
    return [t for t in toks if t and t not in STOPWORDS]


def phrase_tokens(phrase: str) -> list:
    return [t for t in TOKEN_RE.findall(phrase.lower()) if t not in STOPWORDS and len(t) > 1]


def alias_regex(alias: str) -> re.Pattern:
    return re.compile(r"(?<![a-z0-9])" + re.escape(alias.lower().strip()) + r"(?![a-z0-9])", re.IGNORECASE)


# --------------------------------------------------------------------------- #
# PDF text extraction (PyMuPDF preferred, pypdf fallback) - local only
# --------------------------------------------------------------------------- #

def extract_pdf_text(path: Path) -> dict:
    """Local-only extraction. error = hard backend failure; emptiness is NOT an error
    here - the caller decides via the deterministic EMPTY_CHARS detector."""
    info = {"chars": 0, "pages": 0, "method": None, "error": None, "text": ""}
    try:
        import fitz  # PyMuPDF

        with fitz.open(str(path)) as doc:
            parts = [page.get_text() or "" for page in doc]
            info["pages"] = doc.page_count
            info["method"] = "pymupdf"
        info["text"] = "\n".join(parts)
    except Exception as exc:  # error boundary: recorded, never crashes the run
        info["error"] = f"pymupdf: {type(exc).__name__}: {exc}"
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            parts = []
            for page in reader.pages:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    parts.append("")
            info["pages"] = len(reader.pages)
            info["method"] = "pypdf"
            info["text"] = "\n".join(parts)
        except Exception as exc2:
            info["error"] += f" | pypdf: {type(exc2).__name__}: {exc2}"
    info["chars"] = len(info["text"].strip())
    return info


# --------------------------------------------------------------------------- #
# evidence scoring (deterministic, explainable app logic)
# --------------------------------------------------------------------------- #

def _claim_quality(text: str, start: int, end: int) -> str:
    """Classify the claim surrounding an alias hit (D4, deterministic).

    aspirational  - the text right before the hit signals intent to LEARN the
                    skill ("excited to learn Python") rather than evidence of
                    doing it; qualified_low - the text right after marks the
                    skill as basic/limited ("Python (basic scripts)"); direct -
                    everything else (a high-proficiency marker also blocks the
                    low-proficiency downgrade).
    """
    before = text[max(0, start - 45):start]
    after = text[end:min(len(text), end + 40)]
    if ASPIRATION_RE.search(before) or ASPIRATION_RE.search(after[:20]):
        return "aspirational"
    if HIGHPROF_RE.search(after) or HIGHPROF_RE.search(before[-15:]):
        return "direct"
    if LOWPROF_RE.search(after) or LOWPROF_RE.search(before[-15:]):
        return "qualified_low"
    return "direct"


def evidence_for(req: dict, cv_text: str, cover_text: str, cv_tokens: "set | None" = None, cover_tokens: "set | None" = None, quality_override: "str | None" = None) -> dict:
    aliases = [req["skill"]] + list(req.get("aliases") or [])
    # tuned override: the reviewer read the WHOLE document, so the
    # reclassification applies to every alias hit of this requirement, replacing
    # the per-hit heuristic window(_claim_quality scans +/- 45 chars only)
    if quality_override is not None:
        quality_for_all = quality_override
    else:
        quality_for_all = None
    best, mentions = None, 0  # best = (eff, precedence, raw_base, source, quality)
    for alias in aliases:
        if not alias.strip():
            continue
        rx = alias_regex(alias)
        cv_hits = len(rx.findall(cv_text))
        cover_hits = len(rx.findall(cover_text))
        mentions += cv_hits + cover_hits
        for base, source, text in ((1.0, "cv", cv_text), (0.85, "cover letter", cover_text)):
            m = rx.search(text)
            if not m:
                continue
            quality = quality_for_all if quality_for_all is not None else _claim_quality(text, m.start(), m.end())
            # effective credit: capped for qualified/aspirational claims, raw
            # source weight otherwise; ties prefer the higher claim quality so
            # a direct cover-letter hit beats an aspirational CV mention
            eff = CLAIM_CAPS.get(quality, base)
            cand = (eff, QUALITY_PRECEDENCE[quality], base, source, quality)
            if best is None or cand[:2] > best[:2]:
                best = cand
    best_exact = best[2] if best else 0.0
    best_src = best[3] if best else None
    best_quality = best[4] if best else (quality_override or "direct")
    req_tokens = phrase_tokens(req["skill"])
    tokfrac = 0.0
    if req_tokens:
        both = (cv_tokens if cv_tokens is not None else set(tokenize(cv_text))) | (
            cover_tokens if cover_tokens is not None else set(tokenize(cover_text)))
        tokfrac = sum(1 for t in req_tokens if t in both) / len(req_tokens)
    return {"exact": best_exact, "exact_source": best_src, "claim_quality": best_quality,
            "token_fraction": round2(tokfrac), "mentions": mentions}


def evidence_score(ev: dict, snippet_support: bool) -> float:
    score = 0.55 * ev["exact"] + 0.25 * ev["token_fraction"] + (0.20 if snippet_support else 0.0)
    if ev["mentions"] > 1:
        score += min(0.10, 0.02 * (ev["mentions"] - 1))
    cap = CLAIM_CAPS.get(ev.get("claim_quality") or "direct")
    if cap is not None:
        score = min(score, cap)
    return round2(min(1.0, score))


def _phone_like(match: "re.Match") -> str:
    """Replace only genuinely phone-like runs (>= 7 digits), keep short numerics."""
    digits = re.sub(r"\D", "", match.group(0))
    return "[phone]" if len(digits) >= 7 else match.group(0)


def redact(text: str) -> str:
    """PII minimisation: strip direct contact identifiers before persistence.

    Year/month-year tokens are masked first and restored afterwards, so ranges
    like "2018-2020" or "10/2015 - 12/2019" keep their meaning instead of being
    mangled into "[phone]"; genuine phone numbers are still replaced.
    """
    text = EMAIL_RE.sub("[email]", text)
    store: list = []

    def _mask(m: "re.Match") -> str:
        store.append(m.group(0))
        return f"\x00{len(store) - 1}\x00"

    masked = YEAR_TOKEN_RE.sub(_mask, text)
    masked = PHONE_RE.sub(_phone_like, masked)
    for i, token in enumerate(store):
        masked = masked.replace(f"\x00{i}\x00", token)
    return masked


def level_word(score: float) -> str:
    for threshold, word in LEVEL_WORDS:
        if score >= threshold:
            return word
    return "none"


def band_word(overall: float) -> str:
    for threshold, word in BANDS:
        if overall >= threshold:
            return word
    return "weak"


# --------------------------------------------------------------------------- #
# progress reporting (atomic writes; polled by the web UI)
# --------------------------------------------------------------------------- #

def write_progress(run_dir: Path, stage: str, pct: float, message: str) -> None:
    payload = {"stage": stage, "pct": round(pct, 1), "message": message, "updated_at": now_iso()}
    tmp = run_dir / "progress.json.tmp"
    tmp.write_text(canonical_json({"progress": payload}), encoding="utf-8")
    os.replace(tmp, run_dir / "progress.json")


def kernel_subset(payload: dict) -> dict:
    """Keep only the deterministic, replay-comparable keys of the kernel payload.
    Evidence strings are PII-redacted before persistence."""
    evidence = payload.get("evidence")
    if isinstance(evidence, str):
        evidence = redact(evidence)
    return {
        "result": payload.get("result"),
        "confidence": payload.get("confidence"),
        "distribution": payload.get("distribution"),
        "evidence": evidence,
    }


def clamp_context(*parts: str) -> str:
    joined = "\n\n".join(p for p in parts if p and p.strip())
    return joined[:CONTEXT_MAX_CHARS]


# --------------------------------------------------------------------------- #
# stage 1: scan the main folder
# --------------------------------------------------------------------------- #

def scan_candidates(folder: Path, role_overrides: dict, run_salt: str) -> tuple:
    candidates, scan_notes = [], []
    for sub in sorted(p for p in folder.iterdir() if p.is_dir()):
        pdfs = sorted(p for p in sub.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
        if not pdfs:
            scan_notes.append({"folder": sub.name, "note": "no PDF files found - candidate skipped"})
            continue
        files, roles = [], []
        for pdf in pdfs:
            rel = str(pdf.relative_to(folder))
            role = role_overrides.get(rel) or role_overrides.get(pdf.name) or classify_role(pdf)
            if role not in ("cv", "cover") and len(pdfs) == 1 and not roles:
                role = "cv"
            if role not in ("cv", "cover"):
                role = "cv" if not any(r == "cv" for r in roles) else "cover"
            roles.append(role)
            files.append({
                "name": pdf.name,
                "rel_path": str(pdf.relative_to(folder)),
                "role": role,
                "size_bytes": pdf.stat().st_size,
                "sha256": sha256_file(pdf),
            })
        if not any(r == "cv" for r in roles):
            scan_notes.append({"folder": sub.name, "note": "no file classified as CV - candidate flagged for review"})
        candidate_ref = hashlib.sha256((sub.name + "|" + run_salt).encode("utf-8")).hexdigest()[:10]
        candidates.append({
            "candidate_ref": candidate_ref,
            "folder_name": sub.name,
            "folder_path": str(sub),
            "files": files,
        })
    return candidates, scan_notes


# --------------------------------------------------------------------------- #
# stage 2: text extraction + noul readability gates
# --------------------------------------------------------------------------- #

def extract_and_gate(candidates: list, kernel, floors: dict, audit: list) -> None:
    for cand in candidates:
        cand["texts"] = {}
        cand["noul_gates"] = []
        kernel_advisory_recorded = False
        for finfo in cand["files"]:
            path = Path(cand["folder_path"]) / finfo["name"]
            extracted = extract_pdf_text(path)
            text = extracted.pop("text")
            finfo.update(extracted)
            raw_unreadable = extracted["chars"] < EMPTY_CHARS
            readable = not raw_unreadable
            finfo["readable"] = readable
            finfo["short_document"] = readable and extracted["chars"] < SHORT_DOC_CHARS
            if readable:
                # Duplicate role (e.g. cv.pdf + resume.pdf both present):
                # concatenate deterministically instead of silently overwriting
                # the first document's content.
                prev = cand["texts"].get(finfo["role"])
                cand["texts"][finfo["role"]] = (prev + "\n" + text).strip() if prev else text
            statement = "The document contains machine-readable text suitable for automated screening."
            payload = kernel.evaluate_noul(statement, clamp_context(text) if readable else " ")
            conf = float(payload["confidence"])
            kernel_below_floor = should_escalate("noul", conf, floors=floors)
            gate = {
                "file": finfo["name"],
                "role": finfo["role"],
                "chars": extracted["chars"],
                "statement": statement,
                "confidence": conf,
                "floor": floors["noul"],
                "escalate": kernel_below_floor,
                "blocking": raw_unreadable and finfo["role"] == "cv",
                "raw_unreadable": raw_unreadable,
                "short_document": finfo["short_document"],
                "kernel": kernel_subset(payload),
            }
            cand["noul_gates"].append(gate)
            if raw_unreadable and finfo["role"] == "cv":
                rec = escalation_record("noul", conf, floors=floors)
                rec.update({
                    "kind": "unreadable_document",
                    "candidate_ref": cand["candidate_ref"],
                    "file": finfo["name"],
                    "blocking": True,
                    "detail": (
                        f"CV file {finfo['name']} contains no machine-readable text "
                        f"({extracted['chars']} chars) - manual review required"
                    ),
                })
                audit.append(rec)
            elif kernel_below_floor and not kernel_advisory_recorded and readable:
                kernel_advisory_recorded = True
                rec = escalation_record("noul", conf, floors=floors)
                rec.update({
                    "kind": "noul_kernel_advisory",
                    "candidate_ref": cand["candidate_ref"],
                    "file": finfo["name"],
                    "blocking": False,
                    "detail": (
                        f"Readability gate confidence {conf:.2f} below floor {floors['noul']:.2f} "
                        "for at least one document - deterministic text check passed, advisory only"
                    ),
                })
                audit.append(rec)


# --------------------------------------------------------------------------- #
# stage 3: requirement evidence via extract + local matching
# --------------------------------------------------------------------------- #

def verdict_word(score: float) -> str:
    """Review-ready verdict label per requirement (aligned with the level bands)."""
    if score >= 0.6:
        return "met"
    if score >= 0.4:
        return "partial"
    return "missing"


def collect_requirements(profile: dict) -> list:
    reqs = []
    for cat_key, cat_label in CATEGORY_KEYS.items():
        for idx, req in enumerate(profile.get("categories", {}).get(cat_key, []) or []):
            skill = str(req.get("skill", "")).strip()
            if not skill:
                continue
            reqs.append({
                "id": f"{cat_key}-{idx:02d}",
                "category": cat_key,
                "category_label": cat_label,
                "skill": skill,
                "weight": max(0.0, min(5.0, float(req.get("weight", 1.0)))),
                "must_have": bool(req.get("must_have", False)),
                "aliases": [str(a) for a in (req.get("aliases") or []) if str(a).strip()],
            })
    return reqs


def evidence_stage(candidates: list, requirements: list, kernel, floors: dict, audit: list, tuned: "dict | None" = None) -> None:
    """Stage 2 - per-requirement evidence extraction and claim-quality scoring.

    For every candidate x requirement the kernel's extract primitive returns
    up to three text snippets; each snippet is redacted, then graded for
    claim QUALITY (what the document actually claims about the skill) via
    QUALITY_PRECEDENCE. The best grade across CV and cover letter sets the
    requirement's evidence_score. Kernel confidence below the 'extract'
    floor escalates to the review queue instead of silently scoring low -
    the escalation-first contract."""
    tuned_table = (tuned or {}).get("overrides", {})
    for cand in candidates:
        cv_text = cand["texts"].get("cv", "")
        cover_text = cand["texts"].get("cover", "")
        context = clamp_context(cv_text, cover_text)
        cand["requirements"] = []
        low_conf_seen = False
        # Per-candidate constants: tokenize once, not once per requirement.
        cv_tokens = set(tokenize(cv_text))
        cover_tokens = set(tokenize(cover_text))
        for req in requirements:
            instruction = f"Find passages that demonstrate: {req['skill']}"
            payload = kernel.evaluate_extract(instruction, context, top_k=3) if context else {"result": [], "confidence": 0.0, "distribution": {}, "evidence": None}
            conf = float(payload.get("confidence") or 0.0)
            # cap BEFORE redacting: redaction runs a regex scan whose cost is
            # bounded by input length, so never feed it unbounded kernel text
            snippets = [redact(str(s)[:SNIPPET_MAX_CHARS * 4])[:SNIPPET_MAX_CHARS] for s in (payload.get("result") or []) if str(s).strip()]
            snippet_support = bool(snippets) and conf >= floors["extract"]
            # tuned-evidence lookup: keyed on folder_name x requirement skill
            override = tuned_table.get((cand["folder_name"], req["skill"]))
            quality_override = None
            tuned_row = None
            if override and override["confidence"] >= TUNE_MIN_CONFIDENCE:
                quality_override = override["claim_quality"]
                tuned_row = {"applied": True, "confidence": override["confidence"],
                             "rationale": override["rationale"],
                             "tuned_claim_quality": override["claim_quality"]}
            ev = evidence_for(req, cv_text, cover_text, cv_tokens, cover_tokens,
                              quality_override=quality_override)
            score = evidence_score(ev, snippet_support)
            item = {
                **req,
                "exact": ev["exact"],
                "exact_source": ev["exact_source"],
                "claim_quality": ev["claim_quality"],
                "claim_quality_heuristic": None if quality_override is None else _claim_quality_highest_hit(req, cv_text, cover_text),
                "token_fraction": ev["token_fraction"],
                "mentions": ev["mentions"],
                "tuned": tuned_row if tuned_row else {"applied": False},
                "snippets": snippets,
                "extract_confidence": conf,
                "snippet_support": snippet_support,
                "evidence_score": score,
                "level": level_word(score),
                "verdict": verdict_word(score),
            }
            cand["requirements"].append(item)
            if should_escalate("extract", conf, floors=floors) and not low_conf_seen and not snippets:
                low_conf_seen = True
                rec = escalation_record("extract", conf, floors=floors)
                rec.update({
                    "kind": "low_confidence_extraction",
                    "candidate_ref": cand["candidate_ref"],
                    "blocking": False,
                    "detail": f"Extract confidence {conf:.2f} below floor {floors['extract']:.2f} for candidate - evidence extraction degraded",
                })
                audit.append(rec)


# --------------------------------------------------------------------------- #
# stage 4: aggregation + score-primitive advisory + values fit
# --------------------------------------------------------------------------- #

def _claim_quality_highest_hit(req: dict, cv_text: str, cover_text: str) -> str:
    """Recompute the heuristic claim quality (no override) for persistence when a
    tuned override replaced it - keeps every tuned row explainable against the
    heuristic input it corrected. Picks the highest-precedence hit like
    evidence_for does (quality_for_all disabled)."""
    aliases = [req["skill"]] + list(req.get("aliases") or [])
    best_p, best_q = -1, "direct"
    for alias in aliases:
        if not alias.strip():
            continue
        rx = alias_regex(alias)
        for text in (cv_text, cover_text):
            m = rx.search(text)
            if not m:
                continue
            q = _claim_quality(text, m.start(), m.end())
            if QUALITY_PRECEDENCE[q] > best_p:
                best_p, best_q = QUALITY_PRECEDENCE[q], q
    return best_q


def aggregate_categories(reqs: list, must_missing: list, form: str, dz: float) -> tuple:
    """Pure aggregation core (preregistered search space; see
    docs/DEVELOPMENT.md).

    form:
      uniform   - v0: unweighted mean of the category averages
      req_share - category shares from ORIGINAL weights, dz-adjusted averages
      global    - single pooled dz-weighted average (category layer removed)
    dz: zero-evidence weight factor; a requirement with evidence_score == 0.0
      contributes weight * dz (dz = 1.0 reproduces the default behavior).

    Returns (entries, cat_total). entries follow CATEGORY_KEYS order and carry
    the round2-rounded, cap-applied averages exactly as stored in
    results.json; cat_total is computed from those same entries (uniform,
    req_share) or from the pooled dz-weighted average (global, round2 + cap),
    preserving the engine's historical arithmetic order for uniform/dz=1.0."""
    if form not in CATEGORY_WEIGHTING_FORMS:
        raise ValueError(f"unknown category_weighting form: {form!r}")
    dz = min(1.0, max(0.0, float(dz)))
    cap = 0.4 if must_missing else None
    per: dict = {}
    for r in reqs:
        e = r["evidence_score"]
        w = r["weight"] * (dz if e == 0.0 else 1.0)
        a = per.setdefault(r["category"], [0.0, 0.0])  # num_dz, den_dz
        a[0] += e * w
        a[1] += w
    entries = []
    num_t = den_t = 0.0
    for key in CATEGORY_KEYS:
        if key not in per:
            continue
        num_dz, den_dz = per[key]
        avg = (num_dz / den_dz) if den_dz else 0.0
        if cap is not None:
            avg = min(avg, cap)
        entries.append({"category": key, "avg": round2(avg)})
        num_t += num_dz
        den_t += den_dz
    if form == "uniform":
        cat_total = sum(e["avg"] for e in entries) / len(entries) if entries else 0.0
    elif form == "req_share":
        w_orig: dict = {}
        for r in reqs:
            w_orig[r["category"]] = w_orig.get(r["category"], 0.0) + r["weight"]
        wsum = sum(w_orig.get(e["category"], 0.0) for e in entries) or 1.0
        cat_total = sum(e["avg"] * w_orig.get(e["category"], 0.0) for e in entries) / wsum
    else:  # global
        pooled = (num_t / den_t) if den_t else 0.0
        if cap is not None:
            pooled = min(pooled, cap)
        cat_total = round2(pooled)
    return entries, cat_total


def values_fit_score(values_text: str, cv_text: str, cover_text: str) -> tuple:
    phrases = [p.strip() for p in re.split(r"[;,\n]", values_text or "") if len(p.strip()) >= 3]
    if not phrases:
        return None, []
    corpus = set(tokenize(cv_text)) | set(tokenize(cover_text))
    # E1: fold German value terms onto their English counterparts so a German
    # cover letter is scored on equal footing with an English one
    corpus |= {syn for syn in (VALUES_TOKEN_SYNONYMS.get(t) for t in corpus) if syn}
    covered, per_phrase = [], []
    for phrase in phrases:
        toks = phrase_tokens(phrase)
        if not toks:
            continue
        hit = sum(1 for t in toks if t in corpus) / len(toks)
        per_phrase.append({"phrase": phrase, "coverage": round2(hit)})
        covered.append(hit >= 0.6)
    fit = round2(sum(1.0 for c in covered if c) / len(covered)) if covered else 0.0
    return fit, per_phrase


def aggregate_stage(candidates: list, profile: dict, kernel, floors: dict, audit: list) -> None:
    """Stage 4 - fold per-requirement evidence into one score per candidate.

    Orchestration only - the arithmetic lives in the pure
    aggregate_categories() core above. Sequence per candidate:
      1. must-have pre-pass detects gaps ONCE so the 0.4 cap applies
         uniformly to every category (order-independent);
      2. aggregate_categories() builds the six category averages and
         categories_total under the profile's aggregation form;
      3. the kernel's score primitive rates each category (advisory -
         escalates below the 0.80 floor but never overrules evidence);
      4. values fit + the weighted mix produce `overall` (0-100).
    The effective aggregation config is recorded per run in the results
    provenance block (see aggregation_config)."""
    values_text = profile.get("company", {}).get("values_text", "") or ""
    weights_overall = profile.get("weights") or {"categories_total": 0.85, "values_fit": 0.15}
    agg = aggregation_config(profile)
    for cand in candidates:
        cv_text = cand["texts"].get("cv", "")
        cover_text = cand["texts"].get("cover", "")
        combined = clamp_context(cv_text, cover_text)
        # Must-have gaps are detected in ONE pre-pass over all requirements so
        # the 0.4 cap applies uniformly to every category (an incremental
        # per-category detection made the cap order-dependent).
        cand["must_have_missing"] = [r["skill"] for r in cand["requirements"]
                                     if r["must_have"] and r["evidence_score"] < 0.4]
        entries, cat_total = aggregate_categories(
            cand["requirements"], cand["must_have_missing"],
            agg["category_weighting"], agg["zero_weight_factor"],
        )
        cand["categories"] = []
        advisory_categories = []
        for entry in entries:
            cat_key = entry["category"]
            cat_label = CATEGORY_KEYS[cat_key]
            rubric = {"none": "no credible evidence found", "partial": "some indirect evidence", "good": "clear evidence", "strong": "repeated, concrete evidence"}
            payload = kernel.evaluate_score(
                f"Rate the strength of evidence for {cat_label} requirements of this role.",
                rubric,
                combined,
            )
            conf = float(payload["confidence"])
            advisory = should_escalate("score", conf, floors=floors)
            if advisory:
                advisory_categories.append(cat_label)
            cand["categories"].append({
                "category": cat_key,
                "label": cat_label,
                "avg": entry["avg"],
                "kernel_score_confidence": conf,
                "kernel_score_result": payload.get("result"),
                "score_advisory": advisory,
            })
        if advisory_categories:
            rec = escalation_record("score", cand["categories"][0]["kernel_score_confidence"], floors=floors)
            rec.update({
                "kind": "score_advisory",
                "candidate_ref": cand["candidate_ref"],
                "blocking": False,
                "detail": (
                    f"Score primitive below floor {floors['score']:.2f} for "
                    f"{len(advisory_categories)}/{len(cand['categories'])} categories "
                    f"({', '.join(advisory_categories)}) - kernel ratings are advisory only"
                ),
            })
            audit.append(rec)
        fit, per_phrase = values_fit_score(values_text, cv_text, cover_text)
        # Final score: weighted mix of requirement evidence (categories_total)
        # and company-values fit. The must-have cap is the anti-keyword-stuffing
        # guard: a candidate missing ANY must-have requirement cannot score
        # above 40/100 regardless of optional-evidence strength.
        overall_raw = weights_overall.get("categories_total", 0.85) * cat_total + weights_overall.get("values_fit", 0.15) * (fit or 0.0)
        if cand["must_have_missing"]:
            overall_raw = min(overall_raw, 0.40)
        cand["values_fit"] = fit
        cand["values_per_phrase"] = per_phrase
        cand["overall"] = round1(100.0 * overall_raw)
        cand["band"] = band_word(cand["overall"])


# --------------------------------------------------------------------------- #
# stage 5: choice (shortlist), compare (tie-break), rank (advisory order)
# --------------------------------------------------------------------------- #

def top_evidence_lines(cand: dict, limit: int = 6) -> str:
    reqs = sorted(cand["requirements"], key=lambda r: (-r["evidence_score"], r["id"]))
    lines = []
    for r in reqs[:limit]:
        lines.append(f"{r['skill']}: {r['level']} evidence ({r['evidence_score']:.2f})" + (f" - e.g. {r['snippets'][0]}" if r["snippets"] else ""))
    return "\n".join(lines)


def decision_stage(candidates: list, profile: dict, kernel, floors: dict, audit: list) -> dict:
    events = {"compare": [], "rank": None}
    job_title = profile.get("job", {}).get("title", "the role")
    for cand in candidates:
        must_note = "all must-have requirements have supporting evidence" if not cand["must_have_missing"] else "MUST-HAVE GAPS: " + ", ".join(cand["must_have_missing"])
        context = clamp_context(
            f"Role: {job_title}\nMust-have status: {must_note}\nOverall evidence score: {cand['overall']}/100\nTop evidence:\n{top_evidence_lines(cand)}",
        )
        payload = kernel.evaluate_choice(
            "Decide whether this candidate should be shortlisted for the role based only on the documented evidence.",
            ["shortlist", "reject"],
            context,
        )
        conf = float(payload["confidence"])
        escalated = should_escalate("choice", conf, floors=floors)
        if escalated:
            rec = escalation_record("choice", conf, floors=floors)
            rec.update({
                "kind": "shortlist_band",
                "candidate_ref": cand["candidate_ref"],
                "blocking": False,
                "detail": f"Choice confidence {conf:.2f} below floor {floors['choice']:.2f} - candidate placed in review band",
            })
            audit.append(rec)
        cand["choice"] = {
            "decision": payload.get("result"),
            "confidence": conf,
            "escalate": escalated,
            "floor": floors["choice"],
            "kernel": kernel_subset(payload),
        }
        cand["shortlisted"] = payload.get("result") == "shortlist" and not cand["must_have_missing"]

    provisional = sorted(candidates, key=lambda c: (-c["overall"], c["candidate_ref"]))
    labels = {c["candidate_ref"]: c["folder_name"] for c in candidates}
    for i in range(len(provisional) - 1):
        a, b = provisional[i], provisional[i + 1]
        gap = a["overall"] - b["overall"]
        if gap >= COMPARE_EPSILON:
            continue
        pair_ctx = clamp_context(
            f"Role: {job_title}\nCandidate A evidence:\n{top_evidence_lines(a)}\n\nCandidate B evidence:\n{top_evidence_lines(b)}"
        )
        payload = kernel.evaluate_compare(
            "Decide which candidate shows stronger documented evidence for this role.",
            ["A", "B"],
            pair_ctx,
        )
        conf = float(payload["confidence"])
        escalated = should_escalate("compare", conf, floors=floors)
        event = {
            "pair": [a["candidate_ref"], b["candidate_ref"]],
            "gap": round2(gap),
            "decision": payload.get("result"),
            "confidence": conf,
            "floor": floors["compare"],
            "escalate": escalated,
            "applied": False,
        }
        if escalated:
            rec = escalation_record("compare", conf, floors=floors)
            rec.update({
                "kind": "tie_unresolved",
                "candidate_ref": a["candidate_ref"],
                "blocking": False,
                # pseudonymous refs, never folder names: review-queue details
                # are rendered into the exported PDFs
                "detail": f"Near-tie ({gap:.1f} pts) between {a['candidate_ref']} and {b['candidate_ref']} - human tie-break recommended",
            })
            audit.append(rec)
        elif payload.get("result") not in ("A", "B"):
            # D6: a kernel verdict outside {A, B} (e.g. "tie" at full
            # confidence) leaves the pair order unchanged - but the human must
            # still be nudged, so record it even though the floor passed
            rec = escalation_record("compare", conf, floors=floors)
            rec.update({
                "kind": "tie_unresolved",
                "candidate_ref": a["candidate_ref"],
                "blocking": False,
                "detail": f"Compare primitive returned '{payload.get('result')}' for the {gap:.1f}-point near-tie "
                          f"between {a['candidate_ref']} and {b['candidate_ref']} - human tie-break recommended",
            })
            audit.append(rec)
        elif payload.get("result") == "B":
            event["applied"] = True
            ai, bi = provisional.index(a), provisional.index(b)
            provisional[ai], provisional[bi] = provisional[bi], provisional[ai]
        events["compare"].append(event)

    top = provisional[:RANK_TOP_N]
    if len(top) >= 2:
        order_before = [c["candidate_ref"] for c in top]
        payload = kernel.evaluate_rank(
            "Rank these candidates by the strength of their documented evidence for the role (best first).",
            [f"{labels[ref]}" for ref in order_before],
            clamp_context("\n\n".join(
                f"{labels[ref]}: overall {next(c['overall'] for c in candidates if c['candidate_ref'] == ref)}/100, "
                f"band {next(c['band'] for c in candidates if c['candidate_ref'] == ref)}"
                for ref in order_before
            )),
        )
        conf = float(payload["confidence"])
        escalated = should_escalate("rank", conf, floors=floors)
        ranked_refs = []
        for token in re.split(r">", str(payload.get("result") or "")):
            name = token.strip()
            for ref, label in labels.items():
                if label == name and ref not in ranked_refs:
                    ranked_refs.append(ref)
                    break
        conflict = [r for r in ranked_refs if r in order_before and ranked_refs.index(r) != order_before.index(r)] if ranked_refs else order_before
        events["rank"] = {
            "candidates": order_before,
            "decision": payload.get("result"),
            "confidence": conf,
            "floor": floors["rank"],
            "escalate": escalated,
            "order_conflict": bool(conflict),
        }
        if escalated or events["rank"]["order_conflict"]:
            rec = escalation_record("rank", conf, floors=floors)
            rec.update({
                "kind": "rank_conflict" if events["rank"]["order_conflict"] else "rank_advisory",
                "candidate_ref": order_before[0],
                "blocking": False,
                "detail": "Rank advisory disagrees with the computed order - human review of the top ranking recommended",
                "kernel_order": payload.get("result"),
            })
            audit.append(rec)
    return events


# --------------------------------------------------------------------------- #
# stage 6: overall assessment text (deterministic, explainable)
# --------------------------------------------------------------------------- #

def overall_assessment(cand: dict, profile: dict, events: dict) -> str:
    job_title = profile.get("job", {}).get("title", "the role")
    company = profile.get("company", {}).get("name", "the company")
    strengths = sorted(cand["requirements"], key=lambda r: (-r["evidence_score"], r["id"]))[:3]
    gaps = [r for r in sorted(cand["requirements"], key=lambda r: (r["evidence_score"], r["id"])) if r["evidence_score"] < 0.4][:3]
    parts = []
    parts.append(
        f"Against the {job_title} requirements at {company}, this candidate lands in the '{cand['band']}' band "
        f"with an overall evidence score of {cand['overall']:.1f}/100."
    )
    if cand["must_have_missing"]:
        parts.append("Must-have gaps were detected for: " + ", ".join(cand["must_have_missing"]) + ". The score is capped until these are resolved in manual review.")
    else:
        parts.append("All must-have requirements have at least partial supporting evidence in the submitted documents.")
    if strengths:
        parts.append("Strongest evidence: " + "; ".join(f"{r['skill']} ({r['level']})" for r in strengths) + ".")
    if gaps:
        parts.append("Main gaps: " + "; ".join(f"{r['skill']} (no clear match found)" for r in gaps) + ".")
    if cand.get("values_fit") is not None:
        parts.append(f"Alignment with the stated company values is {int(round(100 * cand['values_fit']))}% of value phrases covered.")
    choice = cand.get("choice") or {}
    if choice:
        parts.append(
            f"The shortlist decision primitive returned '{choice.get('decision')}' at confidence {choice.get('confidence', 0):.2f}"
            + (" - below the calibrated floor, so this candidate is placed in the review band." if choice.get("escalate") else ".")
        )
    noul_blocking = any(g.get("blocking") and g["role"] == "cv" for g in cand.get("noul_gates", []))
    if noul_blocking:
        parts.append("WARNING: one or more documents could not be read automatically; this assessment is incomplete and manual review is required before any rejection.")
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# stage 6b: applicant profile enrichment (deterministic, explainable regexes)
# --------------------------------------------------------------------------- #

# "present" in date ranges resolves to the pinned REFERENCE_YEAR (see constants).


def split_sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if len(s.strip()) >= 15]


def detect_education(cv_text: str) -> list:
    """One entry per degree family (highest first), with a short evidence fragment."""
    lowered = cv_text.lower()
    found = []
    for family, keywords in DEGREE_FAMILIES:
        for kw in keywords:
            idx = lowered.find(kw)
            if idx == -1:
                continue
            start = max(0, idx - 40)
            detail = re.sub(r"\s+", " ", cv_text[start:idx + len(kw) + 40].replace("\n", " ")).strip()
            found.append({"level": family, "detail": redact(detail)[:100]})
            break
    return found[:4]


def detect_languages(cv_text: str, cover_text: str) -> list:
    """Match '<language> ... <level>' or '<level> ... <language>' spans (max 30 chars apart)."""
    flat = re.sub(r"\s+", " ", ((cv_text or "") + "\n" + (cover_text or "")).lower())
    lang_pattern = "|".join(sorted(set(CANONICAL_LANGUAGES) | set(LANG_ALIASES), key=len, reverse=True))
    lvl_pattern = "|".join(lvl for _, lvls in LEVEL_BANDS for lvl in lvls)
    rx = re.compile(
        rf"\b({lang_pattern})\b[^.;:!:]{{0,30}}?\b({lvl_pattern})\b"
        rf"|\b({lvl_pattern})\b[^.;:!:]{{0,30}}?\b({lang_pattern})\b"
    )
    out, seen = [], set()
    for m in rx.finditer(flat):
        lang_raw, lvl_raw = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        lang = LANG_ALIASES.get(lang_raw, lang_raw)
        band = next((b for b, lvls in LEVEL_BANDS if lvl_raw in lvls), None)
        if not lang or band is None or (lang, band) in seen:
            continue
        seen.add((lang, band))
        out.append({"language": lang, "level": lvl_raw, "band": band})
    return out[:6]


def detect_timeline(cv_text: str) -> list:
    spans, seen = [], set()
    for m in YEAR_RANGE_RE.finditer(cv_text):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else None
        if not 1950 <= start <= 2100:
            continue
        if end is not None and (end < start or end - start > 45):
            continue
        span = f"{start}-{m.group(2) or 'present'}"
        if span in seen:
            continue
        seen.add(span)
        months = ((end or REFERENCE_YEAR) - start) * 12
        spans.append({"start": start, "end": end, "span": span, "months": months})
    spans.sort(key=lambda s: (s["start"], s["span"]))
    return spans


def merge_intervals(spans: list) -> list:
    merged = []
    for s in spans:
        end = s["end"] or REFERENCE_YEAR
        if merged and s["start"] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([s["start"], end])
    return merged


def estimate_experience(cv_text: str, spans: list) -> tuple:
    """Explicit 'X years' statements win; otherwise merged, deduplicated date ranges.

    D1/D2: date-range spans are already measured in YEARS, so they are
    summed directly (the former /12.0 divisor understated them 12x); explicit
    statements accept decimals ("6.5 years" used to parse as "5 years").
    """
    explicit = []
    for m in YEARS_RE.finditer(cv_text):
        try:
            value = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        if 1 <= value <= 45:
            explicit.append(value)
    if explicit:
        return round2(max(explicit)), "explicit_statement"
    merged = merge_intervals(spans)
    years = round2(sum(e - s for s, e in merged))
    if years > 0:
        return years, "date_ranges"
    return None, "not_detected"


def estimate_seniority(cv_text: str, years) -> tuple:
    """E2: keyword matches are checked per occurrence - a keyword that
    only appears on a CLOSED employment line ("Junior Developer (2017-2020)")
    describes a past title and is skipped, so the estimate reflects the current
    role (or falls through to the experience-based rule)."""
    lowered = cv_text.lower()

    def current_role_hit(scope: str) -> tuple | None:
        for label, keywords in SENIORITY_KEYWORDS:
            for kw in keywords:
                pos = scope.find(kw)
                if pos == -1:
                    continue
                start = lowered.rfind("\n", 0, pos) + 1
                end = lowered.find("\n", pos)
                line = lowered[start:end if end != -1 else len(lowered)]
                if CLOSED_RANGE_RE.search(line):
                    continue  # past title - keep scanning
                return label, kw
        return None

    for scope, suffix in ((lowered[:600], ""), (lowered, " in body text")):
        hit = current_role_hit(scope)
        if hit:
            label, kw = hit
            return label, f"title keyword '{kw.strip('.')}'" + suffix
    if years is not None:
        if years >= 8:
            return "senior", ">= 8 years of detected experience"
        if years >= 4:
            return "mid-level", ">= 4 years of detected experience"
        if years >= 1:
            return "junior", ">= 1 year of detected experience"
    return "unknown", None


def tenure_metrics(spans: list) -> dict | None:
    """Stability estimate from the detected employment spans (closed + open)."""
    if not spans:
        return None
    months = [s["months"] for s in spans]
    return {"positions": len(spans),
            "avg_months": round2(sum(months) / len(months)),
            "longest_months": max(months)}


def detect_achievements(cv_text: str, cover_text: str) -> list:
    scored = []
    for pos, sent in enumerate(split_sentences((cv_text or "") + "\n" + (cover_text or ""))):
        if len(sent) > 280 or not re.search(r"\d", sent):
            continue
        low = sent.lower()
        score = 1
        if "%" in sent or "percent" in low:
            score += 3
        if re.search(r"[\u20ac$£]|\beur\b|\busd\b|\bgbp\b", low):
            score += 2
        if any(v in low for v in ACHIEVEMENT_VERBS):
            score += 2
        if score <= 2:
            continue
        scored.append((-score, pos, redact(sent)[:220]))
    scored.sort()
    return [s[2] for s in scored[:ACHIEVEMENT_MAX]]


def detect_certifications(cv_text: str) -> list:
    out, seen = [], set()
    for sent in split_sentences(cv_text):
        low = sent.lower()
        if not any(k in low for k in CERT_KEYWORDS):
            continue
        frag = re.sub(r"\s+", " ", sent).strip()
        if frag.lower() in seen:
            continue
        seen.add(frag.lower())
        out.append(redact(frag)[:120])
        if len(out) >= 5:
            break
    return out


def risk_flags_for(cand: dict, spans: list, cv_text: str, cv_chars: int) -> list:
    flags = []
    short_stints = [s for s in spans if s["end"] is not None and 0 <= s["months"] < 18]
    if len(short_stints) >= 3:
        flags.append({"flag": "frequent_job_changes",
                      "detail": f"{len(short_stints)} employment spans shorter than 18 months detected"})
    ordered = sorted(spans, key=lambda s: s["start"])
    for prev, nxt in zip(ordered, ordered[1:]):
        prev_end = prev["end"] or REFERENCE_YEAR
        overlap = prev_end - nxt["start"]
        if overlap >= 1:
            # D3: overlapping ranges across employers are invisible to
            # a gap-only check - flag them for a mandatory interview probe
            flags.append({"flag": "employment_overlap",
                          "detail": f"employment ranges overlap by {overlap} year(s) "
                                    f"({prev['span']} and {nxt['span']}) - verify concurrent roles or correct the dates"})
            break
    for prev, nxt in zip(ordered, ordered[1:]):
        prev_end = prev["end"] or REFERENCE_YEAR
        gap = nxt["start"] - prev_end
        if gap >= 1:
            flags.append({"flag": "employment_gap",
                          "detail": f"{gap}-year employment gap between {prev['span']} and {nxt['span']}"})
            break
    if not spans and not MONTH_YEAR_RE.search(cv_text) and len(set(BARE_YEAR_RE.findall(cv_text))) < 3:
        flags.append({"flag": "no_dates_detected",
                      "detail": "no employment dates found - tenure cannot be verified"})
    if 0 < cv_chars < SHORT_DOC_CHARS:
        flags.append({"flag": "thin_cv",
                      "detail": f"CV carries only {cv_chars} machine-readable characters - low signal"})
    if any(g["blocking"] and g["role"] == "cv" for g in cand["noul_gates"]):
        flags.append({"flag": "unreadable_cv",
                      "detail": "CV could not be parsed automatically - assessment incomplete"})
    return flags


def skills_inventory_for(cv_text: str, cover_text: str) -> list:
    """Lexicon scan for skills BEYOND the profile requirements (comparison context)."""
    corpus = (cv_text or "") + "\n" + (cover_text or "")
    out = []
    for name, aliases in SKILL_LEXICON:
        hits = sum(len(alias_regex(a).findall(corpus)) for a in aliases)
        if hits > 0:
            out.append({"skill": name, "mentions": hits})
    out.sort(key=lambda s: (-s["mentions"], s["skill"]))
    return out[:INVENTORY_MAX]


def interview_prompts_for(cand: dict) -> list:
    prompts = []
    reqs = sorted(cand["requirements"], key=lambda x: (not x["must_have"], x["evidence_score"], x["id"]))
    for r in reqs:
        if len(prompts) >= PROMPT_MAX:
            break
        if r["must_have"] and r["evidence_score"] < 0.4:
            quality = r.get("claim_quality") or "direct"
            if quality == "aspirational":
                prompts.append(f"Candidate only expresses the intent to learn '{r['skill']}' - probe actual "
                               f"hands-on depth before crediting the must-have.")
            elif quality == "qualified_low":
                prompts.append(f"Self-assessed basic proficiency for must-have '{r['skill']}' - verify with a "
                               f"practical exercise.")
            else:
                prompts.append(f"Probe real depth in '{r['skill']}' - must-have requirement with only "
                               f"{r['level']} evidence ({r['evidence_score']:.2f}).")
        elif not r["must_have"] and r["evidence_score"] < 0.2:
            prompts.append(f"Ask for concrete examples of '{r['skill']}' - no supporting evidence found in the documents.")
    for rf in (cand.get("profile_card") or {}).get("risk_flags", []):
        if len(prompts) >= PROMPT_MAX:
            break
        prompts.append(f"Discuss with the applicant: {rf['detail'].rstrip('.')}.")
    fit = cand.get("values_fit")
    if fit is not None and fit < 0.5 and len(prompts) < PROMPT_MAX:
        prompts.append(f"Explore alignment with the stated company values - only "
                       f"{int(round(100 * fit))}% of value phrases are covered by the documents.")
    return prompts[:PROMPT_MAX]


def profile_stage(candidates: list) -> None:
    for cand in candidates:
        cv_text = cand["texts"].get("cv", "")
        cover_text = cand["texts"].get("cover", "")
        cv_chars = next((f["chars"] for f in cand["files"] if f["role"] == "cv"), 0)
        spans = detect_timeline(cv_text)
        years, basis = estimate_experience(cv_text, spans)
        seniority, signal = estimate_seniority(cv_text, years)
        cand["profile_card"] = {
            "experience_years": years,
            "experience_basis": basis,
            "seniority_estimate": seniority,
            "seniority_signal": signal,
            "education": detect_education(cv_text),
            "languages": detect_languages(cv_text, cover_text),
            "certifications": detect_certifications(cv_text),
            "achievements": detect_achievements(cv_text, cover_text),
            "career_timeline": [{"span": s["span"], "months": s["months"]} for s in spans[:8]],
            "tenure": tenure_metrics(spans),
            "risk_flags": risk_flags_for(cand, spans, cv_text, cv_chars),
        }
        cand["skills_inventory"] = skills_inventory_for(cv_text, cover_text)
        cand["interview_prompts"] = interview_prompts_for(cand)


# --------------------------------------------------------------------------- #
# stage 6c: cohort standing (percentiles + deltas for comparison views)
# --------------------------------------------------------------------------- #

def _percentile(values: list, value: float) -> float:
    n = len(values)
    if n <= 1:
        return 100.0
    return round2(100.0 * sum(1 for v in values if v < value) / (n - 1))


def cohort_stage(candidates: list) -> None:
    if not candidates:
        return
    overalls = [c["overall"] for c in candidates]
    mean_overall = sum(overalls) / len(overalls)
    best = max(overalls)
    for cand in candidates:
        cat_pcts, cat_ranks = {}, {}
        for cat in cand["categories"]:
            key = cat["category"]
            vals = [next(x["avg"] for x in c["categories"] if x["category"] == key)
                    for c in candidates if any(x["category"] == key for x in c["categories"])]
            cat_pcts[key] = _percentile(vals, cat["avg"])
            cat_ranks[key] = 1 + sum(1 for v in vals if v > cat["avg"])
        cand["cohort"] = {
            "percentile_overall": _percentile(overalls, cand["overall"]),
            "delta_vs_mean": round2(cand["overall"] - mean_overall),
            "delta_vs_best": round2(cand["overall"] - best),
            "category_percentile": cat_pcts,
            "category_rank": cat_ranks,
        }


# --------------------------------------------------------------------------- #
# stage 6e: review readiness (verdict summary, score decomposition, tier)
# --------------------------------------------------------------------------- #

def review_stage(candidates: list, profile: dict, floors: dict) -> None:
    """Extend every dossier with the fields a human reviewer needs to act:
    per-requirement verdict counts, a transparent score decomposition,
    evidence-quality metrics, an A/B/C tier and a one-line review note."""
    weights_overall = profile.get("weights") or {"categories_total": 0.85, "values_fit": 0.15}
    w_cats = weights_overall.get("categories_total", 0.85)
    w_vals = weights_overall.get("values_fit", 0.15)
    agg = aggregation_config(profile)
    extract_floor = floors["extract"]
    for cand in candidates:
        reqs = cand["requirements"]
        met = sum(1 for r in reqs if r["verdict"] == "met")
        partial = sum(1 for r in reqs if r["verdict"] == "partial")
        missing = sum(1 for r in reqs if r["verdict"] == "missing")
        mh_total = sum(1 for r in reqs if r["must_have"])
        mh_met = sum(1 for r in reqs if r["must_have"] and r["verdict"] != "missing")
        cand["verdict_summary"] = {
            "met": met,
            "partial": partial,
            "missing": missing,
            "must_have_met": mh_met,
            "must_have_total": mh_total,
            "completeness_pct": round2(100.0 * (met + 0.5 * partial) / len(reqs)) if reqs else 0.0,
        }
        cats = cand["categories"]
        n_cats = len(cats) or 1
        if agg["category_weighting"] == "uniform":
            contributions = [{"category": c["category"], "label": c["label"], "avg": c["avg"],
                              "points": round2(100.0 * w_cats * c["avg"] / n_cats)} for c in cats]
        else:
            dz = agg["zero_weight_factor"]
            w_orig, w_dz = {}, {}
            for r in reqs:
                w_orig[r["category"]] = w_orig.get(r["category"], 0.0) + r["weight"]
                w_dz[r["category"]] = w_dz.get(r["category"], 0.0) + r["weight"] * (dz if r["evidence_score"] == 0.0 else 1.0)
            denom = w_orig if agg["category_weighting"] == "req_share" else w_dz
            denom_total = sum(denom.values()) or 1.0
            contributions = [{"category": c["category"], "label": c["label"], "avg": c["avg"],
                              "points": round2(100.0 * w_cats * c["avg"] * denom.get(c["category"], 0.0) / denom_total)}
                             for c in cats]
        values_points = round2(100.0 * w_vals * (cand.get("values_fit") or 0.0))
        cap_applied = bool(cand["must_have_missing"])
        cand["score_decomposition"] = {
            "weights": {"categories_total": w_cats, "values_fit": w_vals},
            "contributions": contributions,
            "values_fit_points": values_points,
            "sum_points": round2(sum(c["points"] for c in contributions) + values_points),
            "cap_applied": cap_applied,
            "note": ("overall capped at 40 by unresolved must-have gaps (category averages capped at 0.4)"
                     if cap_applied else None),
        }
        backed = sum(1 for r in reqs if r["snippet_support"])
        low_conf = sum(1 for r in reqs if r["extract_confidence"] < extract_floor)
        cand["evidence_quality"] = {
            "avg_evidence": round2(sum(r["evidence_score"] for r in reqs) / len(reqs)) if reqs else 0.0,
            "doc_backed": backed,
            "doc_backed_pct": round(100.0 * backed / len(reqs)) if reqs else 0,
            "low_confidence_extracts": low_conf,
            "requirements_total": len(reqs),
        }
        if cand["shortlisted"]:
            tier = "A"
        elif cand["overall"] >= 45.0:
            tier = "B"
        else:
            tier = "C"
        cand["tier"] = tier
        cand["review_note"] = review_note_for(cand, tier)


def review_note_for(cand: dict, tier: str) -> str:
    """Deterministic one-line placement rationale for the review workflow."""
    reqs = cand["requirements"]
    vs = cand["verdict_summary"]
    cats = cand["categories"]
    top_cat = max(cats, key=lambda c: c["avg"])["label"] if cats else None
    risks = (cand.get("profile_card") or {}).get("risk_flags") or []
    pct = (cand.get("cohort") or {}).get("percentile_overall")
    unreadable = any(g["blocking"] and g["role"] == "cv" for g in cand["noul_gates"])
    if unreadable:
        head = "assessment incomplete - CV could not be parsed, manual review required before any rejection"
    elif cand["shortlisted"]:
        head = (f"shortlisted - {vs['must_have_met']}/{vs['must_have_total']} must-haves evidenced"
                + (f", strongest in {top_cat}" if top_cat else ""))
    elif cand["must_have_missing"]:
        head = "below the shortlist bar - unresolved must-have gaps: " + ", ".join(cand["must_have_missing"])
    elif cand["overall"] >= 45.0:
        head = "review band - no must-have gaps but evidence depth below the shortlist threshold"
    else:
        head = f"weak match - only {vs['met']}/{len(reqs)} requirements met"
    bits = [head]
    if pct is not None and not unreadable:
        bits.append(f"percentile {pct:.0f} in this cohort")
    if risks:
        bits.append(f"{len(risks)} risk flag(s) to verify")
    return "; ".join(bits) + "."


# --------------------------------------------------------------------------- #
# stage 6d: position-level comparison (leaders, matrix, verdict)
# --------------------------------------------------------------------------- #

def comparison_stage(candidates: list, ranking: list, requirements: list, events: dict) -> dict:
    by_ref = {c["candidate_ref"]: c for c in candidates}
    best = by_ref[ranking[0]] if ranking else None
    second = by_ref[ranking[1]] if len(ranking) >= 2 else None

    leaders = []
    for key, label in CATEGORY_KEYS.items():
        rows = []
        for c in candidates:
            avg = next((x["avg"] for x in c["categories"] if x["category"] == key), None)
            if avg is not None:
                rows.append((avg, -c["rank"], c["candidate_ref"]))
        if rows:
            avg, _, ref = max(rows)
            leaders.append({"category": key, "label": label, "leader_ref": ref, "avg": avg})

    matrix_rows = []
    for r in requirements:
        scores = {c["candidate_ref"]: next((x["evidence_score"] for x in c["requirements"] if x["id"] == r["id"]), None)
                  for c in candidates}
        matrix_rows.append({"id": r["id"], "skill": r["skill"], "category": r["category"],
                            "category_label": r["category_label"], "must_have": r["must_have"], "scores": scores})

    differentiators = []
    for row in matrix_rows:
        vals = [v for v in row["scores"].values() if v is not None]
        if not vals:
            continue
        leader_ref = max(row["scores"], key=lambda ref: (row["scores"][ref], -by_ref[ref]["rank"]))
        top_score = row["scores"][leader_ref]
        mean = sum(vals) / len(vals)
        if top_score >= 0.6 and mean <= 0.4:
            differentiators.append({"skill": row["skill"], "leader_ref": leader_ref,
                                    "leader_score": top_score, "cohort_mean": round2(mean),
                                    "edge": round2(top_score - mean)})
    differentiators.sort(key=lambda d: (-d["edge"], d["skill"]))
    differentiators = differentiators[:6]

    # market gaps: requirements where even the BEST applicant shows weak evidence
    market_gaps = []
    for row in matrix_rows:
        scored = [(v, ref) for ref, v in row["scores"].items() if v is not None]
        if not scored:
            continue
        best_score, best_ref = max(scored)
        if best_score < 0.6:
            market_gaps.append({"skill": row["skill"], "category_label": row["category_label"],
                                "must_have": row["must_have"], "best_score": best_score,
                                "best_ref": best_ref,
                                "n_with_evidence": sum(1 for v, _ in scored if v >= 0.4)})
    market_gaps.sort(key=lambda g: (not g["must_have"], g["best_score"], g["skill"]))
    market_gaps = market_gaps[:8]

    # bench strength per category: how many applicants are strong / capable / thin
    bench = []
    for key, label in CATEGORY_KEYS.items():
        avgs = [x["avg"] for c in candidates for x in c["categories"] if x["category"] == key]
        if not avgs:
            continue
        bench.append({"category": key, "label": label, "candidates": len(avgs),
                      "strong": sum(1 for a in avgs if a >= 0.6),
                      "capable": sum(1 for a in avgs if 0.4 <= a < 0.6),
                      "thin": sum(1 for a in avgs if a < 0.4)})

    # unique strengths: requirement skills only ONE applicant demonstrates strongly
    unique_strengths = []
    for row in matrix_rows:
        strong_refs = [ref for ref, v in row["scores"].items() if v is not None and v >= 0.6]
        if len(strong_refs) != 1:
            continue
        slot = next((u for u in unique_strengths if u["ref"] == strong_refs[0]), None)
        if slot is None:
            slot = {"ref": strong_refs[0], "skills": []}
            unique_strengths.append(slot)
        slot["skills"].append(row["skill"])
    for u in unique_strengths:
        u["skills"].sort()
    unique_strengths.sort(key=lambda u: u["ref"])

    head_to_head = None
    if best is not None and second is not None:
        cats = []
        for key, label in CATEGORY_KEYS.items():
            a = next((x["avg"] for x in best["categories"] if x["category"] == key), None)
            b = next((x["avg"] for x in second["categories"] if x["category"] == key), None)
            if a is None and b is None:
                continue
            winner = "tie" if a == b else ("top_pick" if (a or 0.0) > (b or 0.0) else "runner_up")
            cats.append({"category": key, "label": label, "top_pick": a, "runner_up": b, "winner": winner})
        comeback = []
        for row in matrix_rows:
            a = row["scores"].get(best["candidate_ref"])
            b = row["scores"].get(second["candidate_ref"])
            if a is not None and b is not None and b > a + 0.15:
                comeback.append({"skill": row["skill"], "top_pick": a, "runner_up": b})
        comeback.sort(key=lambda d: (-(d["runner_up"] - d["top_pick"]), d["skill"]))
        head_to_head = {
            "top_pick_ref": best["candidate_ref"],
            "runner_up_ref": second["candidate_ref"],
            "overall": {"top_pick": best["overall"], "runner_up": second["overall"],
                        "gap": round2(best["overall"] - second["overall"])},
            "categories": cats,
            "runner_up_advantages": comeback[:5],
        }

    verdict = None
    if best is not None:
        blocking = any(g["blocking"] for g in best["noul_gates"])
        margin = round2(best["overall"] - second["overall"]) if second is not None else None
        if blocking:
            recommendation = "blocked_manual_review"
        elif best["shortlisted"] and (margin is None or margin >= 5.0):
            recommendation = "strong_front_runner"
        elif best["shortlisted"]:
            recommendation = "proceed_to_interview"
        elif best["overall"] >= 45.0:
            recommendation = "hold_review"
        else:
            recommendation = "no_strong_match_this_round"
        card = best.get("profile_card") or {}
        if second is not None:
            parts = [f"The top-ranked candidate scores {best['overall']:.1f}/100 ({best['band']} band) "
                     f"and leads the runner-up by {margin:.1f} points."]
        else:
            parts = [f"The top-ranked candidate scores {best['overall']:.1f}/100 ({best['band']} band) "
                     "- the only evaluated candidate."]
        parts.append("Unresolved must-have gaps: " + ", ".join(best["must_have_missing"]) + "."
                     if best["must_have_missing"] else
                     "All must-have requirements show at least partial evidence.")
        if best.get("strengths"):
            parts.append("Strongest documented evidence: " + ", ".join(best["strengths"]) + ".")
        pick_edges = [d for d in differentiators if d["leader_ref"] == best["candidate_ref"]]
        if pick_edges:
            parts.append("Key differentiators vs the field: "
                         + ", ".join(d["skill"] for d in pick_edges[:3]) + ".")
        if card.get("seniority_estimate") not in (None, "unknown"):
            exp = (f", around {card['experience_years']:.0f} years of experience"
                   if card.get("experience_years") is not None else "")
            parts.append(f"Profile signals suggest a {card['seniority_estimate']} profile{exp}.")
        if card.get("risk_flags"):
            parts.append("Caution: " + "; ".join(f["detail"].rstrip(".") for f in card["risk_flags"][:2]) + ".")
        if blocking:
            parts.append("WARNING: the top-ranked CV could not be parsed automatically - "
                         "manual review is required before any decision.")
        rank_ev = events.get("rank") or {}
        if rank_ev.get("escalate") or rank_ev.get("order_conflict"):
            parts.append("Note: the rank primitive flagged the advisory order - human review of the "
                         "top ranking is recommended.")
        elif any(ev.get("escalate") for ev in events.get("compare", [])):
            parts.append("Note: at least one near-tie could not be resolved confidently - human tie-break advised.")
        verdict = {
            "recommendation": recommendation,
            "top_pick_ref": best["candidate_ref"],
            "runner_up_ref": second["candidate_ref"] if second is not None else None,
            "margin_to_runner_up": margin,
            "rationale": " ".join(parts),
            "order_note": (f"rank advisory confidence {float(rank_ev.get('confidence') or 0):.2f}"
                           + (" - order conflict flagged" if rank_ev.get("order_conflict") else ""))
                          if rank_ev else None,
            "next_steps": next_steps_for(recommendation, best, second, market_gaps, head_to_head),
        }
    return {
        "candidates_order": list(ranking),
        "category_leaders": leaders,
        "skill_coverage_matrix": matrix_rows,
        "differentiators": differentiators,
        "head_to_head": head_to_head,
        "market_gaps": market_gaps,
        "bench": bench,
        "unique_strengths": unique_strengths,
        "verdict": verdict,
    }


def next_steps_for(recommendation: str, best, second, market_gaps: list, head_to_head) -> list:
    """Deterministic, actionable checklist attached to the position verdict."""
    steps = []
    if recommendation in ("strong_front_runner", "proceed_to_interview"):
        if market_gaps:
            steps.append("Probe the cohort-wide evidence gaps first in every interview: "
                         + ", ".join(g["skill"] for g in market_gaps[:3]) + ".")
        if second is not None and head_to_head and head_to_head.get("runner_up_advantages"):
            steps.append(f"Give candidate {second['candidate_ref']} a structured interview before deciding - "
                         "they lead on: " + ", ".join(a["skill"] for a in head_to_head["runner_up_advantages"][:2]) + ".")
        steps.append(f"Proceed with candidate {best['candidate_ref']} to the next stage; "
                     "record the human sign-off in the audit trail.")
    elif recommendation == "hold_review":
        steps.append("Manually review the top-ranked dossiers before rejecting anyone - the advisory ranking is not a decision.")
        if market_gaps:
            steps.append("No applicant fully demonstrates: " + ", ".join(g["skill"] for g in market_gaps[:3])
                         + " - consider training plans or revising the requirement.")
    elif recommendation == "blocked_manual_review":
        steps.append("Re-request readable documents from the blocked applicants, then re-run the screening.")
    else:
        steps.append("No applicant reached the evaluation bar this round - consider re-opening the search "
                     "or revising the requirements.")
        if market_gaps:
            steps.append("Largest cohort-wide gaps: " + ", ".join(g["skill"] for g in market_gaps[:3]) + ".")
    return steps[:5]


# --------------------------------------------------------------------------- #
# statistics
# --------------------------------------------------------------------------- #

def build_statistics(candidates: list) -> dict:
    n = len(candidates)
    readable = sum(1 for c in candidates if any(g["role"] == "cv" and not g["raw_unreadable"] for g in c["noul_gates"]))
    with_cover = sum(1 for c in candidates if c["texts"].get("cover"))
    shortlisted = sum(1 for c in candidates if c["shortlisted"])
    must_complete = sum(1 for c in candidates if not c["must_have_missing"])
    bands = Counter(c["band"] for c in candidates)
    # clamp so a perfect 100.0 lands in the 90-99 bucket instead of vanishing
    hist = Counter(min(int(c["overall"] // 10) * 10, 90) for c in candidates)
    cat_avg = {}
    for cat_key, cat_label in CATEGORY_KEYS.items():
        vals = [next((x["avg"] for x in c["categories"] if x["category"] == cat_key), None) for c in candidates]
        vals = [v for v in vals if v is not None]
        cat_avg[cat_key] = {"label": cat_label, "avg": round2(sum(vals) / len(vals)) if vals else None}
    req_coverage = {}
    for c in candidates:
        for r in c["requirements"]:
            slot = req_coverage.setdefault(r["id"], {"skill": r["skill"], "category": r["category"], "covered": 0, "n": 0})
            slot["n"] += 1
            if r["evidence_score"] >= 0.4:
                slot["covered"] += 1
    for slot in req_coverage.values():
        slot["coverage_pct"] = round(100.0 * slot["covered"] / slot["n"]) if slot["n"] else 0
    seniority = Counter((c.get("profile_card") or {}).get("seniority_estimate") or "unknown" for c in candidates)
    exps = [c["profile_card"]["experience_years"] for c in candidates
            if c.get("profile_card") and c["profile_card"].get("experience_years") is not None]
    tiers = Counter(c.get("tier") or ("A" if c["shortlisted"] else ("B" if c["overall"] >= 45.0 else "C"))
                    for c in candidates)
    skill_counts = Counter()
    for c in candidates:
        for s in (c.get("skills_inventory") or []):
            skill_counts[s["skill"]] += 1
    edu_dist = Counter(((c.get("profile_card") or {}).get("education") or [{}])[0].get("level", "none")
                       for c in candidates)
    lang_counts = Counter(l["language"] for c in candidates
                          for l in ((c.get("profile_card") or {}).get("languages") or []))
    exps_sorted = sorted(exps)
    if exps_sorted:
        mid = len(exps_sorted) // 2
        median_exp = round2(exps_sorted[mid]) if len(exps_sorted) % 2 else round2((exps_sorted[mid - 1] + exps_sorted[mid]) / 2.0)
    else:
        median_exp = None
    return {
        "candidates_total": n,
        "readable_cv": readable,
        "with_cover_letter": with_cover,
        "must_have_complete": must_complete,
        "shortlisted": shortlisted,
        "funnel": [
            {"stage": "Applications received", "count": n},
            {"stage": "Readable CV", "count": readable},
            {"stage": "Must-have complete", "count": must_complete},
            {"stage": "Shortlisted", "count": shortlisted},
        ],
        "bands": dict(bands),
        "score_histogram": [{"bucket": f"{b}-{b + 9}", "count": hist.get(b, 0)} for b in range(0, 100, 10)],
        "category_averages": cat_avg,
        "requirement_coverage": sorted(req_coverage.values(), key=lambda s: (s["category"], s["skill"])),
        "average_overall": round2(sum(c["overall"] for c in candidates) / n) if n else 0.0,
        "seniority_distribution": dict(sorted(seniority.items())),
        "average_experience_years": round2(sum(exps) / len(exps)) if exps else None,
        "candidates_with_risk_flags": sum(1 for c in candidates if (c.get("profile_card") or {}).get("risk_flags")),
        "tiers": {"A": tiers.get("A", 0), "B": tiers.get("B", 0), "C": tiers.get("C", 0)},
        "talent_pool": {
            "common_skills": [{"skill": k, "count": v, "pct": round(100.0 * v / n) if n else 0}
                              for k, v in skill_counts.most_common(8)],
            "education_distribution": dict(sorted(edu_dist.items())),
            "languages_distribution": [{"language": k, "count": v} for k, v in lang_counts.most_common(6)],
            "median_experience_years": median_exp,
            "avg_skills_per_candidate": round2(sum(len(c.get("skills_inventory") or []) for c in candidates) / n) if n else 0.0,
        },
    }


def build_review_queue(candidates: list, audit: list) -> list:
    queue = []
    for rec in audit:
        queue.append({
            "kind": rec.get("kind"),
            "primitive": rec.get("primitive"),
            "candidate_ref": rec.get("candidate_ref"),
            "blocking": rec.get("blocking", False),
            "detail": rec.get("detail"),
            "confidence": rec.get("confidence"),
            "floor": rec.get("floor"),
        })
    return sorted(queue, key=lambda q: (not q["blocking"], q["candidate_ref"] or "", q["kind"] or ""))


# --------------------------------------------------------------------------- #
# pipeline driver (runs twice for the determinism guarantee)
# --------------------------------------------------------------------------- #

def run_pipeline(profile: dict, folder: Path, options: dict, run_salt: str) -> dict:
    kernel = DeterministicDecisionKernel(use_cuda=False, **kernel_language_kwargs())
    floors = options["floors"]
    audit: list = []
    candidates, scan_notes = scan_candidates(folder, options.get("role_overrides") or {}, run_salt)
    extract_and_gate(candidates, kernel, floors, audit)
    requirements = collect_requirements(profile)
    if not requirements:
        raise ValueError("job profile contains no requirements - nothing to screen")
    evidence_stage(candidates, requirements, kernel, floors, audit, tuned=options.get("tuned"))
    aggregate_stage(candidates, profile, kernel, floors, audit)
    events = decision_stage(candidates, profile, kernel, floors, audit)
    for cand in candidates:
        cand["overall_assessment"] = overall_assessment(cand, profile, events)
    ranking = [c["candidate_ref"] for c in sorted(candidates, key=lambda c: (-c["overall"], c["candidate_ref"]))]
    by_ref = {c["candidate_ref"]: c for c in candidates}
    for cand in candidates:
        cand["rank"] = ranking.index(cand["candidate_ref"]) + 1
        cand["strengths"] = [r["skill"] for r in sorted(cand["requirements"], key=lambda r: (-r["evidence_score"], r["id"]))[:3]]
        cand["gaps"] = [r["skill"] for r in sorted(cand["requirements"], key=lambda r: (r["evidence_score"], r["id"])) if r["evidence_score"] < 0.4][:3]
    profile_stage(candidates)
    cohort_stage(candidates)
    review_stage(candidates, profile, options["floors"])
    comparison = comparison_stage(candidates, ranking, requirements, events)
    return {
        "aggregation": aggregation_config(profile),
        "candidates": candidates,
        "ranking": ranking,
        "ranking_labels": [by_ref[ref]["folder_name"] for ref in ranking if ref in by_ref],
        "scan_notes": scan_notes,
        "statistics": build_statistics(candidates),
        "review_queue": build_review_queue(candidates, audit),
        "events": {
            "compare": events["compare"],
            "rank": events["rank"],
        },
        "comparison": comparison,
    }


def strip_volatile(results: dict) -> dict:
    """Remove wall-clock fields so both passes are byte-comparable."""
    clone = json.loads(canonical_json(results))
    for cand in clone.get("candidates", []):
        cand.pop("folder_path", None)
    return clone


def main() -> int:
    global REFERENCE_YEAR
    parser = argparse.ArgumentParser(
        description=f"Job Attune screening engine (local, deterministic, kernel: {ACTIVE_KERNEL_ID})")
    parser.add_argument("--folder", required=True, help="main folder with one sub-folder per candidate")
    parser.add_argument("--profile", required=True, help="job profile JSON path")
    parser.add_argument("--run-dir", required=True, help="output directory for this run")
    parser.add_argument("--floors", default=str(Path(__file__).resolve().parent / "floors_attune.json"))
    parser.add_argument("--salt", default=None, help="deterministic pseudonymisation salt (defaults to run dir name)")
    parser.add_argument("--reference-year", type=int, default=REFERENCE_YEAR,
                        help="wall-clock anchor for open date ranges (pinned for determinism)")
    parser.add_argument("--tuned-evidence", default=None,
                        help="tuned-evidence JSON (fine-tuning overlay): reclassifies "
                             "claim quality for (candidate, requirement) pairs")
    args = parser.parse_args()
    REFERENCE_YEAR = int(args.reference_year)

    run_dir = Path(args.run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    # first progress state: lets the UI distinguish a booting engine from one
    # that crashed before its first report
    write_progress(run_dir, "boot", 2, "Engine starting")
    try:
        folder = Path(args.folder).expanduser().resolve()
        profile = json.loads(Path(args.profile).resolve().read_text(encoding="utf-8"))
        floors_path = Path(args.floors).expanduser().resolve()
        # Fail fast on a malformed floors file: the frozen library's load_floors falls
        # back to 0.40 per primitive, which would silently de-escalate the review queue.
        # A MISSING file keeps the library fallback contract; a file that exists must
        # parse as JSON and define every primitive with a value in [0, 1].
        if floors_path.exists():
            try:
                probe = json.loads(floors_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                write_progress(run_dir, "error", 100,
                               f"Run failed: floors file is not valid JSON: {floors_path.name}")
                raise ValueError(f"floors file {floors_path} is not valid JSON: {exc}") from exc
            table = probe.get("floors", probe) if isinstance(probe, dict) else None
            if not isinstance(table, dict) or not REQUIRED_FLOORS.issubset(table):
                write_progress(run_dir, "error", 100,
                               f"Run failed: floors file must define {sorted(REQUIRED_FLOORS)}: {floors_path.name}")
                raise ValueError(f"floors file {floors_path} must define primitives {sorted(REQUIRED_FLOORS)}")
            bad = {k: v for k, v in table.items()
                   if k in REQUIRED_FLOORS and not (isinstance(v, (int, float)) and not isinstance(v, bool)
                                                    and 0.0 <= float(v) <= 1.0)}
            if bad:
                write_progress(run_dir, "error", 100,
                               f"Run failed: floors values must be numbers in [0, 1]: {sorted(bad)}: {floors_path.name}")
                raise ValueError(f"floors file {floors_path} has invalid values for {sorted(bad)}")
        floors = load_floors(floors_path)  # load ONCE, pass explicitly (hot-path rule)
        tuned = load_tuned_evidence(args.tuned_evidence) if args.tuned_evidence else None
    except Exception as exc:
        # config/IO failures must reach the UI poller too, not just the traceback
        write_progress(run_dir, "error", 100, f"Run failed: {type(exc).__name__}: {exc}")
        raise
    run_salt = args.salt or run_dir.name
    options = {
        "floors": floors,
        "role_overrides": profile.get("role_overrides") or {},
        "pseudonymous": bool(profile.get("pseudonymous", True)),
        "tuned": tuned,
    }

    started = time.perf_counter()
    write_progress(run_dir, "scan", 5, "Scanning candidate folders")
    try:
        results = run_pipeline(profile, folder, options, run_salt)
        write_progress(run_dir, "verify", 88, "Re-running pipeline for determinism check")
        second = strip_volatile(run_pipeline(profile, folder, options, run_salt))
        first = strip_volatile(results)
        h1, h2 = sha256_text(canonical_json(first)), sha256_text(canonical_json(second))
    except Exception as exc:
        # surface the failure to the UI poller instead of leaving a stale "scan" progress
        write_progress(run_dir, "error", 100, f"Run failed: {type(exc).__name__}: {exc}")
        raise
    elapsed = time.perf_counter() - started
    if h1 != h2:
        # the determinism guarantee is enforced, not advisory: a mismatch fails
        # the run (non-zero exit + error progress) instead of shipping silently
        write_progress(run_dir, "error", 100, "Run failed: determinism check failed (pass1 != pass2 sha256)")
        raise RuntimeError("determinism violation: the two pipeline passes produced different outputs")

    # Text-layer provenance: which kernel language pack and text mode
    # produced this run.
    # run_pipeline constructed the kernel with exactly these validated values
    # (a bad code would have failed the run already).
    lang_kwargs = kernel_language_kwargs()
    manifest = {
        "engine_version": ENGINE_VERSION,
        "omnidecide_version": ACTIVE_KERNEL_ID,
        "kernel_text_mode": lang_kwargs.get("text_mode", "ascii"),
        "kernel_language": lang_kwargs.get("language", "und"),
        "floors_data_version": floors_version(floors_path),
        "floors_path": str(floors_path),
        "floors_table": floors,
        "main_folder": str(folder),
        "reference_year": REFERENCE_YEAR,
        "profile_sha256": sha256_text(canonical_json(profile)),
        "file_hashes": {c["folder_name"]: {f["name"]: f["sha256"] for f in c["files"]} for c in results["candidates"]},
        "pseudonymous": options["pseudonymous"],
        "tuned_evidence": (tuned or {}).get("metadata") or None,
        "tuned_overrides_applied": sum(1 for c in results["candidates"]
                                       for r in c.get("requirements", [])
                                       if (r.get("tuned") or {}).get("applied")),
        "determinism": {"pass1_sha256": h1, "pass2_sha256": h2, "identical": h1 == h2},
        "elapsed_seconds": round(elapsed, 3),
        "created_at": now_iso(),
    }
    results["audit"] = {"manifest": manifest}
    results["run_id"] = run_dir.name
    results["created_at"] = manifest["created_at"]
    results["omnidecide_version"] = manifest["omnidecide_version"]
    results["engine_version"] = ENGINE_VERSION
    results["floors_data_version"] = manifest["floors_data_version"]
    results["determinism"] = manifest["determinism"]
    results["profile"] = {
        "title": profile.get("job", {}).get("title", ""),
        "company": profile.get("company", {}).get("name", ""),
    }

    # Data minimisation (GDPR Art. 5(1)(c)): raw document text and candidate-level
    # absolute paths are consumed by the pipeline in-memory only and never
    # persisted; run-level inputs (main_folder, floors_path) are recorded in the
    # local-only manifest for replay.
    # Evidence snippets were already PII-redacted at extraction time; exports and
    # the UI consume redacted evidence, not raw text.
    for cand in results["candidates"]:
        cand.pop("texts", None)
        cand.pop("folder_path", None)

    out = run_dir / "results.json"
    tmp = run_dir / "results.json.tmp"
    tmp.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, out)
    write_progress(run_dir, "done", 100, f"Run complete: {len(results['candidates'])} candidates screened in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
