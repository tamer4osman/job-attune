#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Job Attune PDF report exports: comprehensive position report + dossiers.

Reads results.json from a run directory and writes pseudonymous-by-default
PDF files under <run-dir>/exports/:

  batch-report.pdf       - full position report: verdict (+ next steps), ranking
                           (best to worst, tiered), category + skill-coverage
                           matrices, bench strength & market gaps, talent pool
                           insights, one dossier section per applicant,
                           methodology & audit appendix
  candidate-<ref>.pdf    - standalone dossier per applicant

100% local (reportlab), English-only, deterministic content (no wall-clock text).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import reportlab.rl_config as rl_config

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Byte-stable PDFs: identical content produces identical bytes (no wall-clock
# /CreationDate), so exports can be hash-verified across re-runs.
rl_config.invariant = 1

ENGINE_EMERALD = colors.Color(0.055, 0.47, 0.33)
SLATE_900 = colors.Color(0.09, 0.13, 0.19)
SLATE_600 = colors.Color(0.38, 0.43, 0.50)
SLATE_100 = colors.Color(0.94, 0.96, 0.97)
AMBER = colors.Color(0.72, 0.45, 0.05)
ROSE = colors.Color(0.72, 0.15, 0.25)
EMERALD_LIGHT = colors.Color(0.87, 0.94, 0.90)
AMBER_LIGHT = colors.Color(0.995, 0.945, 0.82)
ROSE_LIGHT = colors.Color(0.995, 0.905, 0.905)

RECOMMENDATION_LABELS = {
    "strong_front_runner": ("Strong front-runner - proceed to shortlist / offer", ENGINE_EMERALD),
    "proceed_to_interview": ("Proceed to interview", colors.Color(0.10, 0.55, 0.55)),
    "hold_review": ("Hold - manual review before any decision", AMBER),
    "blocked_manual_review": ("Blocked - manual review required (unreadable documents)", ROSE),
    "no_strong_match_this_round": ("No strong match this round", ROSE),
}


def safe(text: str) -> str:
    """Latin-1-safe the text for the base-14 fonts (report content is English)."""
    return str(text).encode("latin-1", "replace").decode("latin-1")


def esc(text: str) -> str:
    return safe(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def folder_name_scrubber(results) -> object:
    """Return a callable replacing candidate folder names with pseudonymous refs.

    Review-queue detail strings are rendered into the exported PDFs; without this
    scrubber a folder name (the applicant's name) leaks through escalation text
    while the report simultaneously claims candidates are pseudonymous.
    """
    pairs = sorted(((c["folder_name"], c["candidate_ref"]) for c in results.get("candidates", [])),
                   key=lambda kv: -len(kv[0]))

    def scrub(text: str) -> str:
        out = str(text)
        for name, ref in pairs:
            if name:
                out = out.replace(name, ref)
        return out

    return scrub


def build_styles():
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=ss["Title"], fontSize=20, textColor=SLATE_900, spaceAfter=2 * mm, alignment=0)
    h2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13, textColor=ENGINE_EMERALD, spaceBefore=5 * mm, spaceAfter=2 * mm, alignment=0)
    h3 = ParagraphStyle("H3", parent=ss["Heading3"], fontSize=10.5, textColor=SLATE_900, spaceBefore=3 * mm, spaceAfter=1.5 * mm, alignment=0)
    body = ParagraphStyle("Body", parent=ss["BodyText"], fontSize=9.5, leading=13, textColor=SLATE_900, alignment=0)
    small = ParagraphStyle("Small", parent=body, fontSize=8, leading=10.5, textColor=SLATE_600)
    cell = ParagraphStyle("Cell", parent=body, fontSize=8.5, leading=11)
    cellsm = ParagraphStyle("CellSm", parent=cell, fontSize=7.5, leading=9)
    return h1, h2, h3, body, small, cell, cellsm


def table(data, widths, align="CENTER", zebra=True, extra_style=None, font_size=8.5):
    t = Table(data, colWidths=widths, hAlign=align, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), SLATE_900),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.Color(0.8, 0.83, 0.86)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if zebra:
        for i in range(1, len(data)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), SLATE_100))
    if extra_style:
        style.extend(extra_style)
    t.setStyle(TableStyle(style))
    return t


def band_color(band: str):
    return {"strong": ENGINE_EMERALD, "good": colors.Color(0.10, 0.55, 0.55), "potential": AMBER}.get(band, ROSE)


def score_cell_color(score) -> colors.Color:
    if score is None:
        return colors.white
    if score >= 0.8:
        return EMERALD_LIGHT
    if score >= 0.4:
        return AMBER_LIGHT
    return ROSE_LIGHT


def header_footer(title):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(ENGINE_EMERALD)
        canvas.rect(0, A4[1] - 14 * mm, A4[0], 14 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(15 * mm, A4[1] - 9 * mm, safe("Job Attune - GDPR-safe resume screening"))
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(A4[0] - 15 * mm, A4[1] - 9 * mm, safe(title))
        canvas.setFillColor(SLATE_600)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(15 * mm, 9 * mm, safe("100% local processing - no data leaves this machine - pseudonymous by default"))
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, safe(f"Page {doc.page}"))
        canvas.restoreState()

    return draw


def label_for(cand, pseudonymous: bool) -> str:
    return f"Candidate {cand['candidate_ref']}" if pseudonymous else safe(cand["folder_name"])


# --------------------------------------------------------------------------- #
# shared dossier building blocks
# --------------------------------------------------------------------------- #

def profile_card_table(cand, cell, cellsm):
    card = cand.get("profile_card") or {}
    years = card.get("experience_years")
    exp_txt = "-" if years is None else f"{years:.1f} yrs ({card.get('experience_basis', 'n/a')})"
    sen = card.get("seniority_estimate") or "unknown"
    if card.get("seniority_signal"):
        sen += f" - {card['seniority_signal']}"
    edu = card.get("education") or []
    edu_txt = "; ".join(f"{e['level']}: {e['detail']}" for e in edu) or "not detected"
    langs = card.get("languages") or []
    lang_txt = "; ".join(f"{l['language']} {l['level']}/{l['band']}" for l in langs) or "not detected"
    certs = card.get("certifications") or []
    cert_txt = "; ".join(certs) or "not detected"
    risks = card.get("risk_flags") or []
    risk_txt = "; ".join(f"{r['flag']}: {r['detail']}" for r in risks) or "none"
    timeline = card.get("career_timeline") or []
    tl_txt = ", ".join(t["span"] for t in timeline) or "no employment spans detected"
    eq = cand.get("evidence_quality") or {}
    eq_txt = (f"avg evidence {eq.get('avg_evidence', 0):.2f}, "
              f"{eq.get('doc_backed', 0)}/{eq.get('requirements_total', 0)} requirements doc-backed, "
              f"{eq.get('low_confidence_extracts', 0)} low-confidence extracts") if eq else "-"
    tenure = card.get("tenure")
    ten_txt = (f"{tenure['positions']} spans, avg {tenure['avg_months']:.0f} mo, "
               f"longest {tenure['longest_months']:.0f} mo") if tenure else "-"
    rows = [
        [Paragraph("<b>Experience</b>", cell), Paragraph(esc(exp_txt), cell),
         Paragraph("<b>Seniority</b>", cell), Paragraph(esc(sen), cellsm)],
        [Paragraph("<b>Education</b>", cell), Paragraph(esc(edu_txt), cellsm),
         Paragraph("<b>Languages</b>", cell), Paragraph(esc(lang_txt), cellsm)],
        [Paragraph("<b>Certifications</b>", cell), Paragraph(esc(cert_txt), cellsm),
         Paragraph("<b>Career spans</b>", cell), Paragraph(esc(tl_txt), cellsm)],
        [Paragraph("<b>Risk flags</b>", cell), Paragraph(esc(risk_txt), cellsm),
         Paragraph("<b>Cohort</b>", cell), Paragraph(esc(cohort_line(cand)), cellsm)],
        [Paragraph("<b>Evidence quality</b>", cell), Paragraph(esc(eq_txt), cellsm),
         Paragraph("<b>Tenure</b>", cell), Paragraph(esc(ten_txt), cellsm)],
    ]
    t = Table(rows, colWidths=[26 * mm, 64 * mm, 26 * mm, 64 * mm], hAlign="CENTER")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.Color(0.8, 0.83, 0.86)),
        ("BACKGROUND", (0, 0), (0, -1), SLATE_100), ("BACKGROUND", (2, 0), (2, -1), SLATE_100),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def cohort_line(cand) -> str:
    ch = cand.get("cohort") or {}
    pct = ch.get("percentile_overall")
    dmean = ch.get("delta_vs_mean")
    parts = []
    if pct is not None:
        parts.append(f"percentile {pct:.0f}")
    if dmean is not None:
        parts.append(f"{dmean:+.1f} pts vs cohort mean")
    return ", ".join(parts) or "-"


def evidence_snippets_table(cand, cell, cellsm, limit=5):
    reqs = sorted(cand["requirements"], key=lambda r: (-r["evidence_score"], r["id"]))
    rows = [[Paragraph("<b>Top evidence</b>", cell), Paragraph("<b>Level</b>", cell), Paragraph("<b>Redacted snippet</b>", cell)]]
    picked = 0
    for r in reqs:
        if picked >= limit:
            break
        if not r["snippets"]:
            continue
        rows.append([
            Paragraph(esc(r["skill"]), cellsm),
            Paragraph(esc(r["level"]), cellsm),
            Paragraph(f"&ldquo;{esc(r['snippets'][0])}&rdquo;", cellsm),
        ])
        picked += 1
    if picked == 0:
        return None
    return table(rows, [40 * mm, 16 * mm, 124 * mm], zebra=True, font_size=7.5)


def dossier_flow(cand, styles, pseudonymous: bool) -> list:
    """Full per-candidate dossier: profile card, prompts, categories, evidence."""
    h3, body, small, cell, cellsm = styles[2], styles[3], styles[4], styles[5], styles[6]
    flow = []
    note = cand.get("review_note")
    if note:
        flow.append(Paragraph(safe(f"<b>Review note (tier {cand.get('tier', '-')}):</b> ") + esc(note), small))
        flow.append(Spacer(1, 1.5 * mm))
    flow.append(profile_card_table(cand, cell, cellsm))
    card = cand.get("profile_card") or {}
    achievements = card.get("achievements") or []
    if achievements:
        flow.append(Paragraph("Quantified achievements (extracted)", h3))
        for a in achievements:
            flow.append(Paragraph(f"&bull; {esc(a)}", small))
    prompts = cand.get("interview_prompts") or []
    if prompts:
        flow.append(Paragraph("Interview prompts for this applicant", h3))
        for i, p in enumerate(prompts, 1):
            flow.append(Paragraph(f"{i}. {esc(p)}", small))
    inv = cand.get("skills_inventory") or []
    if inv:
        flow.append(Paragraph("Skills inventory (lexicon scan beyond the requirements)", h3))
        flow.append(Paragraph(esc(", ".join(f"{s['skill']} ({s['mentions']})" for s in inv)), small))
    flow.append(Paragraph("Category breakdown", h3))
    cat_rows = [[Paragraph("<b>Category</b>", cell), Paragraph("<b>Evidence avg</b>", cell),
                 Paragraph("<b>Cohort rank</b>", cell), Paragraph("<b>Kernel rating</b>", cell), Paragraph("<b>Advisory</b>", cell)]]
    ch = cand.get("cohort") or {}
    for c in cand["categories"]:
        rank = (ch.get("category_rank") or {}).get(c["category"])
        cat_rows.append([
            Paragraph(esc(c["label"]), cell),
            Paragraph(f"{c['avg'] * 100:.0f}%", cell),
            Paragraph(f"#{rank}" if rank else "-", cell),
            Paragraph(esc(str(c.get("kernel_score_result") or "-")), cell),
            Paragraph("below floor" if c.get("score_advisory") else "-", cell),
        ])
    flow.append(table(cat_rows, [52 * mm, 28 * mm, 24 * mm, 46 * mm, 30 * mm]))
    dec = cand.get("score_decomposition") or {}
    if dec.get("contributions"):
        flow.append(Paragraph("Score decomposition (how the overall score is composed)", h3))
        dec_rows = [[Paragraph("<b>Component</b>", cell), Paragraph("<b>Evidence avg</b>", cell),
                     Paragraph("<b>Points of 100</b>", cell)]]
        for c in dec["contributions"]:
            dec_rows.append([Paragraph(esc(c["label"]), cell),
                             Paragraph(f"{c['avg'] * 100:.0f}%", cell),
                             Paragraph(f"{c['points']:.1f}", cell)])
        if dec.get("values_fit_points"):
            dec_rows.append([Paragraph("Company values fit", cell), Paragraph("-", cell),
                             Paragraph(f"{dec['values_fit_points']:.1f}", cell)])
        dec_rows.append([Paragraph("<b>Total</b>", cell), Paragraph("", cell),
                         Paragraph(f"<b>{dec.get('sum_points', 0):.1f}</b>", cell)])
        flow.append(table(dec_rows, [70 * mm, 34 * mm, 30 * mm]))
        if dec.get("note"):
            flow.append(Paragraph(esc(dec["note"]), small))
    flow.append(Paragraph("Requirement evidence", h3))
    req_rows = [[Paragraph("<b>Requirement</b>", cell), Paragraph("<b>Category</b>", cell),
                 Paragraph("<b>Evidence</b>", cell), Paragraph("<b>Level</b>", cell),
                 Paragraph("<b>Verdict</b>", cell), Paragraph("<b>Must-have</b>", cell)]]
    for r in cand["requirements"]:
        req_rows.append([
            Paragraph(esc(r["skill"]), cell),
            Paragraph(esc(r["category_label"]), cell),
            Paragraph(f"{r['evidence_score']:.2f}", cell),
            Paragraph(esc(r["level"]), cell),
            Paragraph(esc(r.get("verdict", "-")), cell),
            Paragraph("yes" if r["must_have"] else "-", cell),
        ])
    flow.append(table(req_rows, [50 * mm, 38 * mm, 20 * mm, 22 * mm, 16 * mm, 18 * mm]))
    snip = evidence_snippets_table(cand, cell, cellsm)
    if snip is not None:
        flow.append(Paragraph("Top evidence snippets (PII redacted)", h3))
        flow.append(snip)
    return flow


# --------------------------------------------------------------------------- #
# position-level sections (batch report only)
# --------------------------------------------------------------------------- #

def verdict_section(results, styles) -> list:
    h2, h3, body, small, cell, cellsm = styles[1], styles[2], styles[3], styles[4], styles[5], styles[6]
    comp = results.get("comparison") or {}
    v = comp.get("verdict")
    if not v:
        return []
    label, color = RECOMMENDATION_LABELS.get(v.get("recommendation"), ("Review recommended", AMBER))
    hexcol = "#%02x%02x%02x" % (int(color.red * 255), int(color.green * 255), int(color.blue * 255))
    rows = [
        [Paragraph("<b>Position verdict</b>", cell),
         Paragraph(f'<b><font color="{hexcol}">{esc(label)}</font></b>', cell)],
    ]
    top = v.get("top_pick_ref") or "-"
    runner = v.get("runner_up_ref") or "-"
    rows.append([
        Paragraph("<b>Top pick / runner-up</b>", cell),
        Paragraph(esc(f"{top} vs {runner}"
                      + (f" (margin {v['margin_to_runner_up']:.1f} pts)" if v.get("margin_to_runner_up") is not None else "")), cell),
    ])
    story = [table(rows, [44 * mm, 136 * mm], zebra=False)]
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(esc(v.get("rationale", "")), body))
    steps = v.get("next_steps") or []
    if steps:
        story.append(Paragraph("<b>Recommended next steps</b>", h3))
        for s in steps:
            story.append(Paragraph(f"&bull; {esc(s)}", small))
    if v.get("order_note"):
        story.append(Paragraph(safe(f"Order confidence: {v['order_note']}"), small))
    return story


def ranking_table(results, styles, pseudonymous: bool) -> Table:
    cell, cellsm = styles[5], styles[6]
    by_ref = {c["candidate_ref"]: c for c in results["candidates"]}
    rows = [[Paragraph("<b>Rank</b>", cell), Paragraph("<b>Candidate</b>", cell), Paragraph("<b>Tier</b>", cell),
             Paragraph("<b>Overall</b>", cell), Paragraph("<b>Band</b>", cell), Paragraph("<b>Pctile</b>", cell),
             Paragraph("<b>Exp</b>", cell), Paragraph("<b>Seniority</b>", cell), Paragraph("<b>Must-have gaps</b>", cell),
             Paragraph("<b>Shortl.</b>", cell)]]
    for i, ref in enumerate(results["ranking"], 1):
        c = by_ref[ref]
        card = c.get("profile_card") or {}
        ch = c.get("cohort") or {}
        years = card.get("experience_years")
        rows.append([
            Paragraph(str(i), cell), Paragraph(esc(label_for(c, pseudonymous)), cell),
            Paragraph(esc(c.get("tier", "-")), cell),
            Paragraph(f"{c['overall']:.1f}", cell), Paragraph(esc(c["band"]), cell),
            Paragraph("-" if ch.get("percentile_overall") is None else f"{ch['percentile_overall']:.0f}", cell),
            Paragraph("-" if years is None else f"{years:.1f}", cell),
            Paragraph(esc(card.get("seniority_estimate") or "unknown"), cellsm),
            Paragraph(esc(", ".join(c["must_have_missing"]) or "-"), cellsm),
            Paragraph("yes" if c["shortlisted"] else "no", cell),
        ])
    return table(rows, [10 * mm, 30 * mm, 9 * mm, 14 * mm, 16 * mm, 12 * mm, 10 * mm, 20 * mm, 42 * mm, 10 * mm], font_size=7.5)


def category_matrix_table(results, styles, pseudonymous: bool) -> Table:
    cell, cellsm = styles[5], styles[6]
    by_ref = {c["candidate_ref"]: c for c in results["candidates"]}
    comp = results.get("comparison") or {}
    # per-column leaders: shade the cell of the category's leader, not the whole
    # row of any candidate who leads somewhere
    leaders_by_cat = {l["category"]: l["leader_ref"] for l in comp.get("category_leaders", [])}
    cat_keys = [l["category"] for l in comp.get("category_leaders", [])]
    if not cat_keys:
        cat_keys = list(next(iter(results["candidates"]), {}).get("categories", [{}])[0].get("category", []) or [])
    header = [Paragraph("<b>Candidate</b>", cell)]
    for key in cat_keys:
        lbl = next((l["label"] for l in comp.get("category_leaders", []) if l["category"] == key), key)
        header.append(Paragraph(f"<b>{esc(lbl)}</b>", cellsm))
    rows = [header]
    extra = []
    for r_i, ref in enumerate(results["ranking"], 1):
        c = by_ref[ref]
        row = [Paragraph(esc(f"#{r_i} {label_for(c, pseudonymous)}"), cellsm)]
        for col_i, key in enumerate(cat_keys, 1):
            avg = next((x["avg"] for x in c["categories"] if x["category"] == key), None)
            val = "-" if avg is None else f"{avg * 100:.0f}%"
            is_leader = leaders_by_cat.get(key) == ref
            row.append(Paragraph(f"<b>{val}</b>" if is_leader else val, cellsm))
            if is_leader:
                extra.append(("BACKGROUND", (col_i, r_i), (col_i, r_i), EMERALD_LIGHT))
        rows.append(row)
    return table(rows, [40 * mm] + [(140.0 / max(len(cat_keys), 1)) * mm] * len(cat_keys),
                 zebra=True, extra_style=extra, font_size=7.5)


def coverage_matrix_tables(results, styles, pseudonymous: bool, chunk: int = 10) -> list:
    cell, cellsm = styles[5], styles[6]
    comp = results.get("comparison") or {}
    matrix = comp.get("skill_coverage_matrix") or []
    refs = comp.get("candidates_order") or results["ranking"]
    out = []
    for start in range(0, len(refs), chunk):
        group = refs[start:start + chunk]
        header = [Paragraph("<b>Requirement</b>", cellsm), Paragraph("<b>MH</b>", cellsm)]
        for ref in group:
            header.append(Paragraph(f"<b>{esc(ref[:8])}</b>", cellsm))
        rows = [header]
        extra = []
        for r_i, row_def in enumerate(matrix, 1):
            row = [Paragraph(esc(row_def["skill"]), cellsm),
                   Paragraph("Y" if row_def["must_have"] else "-", cellsm)]
            for col_i, ref in enumerate(group, 2):
                score = (row_def["scores"] or {}).get(ref)
                row.append(Paragraph("-" if score is None else f"{score:.2f}", cellsm))
                extra.append(("BACKGROUND", (col_i, r_i), (col_i, r_i), score_cell_color(score)))
            rows.append(row)
        label_w = 46 * mm
        col_w = (134.0 / max(len(group), 1)) * mm
        out.append(table(rows, [label_w, 10 * mm] + [col_w] * len(group), zebra=True, extra_style=extra, font_size=7))
        if start + chunk < len(refs):
            out.append(Spacer(1, 2 * mm))
    return out


def head_to_head_section(results, styles, pseudonymous: bool) -> list:
    h3, small, cell, cellsm = styles[2], styles[4], styles[5], styles[6]
    comp = results.get("comparison") or {}
    h2h = comp.get("head_to_head")
    if not h2h:
        return []
    by_ref = {c["candidate_ref"]: c for c in results["candidates"]}
    a = by_ref.get(h2h["top_pick_ref"])
    b = by_ref.get(h2h["runner_up_ref"])
    if not a or not b:
        return []
    flow = [Paragraph("Head-to-head: top pick vs runner-up", h3)]
    ov = h2h.get("overall") or {}
    flow.append(Paragraph(safe(
        f"{label_for(a, pseudonymous)} {ov.get('top_pick', 0):.1f} points vs "
        f"{label_for(b, pseudonymous)} {ov.get('runner_up', 0):.1f} points (gap {ov.get('gap', 0):.1f})."), small))
    rows = [[Paragraph("<b>Category</b>", cell), Paragraph("<b>Top pick</b>", cell),
             Paragraph("<b>Runner-up</b>", cell), Paragraph("<b>Winner</b>", cell)]]
    for c in h2h.get("categories", []):
        rows.append([
            Paragraph(esc(c["label"]), cell),
            Paragraph("-" if c["top_pick"] is None else f"{c['top_pick'] * 100:.0f}%", cell),
            Paragraph("-" if c["runner_up"] is None else f"{c['runner_up'] * 100:.0f}%", cell),
            Paragraph(esc(c["winner"].replace("_", " ")), cell),
        ])
    flow.append(table(rows, [62 * mm, 30 * mm, 30 * mm, 38 * mm]))
    adv = h2h.get("runner_up_advantages") or []
    if adv:
        flow.append(Paragraph("Where the runner-up is stronger (interview focus areas)", h3))
        flow.append(Paragraph(esc("; ".join(f"{x['skill']} ({x['runner_up']:.2f} vs {x['top_pick']:.2f})" for x in adv)), small))
    return flow


def bench_market_section(results, styles, pseudonymous: bool) -> list:
    h2, h3, small, cell, cellsm = styles[1], styles[2], styles[4], styles[5], styles[6]
    comp = results.get("comparison") or {}
    bench = comp.get("bench") or []
    gaps = comp.get("market_gaps") or []
    if not bench and not gaps:
        return []
    flow = [Paragraph("Bench strength & market gaps", h2)]
    if bench:
        flow.append(Paragraph("Bench strength per category (how many applicants are strong / capable / thin)", h3))
        rows = [[Paragraph("<b>Category</b>", cell), Paragraph("<b>Strong (&ge; 0.6)</b>", cell),
                 Paragraph("<b>Capable</b>", cell), Paragraph("<b>Thin (&lt; 0.4)</b>", cell),
                 Paragraph("<b>Bench read</b>", cell)]]
        for b in bench:
            read = ("deep bench - low hiring risk" if b["strong"] >= 3 else
                    "solid depth" if b["strong"] >= 2 else
                    "single point of failure" if b["strong"] == 1 else
                    "no strong applicants in this category")
            rows.append([Paragraph(esc(b["label"]), cell), Paragraph(str(b["strong"]), cell),
                         Paragraph(str(b["capable"]), cell), Paragraph(str(b["thin"]), cell),
                         Paragraph(esc(read), cellsm)])
        flow.append(table(rows, [50 * mm, 26 * mm, 22 * mm, 24 * mm, 58 * mm]))
    if gaps:
        by_ref = {c["candidate_ref"]: c for c in results["candidates"]}
        flow.append(Paragraph("Market gaps - requirements where even the best applicant shows weak evidence", h3))
        rows = [[Paragraph("<b>Requirement</b>", cell), Paragraph("<b>Category</b>", cell),
                 Paragraph("<b>MH</b>", cell), Paragraph("<b>Best evidence</b>", cell),
                 Paragraph("<b>Best applicant</b>", cell), Paragraph("<b>With evidence</b>", cell)]]
        for g in gaps:
            best_c = by_ref.get(g["best_ref"])
            rows.append([Paragraph(esc(g["skill"]), cell), Paragraph(esc(g["category_label"]), cell),
                         Paragraph("Y" if g["must_have"] else "-", cell),
                         Paragraph(f"{g['best_score']:.2f}", cell),
                         Paragraph(esc(label_for(best_c, pseudonymous)) if best_c else esc(g["best_ref"]), cellsm),
                         Paragraph(f"{g['n_with_evidence']}/{len(results['candidates'])}", cell)])
        flow.append(table(rows, [44 * mm, 38 * mm, 10 * mm, 22 * mm, 40 * mm, 26 * mm], font_size=7.5))
        flow.append(Paragraph(safe(
            "Market gaps cannot be solved by ranking - verify at interview, plan training, or revise the requirement."), small))
    return flow


def talent_pool_section(results, styles) -> list:
    h2, h3, small, cell = styles[1], styles[2], styles[4], styles[5]
    st = results.get("statistics") or {}
    tp = st.get("talent_pool") or {}
    if not tp:
        return []
    flow = [Paragraph("Talent pool insights", h2)]
    common = tp.get("common_skills") or []
    if common:
        flow.append(Paragraph("Most common skills across the cohort (lexicon scan, share of applicants)", h3))
        rows = [[Paragraph("<b>Skill</b>", cell), Paragraph("<b>Applicants</b>", cell), Paragraph("<b>Share</b>", cell)]]
        for s in common:
            rows.append([Paragraph(esc(s["skill"]), cell), Paragraph(str(s["count"]), cell),
                         Paragraph(f"{s['pct']}%", cell)])
        flow.append(table(rows, [70 * mm, 30 * mm, 30 * mm]))
    lines = []
    edu = tp.get("education_distribution") or {}
    if edu and set(edu) != {"none"}:
        lines.append("Highest education detected: " + ", ".join(f"{k}: {v}" for k, v in edu.items()))
    langs = tp.get("languages_distribution") or []
    if langs:
        lines.append("Languages declared: " + ", ".join(f"{l['language']} ({l['count']})" for l in langs))
    if tp.get("median_experience_years") is not None:
        lines.append(f"Median experience: {tp['median_experience_years']:.1f} years")
    if tp.get("avg_skills_per_candidate") is not None:
        lines.append(f"Average skills detected per applicant: {tp['avg_skills_per_candidate']:.1f}")
    tiers = st.get("tiers") or {}
    if tiers:
        lines.append(f"Tier mix: A = {tiers.get('A', 0)} shortlisted, B = {tiers.get('B', 0)} review band, "
                     f"C = {tiers.get('C', 0)} weak match")
    for ln in lines:
        flow.append(Paragraph(esc(ln), small))
    return flow


def methodology_section(results, styles) -> list:
    h2, small, cell, cellsm = styles[1], styles[4], styles[5], styles[6]
    scrub = folder_name_scrubber(results)
    flow = [Paragraph("Methodology & audit appendix", h2)]
    det = results.get("determinism") or {}
    kernel_id = str(results.get("omnidecide_version") or "")
    kernel_label = f"Kernel {kernel_id}"
    flow.append(Paragraph(safe(
        f"Engine {results.get('engine_version')} - {kernel_label} - floors data "
        f"v{results.get('floors_data_version')} - deterministic replay: "
        f"{'PASS (identical sha256 across two passes)' if det.get('identical') else 'FAILED'} "
        f"({str(det.get('pass1_sha256', ''))[:16]}...)"), small))
    manifest = (results.get("audit") or {}).get("manifest") or {}
    floors = manifest.get("floors_table") or {}
    if floors:
        rows = [[Paragraph("<b>Primitive</b>", cell), Paragraph("<b>Confidence floor</b>", cell),
                 Paragraph("<b>Meaning</b>", cell)]]
        meanings = {
            "noul": "document readability gate (blocking on hard failure)",
            "extract": "evidence snippet extraction per requirement",
            "score": "advisory per-category evidence rating",
            "choice": "shortlist decision per candidate",
            "compare": "adjacent-pair tie-break",
            "rank": "advisory order check over the top candidates",
        }
        for k in sorted(floors):
            rows.append([Paragraph(esc(k), cell), Paragraph(f"{floors[k]:.2f}", cell),
                         Paragraph(esc(meanings.get(k, "-")), cellsm)])
        flow.append(table(rows, [30 * mm, 34 * mm, 106 * mm]))
    flow.append(Paragraph("Review queue (escalations)", h2))
    rq = results.get("review_queue") or []
    if rq:
        rows = [[Paragraph("<b>Kind</b>", cell), Paragraph("<b>Candidate</b>", cell),
                 Paragraph("<b>Blocking</b>", cell), Paragraph("<b>Detail</b>", cell)]]
        for q in rq[:20]:
            rows.append([
                Paragraph(esc(str(q.get("kind") or "-")), cellsm),
                Paragraph(esc(str(q.get("candidate_ref") or "-")), cellsm),
                Paragraph("yes" if q.get("blocking") else "no", cellsm),
                # scrub folder names: details must not re-identify applicants in
                # pseudonymous exports
                Paragraph(esc(scrub(str(q.get("detail") or "-"))), cellsm),
            ])
        flow.append(table(rows, [42 * mm, 24 * mm, 16 * mm, 98 * mm], font_size=7.5))
    else:
        flow.append(Paragraph("No escalations were raised in this run.", small))
    flow.append(Paragraph(safe(
        "All extracted snippets are PII-redacted locally (emails/phones replaced) before persistence; "
        "raw document text and local paths are never persisted or exported."), small))
    return flow


# --------------------------------------------------------------------------- #
# per-candidate section (legacy shape, now a dossier wrapper)
# --------------------------------------------------------------------------- #

def candidate_section(cand, styles, pseudonymous: bool) -> list:
    h2, body = styles[1], styles[3]
    flow = [Paragraph(safe(f"#{cand['rank']}  {label_for(cand, pseudonymous)}  [Tier {cand.get('tier', '-')}]") if pseudonymous
                      else f"#{cand['rank']}  {esc(cand['folder_name'])}  [Tier {cand.get('tier', '-')}]", h2),
            Paragraph(esc(cand["overall_assessment"]), body)]
    flow.extend(dossier_flow(cand, styles, pseudonymous))
    return flow


def main() -> int:
    parser = argparse.ArgumentParser(description="Job Attune PDF export")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--pseudonymous", default="1")
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    pseudonymous = str(args.pseudonymous).lower() not in ("0", "false", "no")
    exports = run_dir / "exports"
    exports.mkdir(exist_ok=True)
    h1, h2, h3, body, small, cell, cellsm = styles = build_styles()
    manifest = {"files": []}
    prof = results.get("profile") or {}
    st = results["statistics"]

    # ---------------- batch report (comprehensive position report) ----------------
    story = []
    story.append(Paragraph("Position Report", h1))
    story.append(Paragraph(
        safe(f"{prof.get('title', '')} - {prof.get('company', '')} | Run {results['run_id']} | {results['created_at']}"),
        small))
    story.append(Paragraph(
        safe("Candidates are pseudonymous (sha256-based references). The mapping to original folder names stays on this machine and is never exported."),
        small))

    story.append(Paragraph("1. Position verdict", h2))
    story.extend(verdict_section(results, styles))

    story.append(Paragraph("2. Key figures", h2))
    kpis = [
        [Paragraph("<b>Candidates</b>", cell), Paragraph("<b>Readable CVs</b>", cell),
         Paragraph("<b>Must-have complete</b>", cell), Paragraph("<b>Shortlisted</b>", cell),
         Paragraph("<b>Avg overall</b>", cell), Paragraph("<b>Avg exp (yrs)</b>", cell),
         Paragraph("<b>Risk-flagged</b>", cell), Paragraph("<b>Review items</b>", cell)],
        [Paragraph(str(st["candidates_total"]), cell), Paragraph(str(st["readable_cv"]), cell),
         Paragraph(str(st["must_have_complete"]), cell), Paragraph(str(st["shortlisted"]), cell),
         Paragraph(f"{st['average_overall']:.1f}", cell),
         Paragraph("-" if st.get("average_experience_years") is None else f"{st['average_experience_years']:.1f}", cell),
         Paragraph(str(st.get("candidates_with_risk_flags", 0)), cell),
         Paragraph(str(len(results["review_queue"])), cell)],
    ]
    story.append(table(kpis, [22 * mm] * 8, font_size=7.5))
    if st.get("seniority_distribution"):
        story.append(Paragraph(esc("Seniority mix: " + ", ".join(f"{k}: {v}" for k, v in st["seniority_distribution"].items())), small))
    if st.get("tiers"):
        t = st["tiers"]
        story.append(Paragraph(esc(f"Tier mix: A = {t.get('A', 0)} shortlisted, B = {t.get('B', 0)} review band, "
                                   f"C = {t.get('C', 0)} weak match"), small))

    story.append(Paragraph("3. Funnel", h2))
    story.append(table([[Paragraph(f"<b>{esc(f['stage'])}</b>", cell) for f in st["funnel"]],
                        [Paragraph(str(f["count"]), cell) for f in st["funnel"]]],
                       [44 * mm] * 4))

    story.append(Paragraph("4. Ranking (best to worst)", h2))
    story.append(ranking_table(results, styles, pseudonymous))

    story.append(Paragraph("5. Category comparison matrix (column leader shaded)", h2))
    story.append(category_matrix_table(results, styles, pseudonymous))

    story.append(Paragraph("6. Skill coverage matrix (0-1 evidence per requirement)", h2))
    story.append(Paragraph(safe(
        "Cell shading: green >= 0.80 (strong), amber >= 0.40 (partial), red < 0.40 (weak/none). "
        "MH = must-have requirement. Candidate columns follow the ranking order."), small))
    story.extend(coverage_matrix_tables(results, styles, pseudonymous))

    story.append(Paragraph("7. Head-to-head (top pick vs runner-up)", h2))
    story.extend(head_to_head_section(results, styles, pseudonymous))

    story.append(Paragraph("8. Bench strength & market gaps", h2))
    story.extend(bench_market_section(results, styles, pseudonymous))

    story.append(Paragraph("9. Talent pool insights", h2))
    story.extend(talent_pool_section(results, styles))

    story.append(Paragraph("10. Applicant dossiers (ranked best to worst)", h2))
    by_ref = {c["candidate_ref"]: c for c in results["candidates"]}
    for i, ref in enumerate(results["ranking"], 1):
        c = by_ref[ref]
        story.extend(candidate_section(c, styles, pseudonymous))
        if i < len(results["ranking"]):
            story.append(PageBreak())

    story.append(PageBreak())
    story.extend(methodology_section(results, styles))

    fn = exports / "batch-report.pdf"
    doc = SimpleDocTemplate(str(fn), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=22 * mm, bottomMargin=16 * mm)
    doc.build(story, onFirstPage=header_footer(results["run_id"]), onLaterPages=header_footer(results["run_id"]))
    manifest["files"].append({"kind": "batch", "ref": None, "file": fn.name, "sha256": hashlib.sha256(fn.read_bytes()).hexdigest()})

    # ---------------- standalone per-candidate dossiers ----------------
    for ref in results["ranking"]:
        c = by_ref[ref]
        label = label_for(c, pseudonymous)
        story2 = [Paragraph(f"Candidate Report - {esc(label)}", h1),
                  Paragraph(safe(f"{prof.get('title', '')} - {prof.get('company', '')} | Run {results['run_id']}"), small)]
        story2.append(Paragraph(esc(c["overall_assessment"]), body))
        story2.extend(dossier_flow(c, styles, pseudonymous))
        fn2 = exports / f"candidate-{ref}.pdf"
        doc2 = SimpleDocTemplate(str(fn2), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                                 topMargin=22 * mm, bottomMargin=16 * mm)
        doc2.build(story2, onFirstPage=header_footer(label), onLaterPages=header_footer(label))
        manifest["files"].append({"kind": "candidate", "ref": ref, "file": fn2.name, "sha256": hashlib.sha256(fn2.read_bytes()).hexdigest()})

    # atomic manifest swap last: readers either see the previous complete
    # manifest or the new one, never a torn file
    manifest_tmp = exports / "manifest.json.tmp"
    manifest_tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(manifest_tmp, exports / "manifest.json")
    print(f"exports written: {len(manifest['files'])} files in {exports}")
    return 0


if __name__ == "__main__":
    os.umask(0o077)
    raise SystemExit(main())
