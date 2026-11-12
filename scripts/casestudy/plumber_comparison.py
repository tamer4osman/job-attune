#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Expert-vs-tool ranking comparison for the manual-labor (plumber) case study.

Reads the committed expert ranking (attune-data/casestudy-plumber/expert/),
the three engine runs (run1 pilot, v2 native, counterfactual whitespace-
tolerant) and writes:
  - attune-data/casestudy-plumber/expert/comparison.json
  - chart: work-external chart path passed as argv[1] (PNG)

Metrics: Spearman rank correlation, top-4/bottom-3 overlap, per-candidate
rank deltas. The expert ranking was committed BEFORE any engine run.
"""

# pylint: disable=duplicate-code
# R0801: Intentional structural parallel with the sibling case-study
# file -- both run the same verification/corpus-generation pipeline
# over different job-role corpora. The duplication is by design.
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CS = ROOT / "attune-data" / "casestudy-plumber"
RUNS = ROOT / "attune-data" / "runs"


def spearman(order_a: list[str], order_b: list[str]) -> float:
    n = len(order_a)
    ra = {c: i + 1 for i, c in enumerate(order_a)}
    rb = {c: i + 1 for i, c in enumerate(order_b)}
    d2 = sum((ra[c] - rb[c]) ** 2 for c in order_a)
    return round(1.0 - 6.0 * d2 / (n * (n * n - 1)), 3)


def main() -> int:
    expert = json.loads((CS / "expert" / "expert_ranking.json").read_text())
    expert_order = expert["expert_ranking_order"]
    expert_by = {c["folder"]: c for c in expert["candidates"]}

    run_v2 = json.loads((RUNS / "casestudy-plumber-native" / "results.json").read_text())
    run1 = json.loads((RUNS / "casestudy-plumber-run1-alias-gaps" / "results.json").read_text())
    cf = json.loads((RUNS / "casestudy-plumber-counterfactual-tolerant" / "results.json").read_text())

    tool_v2 = run_v2["ranking_labels"]
    tool_run1 = run1["ranking_labels"]
    tool_cf = cf["ranking_labels"]

    cand_v2 = {c["folder_name"]: c for c in run_v2["candidates"]}
    cand_cf = {c["folder_name"]: c for c in cf["candidates"]}
    cand_run1 = {c["folder_name"]: c for c in run1["candidates"]}

    rows = []
    for i, folder in enumerate(expert_order, 1):
        rows.append({
            "folder": folder,
            "expert_rank": i,
            "expert_score": expert_by[folder]["total"],
            "tool_rank_v2": tool_v2.index(folder) + 1,
            "tool_score_v2": cand_v2[folder]["overall"],
            "tool_rank_run1": tool_run1.index(folder) + 1,
            "tool_score_run1": cand_run1[folder]["overall"],
            "tool_rank_counterfactual": tool_cf.index(folder) + 1,
            "tool_score_counterfactual": cand_cf[folder]["overall"],
            "must_have_missing_v2": cand_v2[folder]["must_have_missing"],
            "values_fit_v2": cand_v2[folder]["values_fit"],
            "language": expert_by[folder].get("language", ""),
        })
    for r in rows:
        r["delta_v2"] = r["tool_rank_v2"] - r["expert_rank"]

    metrics = {
        "spearman_expert_vs_tool_v2": spearman(expert_order, tool_v2),
        "spearman_expert_vs_tool_run1": spearman(expert_order, tool_run1),
        "spearman_expert_vs_counterfactual": spearman(expert_order, tool_cf),
        "spearman_run1_vs_v2": spearman(tool_run1, tool_v2),
        "top4_overlap_v2": sorted(set(expert_order[:4]) & set(tool_v2[:4])),
        "bottom3_overlap_v2": sorted(set(expert_order[-3:]) & set(tool_v2[-3:])),
        "exact_agreement_v2": [r["folder"] for r in rows if r["delta_v2"] == 0],
        "max_rank_gap_v2": max(abs(r["delta_v2"]) for r in rows),
    }

    out = {
        "method": "expert ranking committed before any engine run (see expert_ranking.json)",
        "runs": {
            "run1_pilot": "casestudy-plumber-run1-alias-gaps",
            "v2_native": "casestudy-plumber-native",
            "counterfactual_tolerant_alias": "casestudy-plumber-counterfactual-tolerant",
        },
        "expert_order": expert_order,
        "tool_order_v2": tool_v2,
        "tool_order_run1": tool_run1,
        "tool_order_counterfactual": tool_cf,
        "candidates": rows,
        "metrics": metrics,
    }
    out_path = CS / "expert" / "comparison.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"written -> {out_path.relative_to(ROOT)}")
    print(json.dumps(metrics, indent=1, ensure_ascii=False))

    if len(sys.argv) > 1:
        render_chart(Path(sys.argv[1]), rows, metrics)
    return 0


def render_chart(path: Path, rows: list, metrics: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.font_manager as fm
    for f in ("/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf",):
        try:
            fm.fontManager.addfont(f)
        except Exception:
            pass
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Noto Sans SC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    INK, ACCENT, GRAY = "#1F2937", "#C2410C", "#94A3B8"
    n = len(rows)
    rows_sorted = sorted(rows, key=lambda r: r["expert_rank"])
    fig, ax = plt.subplots(figsize=(8.6, 7.2), constrained_layout=True)

    ys = list(range(n, 0, -1))
    for y, r in zip(ys, rows_sorted):
        e, t, c = r["expert_rank"], r["tool_rank_v2"], r["tool_rank_counterfactual"]
        ax.plot([e, t], [y, y], color=GRAY, lw=2.2, zorder=1, solid_capstyle="round")
        ax.scatter([e], [y], s=110, color=INK, zorder=3, label="Expert (committed)" if y == n else None)
        ax.scatter([t], [y], s=110, facecolors="white", edgecolors=ACCENT, lw=2.2, zorder=3,
                   label="Job-Attune v2" if y == n else None)
        if abs(c - t) >= 1:
            ax.scatter([c], [y], s=64, marker="^", color="#0F766E", zorder=4,
                       label="v2 + whitespace-tolerant aliases (counterfactual)" if y == n else None)
        if abs(r["delta_v2"]) >= 4:
            ax.annotate(f"\u0394{r['delta_v2']:+d}", xy=(max(e, t), y), xytext=(8, -3),
                        textcoords="offset points", fontsize=8.5, color=ACCENT, fontweight="bold")

    ax.set_yticks(ys)
    ax.set_yticklabels([r["folder"].replace("_", " ") for r in rows_sorted], fontsize=10)
    ax.set_xticks(range(1, n + 1))
    ax.set_xlim(0.2, n + 0.9)
    ax.set_ylim(0.2, n + 0.8)
    ax.set_xlabel("Rank (1 = strongest applicant)", fontsize=10)
    ax.set_title("Expert ranking vs Job-Attune ranking\nPlumber / Sanitary & Heating Technician (SHK) - 12 fictional applicants",
                 fontsize=12, fontweight="bold", color=INK)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#E5E7EB", lw=0.7)
    ax.set_axisbelow(True)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=3, fontsize=8.4, frameon=False)
    fig.savefig(path, dpi=200)
    print(f"chart -> {path}")


if __name__ == "__main__":
    raise SystemExit(main())
