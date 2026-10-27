# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Job Attune bench baselines - candidate-blind, stdlib-only scoring baselines.

Three baselines benchmarked against the Job Attune engine (see run_bench.py):

  boolean-ats  must-have keyword veto (ATS-style): candidates missing ANY
               must-have requirement are rejected outright; survivors are
               ranked by nice-to-have coverage. Keywords come exclusively
               from the job profile (skills + aliases) - never from the
               candidate documents (candidate-blind guarantee).

  tfidf        TF-IDF cosine similarity between each candidate document bag
               and a profile-derived query bag (skills + aliases + company +
               job strings). Sublinear tf, smoothed idf, engine tokenizer.

  bm25         Okapi BM25 (k1=1.5, b=0.75) over the same corpus/query.

All three are deterministic: identical inputs produce identical scores, and
ties are broken by candidate id at ranking time (run_bench.rank_scores).
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

_ENGINE_PATH = Path(__file__).resolve().parent.parent / "attune-engine" / "engine.py"
_spec = importlib.util.spec_from_file_location("attune_engine", _ENGINE_PATH)
_engine = importlib.util.module_from_spec(_spec)
sys.modules["attune_engine"] = _engine
_spec.loader.exec_module(_engine)


# --------------------------------------------------------------------------- #
# Corpus + query construction (candidate-blind)
# --------------------------------------------------------------------------- #

def load_corpus_texts(folder: Path) -> dict:
    """folder_name -> concatenated text of every PDF in the candidate folder.

    Reuses the engine's own extraction (PyMuPDF preferred, pypdf fallback) so
    all four systems rank exactly the same bytes of text.
    """
    candidates, _notes = _engine.scan_candidates(folder, {}, "bench")
    texts = {}
    for cand in candidates:
        parts = []
        for f in cand.get("files", []):
            info = _engine.extract_pdf_text(folder / f["rel_path"])
            if info.get("text"):
                parts.append(info["text"])
        texts[cand["folder_name"]] = "\n".join(parts)
    return texts


def profile_query_tokens(profile: dict) -> list:
    """Query bag built ONLY from the profile (skills, aliases, company, job)."""
    reqs = _engine.collect_requirements(profile)
    phrases = [r["skill"] for r in reqs]
    phrases += [a for r in reqs for a in r["aliases"]]
    phrases += [str(profile.get("company", "")), str(profile.get("job", ""))]
    tokens = []
    for ph in phrases:
        tokens.extend(_engine.phrase_tokens(ph))
    return tokens


def _requirement_hits(profile: dict, text: str) -> list:
    """Per-requirement boolean hit using the engine's alias regexes."""
    reqs = _engine.collect_requirements(profile)
    hits = []
    for req in reqs:
        patterns = [_engine.alias_regex(req["skill"])] + [_engine.alias_regex(a) for a in req["aliases"]]
        hits.append(any(p.search(text) for p in patterns))
    return hits


# --------------------------------------------------------------------------- #
# boolean-ats
# --------------------------------------------------------------------------- #

def boolean_ats_scores(profile: dict, texts: dict) -> dict:
    """folder_name -> score. Score semantics: passers scored in [1, 2] by
    nice-to-have coverage; rejected candidates scored 0.0."""
    scores = {}
    reqs = _engine.collect_requirements(profile)
    for folder, text in texts.items():
        hits = _requirement_hits(profile, text)
        must = [h for h, r in zip(hits, reqs) if r["must_have"]]
        nice = [h for h, r in zip(hits, reqs) if not r["must_have"]]
        if must and not all(must):
            scores[folder] = 0.0
        else:
            must_cov = (sum(must) / len(must)) if must else 1.0
            nice_frac = (sum(nice) / len(nice)) if nice else 0.0
            scores[folder] = 1.0 + must_cov + nice_frac  # (1, 2]
    return scores


# --------------------------------------------------------------------------- #
# tf-idf + bm25 (shared vectorization)
# --------------------------------------------------------------------------- #

def _doc_tokens(text: str) -> list:
    return _engine.tokenize(text)


def tfidf_scores(profile: dict, texts: dict) -> dict:
    query = _doc_tokens(" ".join(profile_query_tokens(profile)))
    docs = {f: _doc_tokens(t) for f, t in texts.items()}
    ids = sorted(docs)
    N = len(ids) + 1
    df = {}
    for f in ids:
        for term in set(docs[f]):
            df[term] = df.get(term, 0) + 1
    for term in set(query):
        df[term] = df.get(term, 0) + 1

    def idf(term: str) -> float:
        return math.log((1.0 + N) / (1.0 + df.get(term, 0))) + 1.0

    def vec(tokens: list) -> tuple:
        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        norm = 0.0
        out = {}
        for t, c in tf.items():
            w = (1.0 + math.log(c)) * idf(t)
            out[t] = w
            norm += w * w
        return out, math.sqrt(norm)

    qv, qnorm = vec(query)
    scores = {}
    for f in ids:
        dv, dnorm = vec(docs[f])
        dot = sum(w * qv[t] for t, w in dv.items() if t in qv)
        scores[f] = dot / (dnorm * qnorm) if dnorm and qnorm else 0.0
    return scores


def bm25_scores(profile: dict, texts: dict, k1: float = 1.5, b: float = 0.75) -> dict:
    query_terms = sorted(set(_doc_tokens(" ".join(profile_query_tokens(profile)))))
    docs = {f: _doc_tokens(t) for f, t in texts.items()}
    ids = sorted(docs)
    N = len(ids)
    avgdl = (sum(len(docs[f]) for f in ids) / N) if N else 0.0
    df = {}
    for f in ids:
        for term in set(docs[f]):
            df[term] = df.get(term, 0) + 1

    def idf(term: str) -> float:
        n = df.get(term, 0)
        return math.log((N - n + 0.5) / (n + 0.5) + 1.0)

    scores = {}
    for f in ids:
        tf = {}
        for t in docs[f]:
            tf[t] = tf.get(t, 0) + 1
        dl = len(docs[f])
        s = 0.0
        for q in query_terms:
            freq = tf.get(q, 0)
            if not freq:
                continue
            denom = freq + k1 * (1.0 - b + b * dl / avgdl) if avgdl else freq + k1
            s += idf(q) * (freq * (k1 + 1.0)) / denom
        scores[f] = s
    return scores
