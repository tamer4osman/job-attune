// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// Position report tab. Port of src/components/attune/position-report.tsx:
// verdict banner, category leaders, differentiators, bench + market gaps,
// head-to-head, skill coverage matrix, talent pool insights. One builder
// per section below; PositionReport wires them together (append() skips
// the nulls a section returns when its data block is absent).

import { el, badge, icon, append } from "../ui.js";

const VERDICT_STYLES = {
  strong_front_runner: { label: "Strong front-runner - proceed to shortlist / offer", cls: "border-color:var(--emerald-300);background:var(--emerald-50);color:var(--emerald-900)" },
  proceed_to_interview: { label: "Proceed to interview", cls: "border-color:var(--teal-200);background:var(--teal-50);color:var(--teal-900)" },
  hold_review: { label: "Hold - manual review before any decision", cls: "border-color:var(--amber-300);background:var(--amber-50);color:var(--amber-900)" },
  blocked_manual_review: { label: "Blocked - manual review required (unreadable documents)", cls: "border-color:var(--rose-300);background:var(--rose-50);color:var(--rose-900)" },
  no_strong_match_this_round: { label: "No strong match this round", cls: "border-color:var(--rose-300);background:var(--rose-50);color:var(--rose-900)" },
};

function heatClass(score) {
  if (score == null) return "heat-none";
  if (score >= 0.8) return "heat-high";
  if (score >= 0.4) return "heat-mid";
  return "heat-low";
}

export function PositionReport(results) {
  const byRef = Object.fromEntries(results.candidates.map((c) => [c.candidate_ref, c]));
  const comp = results.comparison;

  if (!comp?.verdict) {
    return el("div", { class: "card" },
      el("div", { class: "card-body", style: "padding:1.5rem;font-size:14px;color:var(--muted)" },
        "This run was produced by an older engine version without the comparison block. Start a new run to get the position verdict, comparison matrices and per-applicant dossiers."));
  }

  const v = comp.verdict;
  const verdict = VERDICT_STYLES[v.recommendation] ?? {
    label: "Review recommended",
    cls: "border-color:var(--amber-300);background:var(--amber-50);color:var(--amber-900)",
  };
  const topPick = v.top_pick_ref ? byRef[v.top_pick_ref] : undefined;
  const runnerUp = v.runner_up_ref ? byRef[v.runner_up_ref] : undefined;
  const matrix = comp.skill_coverage_matrix;

  const root = el("div", { class: "stack" });
  append(root,
    verdictBanner(v, verdict),
    leadersAndDifferentiators(comp, byRef),
    benchAndGaps(comp, results, byRef),
    headToHead(comp, topPick, runnerUp),
    coverageMatrix(comp, matrix, byRef),
    talentPool(results),
  );
  return root;
}

/* verdict banner */
function verdictBanner(v, verdict) {
  return el("div", { class: "card", style: verdict.cls },
    el("div", { class: "card-head tight" },
      el("h2", { class: "card-title" }, icon("Crown", 20), "Position verdict"),
      el("p", { class: "card-desc", style: verdict.cls.includes("emerald") ? "color:var(--emerald-800)" : "" },
        "Deterministic recommendation derived from the scored cohort - human sign-off still required."),
    ),
    el("div", { class: "card-body stack-sm" },
      el("p", { style: "font-size:16px;font-weight:700" }, verdict.label),
      el("p", { style: "font-size:14px;line-height:1.6" }, v.rationale),
      v.next_steps?.length ? el("div", {
        style: "border:1px solid rgb(255 255 255 / 0.4);background:rgb(255 255 255 / 0.5);border-radius:0.5rem;padding:0.625rem",
      },
        el("p", { style: "font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;opacity:0.6" }, "Recommended next steps"),
        el("ul", { style: "list-style:disc inside;margin-top:0.25rem;font-size:14px" },
          v.next_steps.map((s) => el("li", {}, s))),
      ) : null,
      v.order_note ? el("p", { class: "text-xs", style: "display:flex;align-items:center;gap:0.375rem;opacity:0.8" },
        icon("Scale", 14), v.order_note) : null,
    ),
  );
}

/* leaders + differentiators */
function leadersAndDifferentiators(comp, byRef) {
  const pair = el("div", { class: "grid-2" });

  pair.appendChild(el("div", { class: "card" },
    el("div", { class: "card-head tight" },
      el("h3", { class: "card-title sm" }, icon("TrendingUp", 16), "Category leaders"),
      el("p", { class: "card-desc" }, "Who leads each requirement category across the whole field."),
    ),
    el("div", { class: "card-body tight" }, comp.category_leaders.map((l) =>
      el("div", { class: "kv-row", style: "font-size:14px" },
        el("span", { class: "k", style: "width:10rem;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" }, l.label),
        badge(byRef[l.leader_ref]?.folder_name ?? l.leader_ref, "outline", "badge-11 badge-emerald-soft mono"),
        el("span", { class: "v strong tabular", style: "margin-left:auto;width:auto" }, `${Math.round(l.avg * 100)}%`),
      ))),
  ));

  pair.appendChild(el("div", { class: "card" },
    el("div", { class: "card-head tight" },
      el("h3", { class: "card-title sm" }, icon("GitCompareArrows", 16), "Key differentiators"),
      el("p", { class: "card-desc" }, "Skills where one applicant clearly separates from the cohort mean."),
    ),
    el("div", { class: "card-body tight" },
      comp.differentiators.length === 0
        ? el("p", { style: "font-size:14px;color:var(--muted)" }, "No strong separation signals in this cohort.")
        : comp.differentiators.map((d) =>
          el("div", { class: "kv-row", style: "font-size:14px" },
            el("span", { style: "flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" }, d.skill),
            badge(byRef[d.leader_ref]?.folder_name ?? d.leader_ref, "outline", "badge-10 badge-emerald-soft mono"),
            el("span", { class: "tabular muted", style: "font-size:12px;width:7rem;text-align:right" },
              `${d.leader_score.toFixed(2)} vs mean ${d.cohort_mean.toFixed(2)}`),
            el("span", { class: "tabular strong", style: "font-size:12px;width:3rem;text-align:right;color:var(--emerald-700)" },
              `+${d.edge.toFixed(2)}`),
          )),
    ),
  ));
  return pair;
}

/* bench + market gaps */
function benchAndGaps(comp, results, byRef) {
  if (!comp.bench?.length && !comp.market_gaps?.length) return null;
  const pair2 = el("div", { class: "grid-2" });
  pair2.appendChild(el("div", { class: "card" },
    el("div", { class: "card-head tight" },
      el("h3", { class: "card-title sm" }, icon("Layers", 16), "Bench strength by category"),
      el("p", { class: "card-desc" }, "How deep the applicant pool runs per requirement category."),
    ),
    el("div", { class: "card-body tight" }, (comp.bench ?? []).map((b) => {
      const read = b.strong >= 3 ? "deep bench" : b.strong >= 2 ? "solid depth" : b.strong === 1 ? "single point of failure" : "no strong applicants";
      return el("div", { class: "kv-row", style: "font-size:14px" },
        el("span", { class: "k", style: "width:10rem;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" }, b.label),
        el("span", { style: "display:flex;gap:0.25rem" },
          badge(`${b.strong} strong`, "emerald-soft", "badge-11 tabular"),
          badge(`${b.capable} capable`, "amber-soft", "badge-11 tabular"),
          badge(`${b.thin} thin`, "rose-soft", "badge-11 tabular")),
        el("span", { class: "muted", style: "margin-left:auto;font-size:11px;font-style:italic" }, read),
      );
    }),
  )));
  pair2.appendChild(el("div", { class: "card" },
    el("div", { class: "card-head tight" },
      el("h3", { class: "card-title sm" }, icon("AlertTriangle", 16, ""), "Market gaps & unique edges"),
      el("p", { class: "card-desc" }, "Requirements the whole cohort misses - and skills only one applicant brings."),
    ),
    el("div", { class: "card-body tight stack-sm" },
      (comp.market_gaps ?? []).length === 0
        ? el("p", { style: "font-size:14px;color:var(--muted)" },
            "No market gaps - every requirement has at least one applicant with solid evidence.")
        : el("div", { class: "stack-sm" }, (comp.market_gaps ?? []).map((g) =>
            el("div", { class: "alert alert-warn", style: "font-size:12px;padding:0.375rem 0.625rem" },
              el("span", { style: "flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" },
                g.skill, g.must_have ? el("b", { class: "warn-text" }, " (must-have)") : null),
              el("span", { class: "tabular" }, `best ${g.best_score.toFixed(2)}`),
              el("span", { class: "muted" }, `${g.n_with_evidence}/${results.candidates.length} w/ evidence`)))),
      (comp.unique_strengths ?? []).length ? el("div", { class: "stack-sm" }, (comp.unique_strengths ?? []).map((u) =>
        el("p", { style: "font-size:12px;color:var(--emerald-900);display:flex;gap:0.375rem" },
          icon("Sparkles", 12, ""),
          el("span", {},
            el("b", { class: "mono" }, byRef[u.ref]?.folder_name ?? u.ref),
            " is the only applicant with strong evidence for: ", u.skills.join(", "))))) : null,
    ),
  ));
  return pair2;
}

/* head to head */
function headToHead(comp, topPick, runnerUp) {
  if (!comp.head_to_head || !topPick || !runnerUp) return null;
  return el("div", { class: "card" },
    el("div", { class: "card-head tight" },
      el("h3", { class: "card-title sm" }, icon("Swords", 16), `Head-to-head: ${topPick.folder_name} vs ${runnerUp.folder_name}`),
      el("p", { class: "card-desc" },
        `${comp.head_to_head.overall.top_pick.toFixed(1)} vs ${comp.head_to_head.overall.runner_up.toFixed(1)} points (gap ${comp.head_to_head.overall.gap.toFixed(1)}).`),
    ),
    el("div", { class: "card-body tight stack-sm" },
      el("div", { class: "mini-grid" }, comp.head_to_head.categories.map((c) =>
        el("div", { class: "mini-card", style: "display:flex;align-items:center;gap:0.5rem;font-size:12px" },
          el("span", { style: "flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" }, c.label),
          el("span", {
            class: `tabular ${c.winner === "top_pick" ? "strong" : "muted"}`,
            style: c.winner === "top_pick" ? "color:var(--emerald-700)" : "",
          }, c.top_pick == null ? "-" : `${Math.round(c.top_pick * 100)}%`),
          el("span", { style: "color:var(--slate-300)" }, "vs"),
          el("span", {
            class: `tabular ${c.winner === "runner_up" ? "strong" : "muted"}`,
            style: c.winner === "runner_up" ? "color:var(--teal-700)" : "",
          }, c.runner_up == null ? "-" : `${Math.round(c.runner_up * 100)}%`),
        ))),
      comp.head_to_head.runner_up_advantages?.length ? el("p", {
        class: "alert alert-warn", style: "font-size:12px",
      }, icon("AlertTriangle", 14),
        el("span", {},
          "Where the runner-up is stronger (interview focus): ",
          comp.head_to_head.runner_up_advantages.map((a) => `${a.skill} (${a.runner_up.toFixed(2)} vs ${a.top_pick.toFixed(2)})`).join("; "))) : null,
    ),
  );
}

/* skill coverage matrix */
function coverageMatrix(comp, matrix, byRef) {
  const thead = el("thead", {}, el("tr", {},
    el("th", { style: "text-align:left" }, "Requirement"),
    el("th", {}, "MH"),
    comp.candidates_order.map((ref) =>
      el("th", { class: "mono", style: "font-size:10px" }, byRef[ref]?.folder_name ?? ref))));
  const tbody = el("tbody", {}, matrix.map((row) =>
    el("tr", {},
      el("td", {}, row.skill),
      el("td", { class: "muted", style: "font-size:10px" }, row.must_have ? "Y" : "-"),
      comp.candidates_order.map((ref) => {
        const s = row.scores[ref];
        return el("td", { class: `tabular ${heatClass(s)}` }, s == null ? "-" : s.toFixed(2));
      }))));
  return el("div", { class: "card" },
    el("div", { class: "card-head tight" },
      el("h3", { class: "card-title sm" }, "Skill coverage matrix (evidence 0-1, best to worst)"),
      el("p", { class: "card-desc" },
        "Requirements as rows, applicants as columns in ranking order. Green ≥ 0.80, amber ≥ 0.40, red below. MH = must-have."),
    ),
    el("div", { class: "card-body table-wrap" }, el("table", { class: "matrix" }, thead, tbody)),
  );
}

/* talent pool insights */
function talentPool(results) {
  if (!results.statistics?.talent_pool) return null;
  const tp = results.statistics.talent_pool;
  return el("div", { class: "card" },
    el("div", { class: "card-head tight" },
      el("h3", { class: "card-title sm" }, icon("Users", 16), "Talent pool insights"),
      el("p", { class: "card-desc" }, "What the applicant pool for this position looks like as a whole."),
    ),
    el("div", { class: "card-body tight stack-sm" },
      (tp.common_skills ?? []).length ? el("div", {},
        el("p", { style: "font-size:12px;font-weight:600;color:var(--slate-700)" }, "Most common skills across the cohort"),
        el("div", {}, tp.common_skills.map((s) =>
          el("div", { class: "cat-row" },
            el("span", { class: "lbl" }, s.skill),
            el("div", { class: "track" }, el("div", { class: "fill", style: `width:${s.pct}%;opacity:0.7` })),
            el("span", { class: "muted tabular", style: "width:4rem;text-align:right;font-size:12px" }, `${s.pct}% (${s.count})`)))),
      ) : null,
      el("div", { style: "display:flex;flex-wrap:wrap;gap:0.25rem 1rem;font-size:12px;color:var(--muted)" },
        Object.entries(tp.education_distribution ?? {}).map(([k, n]) =>
          el("span", {}, "highest education ", el("b", { style: "color:var(--slate-700)" }, k), `: ${n}`)),
        (tp.languages_distribution ?? []).slice(0, 4).map((l) =>
          el("span", {}, `${l.language}: `, el("b", { style: "color:var(--slate-700)" }, String(l.count)))),
        tp.median_experience_years != null
          ? el("span", {}, "median experience ", el("b", { style: "color:var(--slate-700)" }, `${tp.median_experience_years.toFixed(1)} yrs`))
          : null,
        el("span", {}, "avg skills detected ", el("b", { style: "color:var(--slate-700)" }, tp.avg_skills_per_candidate.toFixed(1))),
      ),
    ),
  );
}
