#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Build the manual-labor (furniture technician) case-study corpus.

Generates one PDF per persona file (ReportLab) under
attune-data/casestudy-trades/candidates/<folder>/, plus ground_truth.json
recording true document roles, language, planted challenges and the coarse
design strength per candidate.

Deterministic: identical inputs -> identical PDF bytes across runs.
"""

# pylint: disable=duplicate-code
# R0801: Intentional structural parallel with the sibling case-study
# file -- both run the same verification/corpus-generation pipeline
# over different job-role corpora. The duplication is by design.
from __future__ import annotations

import json
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trades_personas import PERSONAS

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "attune-data" / "casestudy-trades"

BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=14)
HEAD = ParagraphStyle("head", fontName="Helvetica-Bold", fontSize=10.5, leading=15,
                      spaceBefore=8, spaceAfter=2)
TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=13, leading=17,
                       spaceAfter=6)


def build_pdf(path: Path, title: str, body: str) -> None:
    story = [Paragraph(title, TITLE)]
    for block in body.strip("\n").split("\n\n"):
        text = " ".join(line.strip() for line in block.strip().splitlines())
        if not text:
            continue
        if text.startswith("# "):
            story.append(Paragraph(text[2:], HEAD))
        else:
            story.append(Paragraph(text, BODY))
            story.append(Spacer(1, 2 * mm))
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=title, author="case-study corpus",
                            subject="Job-Attune manual-labor case study")
    doc.build(story)


def main() -> None:
    cand_root = OUT / "candidates"
    cand_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "corpus": "manual-labor-case-study",
        "role": "Furniture Technician (Assembly & Service)",
        "profile": "profile-furniture-technician.json",
        "profile_grounding": "Requirements modelled on published criteria for comparable positions: Havertys Furniture Service Technician (jobs.havertys.com), Cushman & Wakefield Workplace Services Technician (careers.cushmanwakefield.com), furniture installer postings (reading assembly instructions and layout plans), and German Kuechen- und Moebelmonteur / Tischler postings on the Bundesagentur fuer Arbeit job board (10001-1003465780-S), all retrieved 2026-11-11.",
        "candidates": [],
    }
    for persona in PERSONAS:
        folder = cand_root / persona["folder"]
        folder.mkdir(parents=True, exist_ok=True)
        entry = {
            "folder": persona["folder"],
            "language": persona["lang"],
            "strength": persona["strength"],
            "challenge": persona["challenge"],
            "files": [],
        }
        for spec in persona["files"]:
            path = folder / spec["name"]
            build_pdf(path, spec["title"], spec["body"])
            entry["files"].append({
                "name": spec["name"],
                "true_role": spec["kind"],        # what the CONTENT is
                "lang": spec["lang"],
            })
            print(f"built {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")
        manifest["candidates"].append(entry)
    gt_path = OUT / "ground_truth.json"
    gt_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"ground truth manifest -> {gt_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
