#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Counterfactual experiment (case study only, NOT an engine release change):

Reruns the trades screening with alias matching made whitespace-tolerant
(multi-word aliases may span PDF line breaks). Quantifies finding M4 of the
manual-labor case study: "furniture installation" split across lines in
david_osei's CV missed the must-have alias, capping him at 40.

Writes results to attune-data/runs/casestudy-trades-counterfactual-tolerant/.
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
        "--folder", str(ROOT / "attune-data/casestudy-trades/candidates"),
        "--profile", str(ROOT / "attune-data/casestudy-trades/profile-furniture-technician.json"),
        "--run-dir", str(ROOT / "attune-data/runs/casestudy-trades-counterfactual-tolerant"),
        "--salt", "casestudy-trades-native",
    ]
    engine.main()


if __name__ == "__main__":
    main()
