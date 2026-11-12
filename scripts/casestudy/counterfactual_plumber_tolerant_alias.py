#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Counterfactual experiment for the plumber/SHK case study (measurement
only, NOT an engine release change):

Reruns the plumber screening with alias matching made whitespace-tolerant
(multi-word aliases may span PDF line breaks). Quantifies the line-break
finding of the manual-labor case studies on this corpus: multi-word aliases
matched with literal spaces miss PDF line breaks.

Writes results to attune-data/runs/casestudy-plumber-counterfactual-tolerant/.
The repository engine is NOT modified.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "attune-engine"))

import engine  # noqa: E402


def tolerant_alias_regex(alias: str) -> re.Pattern:
    parts = [re.escape(w) for w in alias.lower().strip().split()]
    return re.compile(r"(?<![a-z0-9])" + r"[\s]+".join(parts) + r"(?![a-z0-9])",
                      re.IGNORECASE)


def main() -> None:
    engine.alias_regex = tolerant_alias_regex  # counterfactual patch (in-memory)
    sys.argv = [
        "engine.py",
        "--folder", str(ROOT / "attune-data/casestudy-plumber/candidates"),
        "--profile", str(ROOT / "attune-data/casestudy-plumber/profile-plumber.json"),
        "--run-dir", str(ROOT / "attune-data/runs/casestudy-plumber-counterfactual-tolerant"),
        "--salt", "casestudy-plumber",
    ]
    engine.main()


if __name__ == "__main__":
    main()
