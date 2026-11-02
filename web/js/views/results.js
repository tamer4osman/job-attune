// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// Step 4 - results workspace: stat cards + the six tabs (overview, position
// report, ranking, candidates, review, audit & export). Ports
// ranking-board.tsx, overview-charts.tsx and the step-4 shell of page.tsx.

import { el, badge, icon, createTabs, append } from "../ui.js";
import { hbarChart, vbarChart, radarChart, chartCard, KIND_COLORS, EMERALD, AMBER, ROSE } from "../charts.js";
import { openCandidateDialog } from "./candidate-detail.js";
import { PositionReport } from "./position-report.js";
import { Governance } from "./governance.js";

const BAND_CLASSES = {
  strong: "band-strong",
  good: "band-good",
  potential: "band-potential",
  weak: "band-weak",
};

const RANK_COLORS = ["#f26c17", "#b3a990", "#8f6a0b"];

function rankBadgeEl(rank) {
  const style = rank <= 3
    ? `background-color:${RANK_COLORS[rank - 1]};color:#fff`
    : "background-color:#f5f1e3;color:#524a42";
  return el("span", { class: "rank-badge", style }, String(rank));
}

function scoreBar(value) {
  return el("div", { class: "scorebar" },
    el("div", { class: "scorebar-track" },
      el("div", { class: "scorebar-fill", style: `width:${Math.min(100, value)}%` })),
    el("span", { class: "scorebar-num" }, value.toFixed(1)));
}

/* ------------------------------------------------------------------ */
/* Stat cards                                                          */
/* ------------------------------------------------------------------ */

function statCards(results) {
  const s = results.statistics;
  const items = [
    { label: "Candidates", value: s.candidates_total },
    { label: "Readable CVs", value: s.readable_cv },
    { label: "Must-have complete", value: s.must_have_complete },
    { label: "Shortlisted", value: s.shortlisted },
    { label: "Avg overall", value: s.average_overall.toFixed(1) },
    { label: "Review items", value: results.review_queue.length },
  ];
  return el("div", { class: "stat-grid" }, items.map((it) =>
    el("div", { class: "card" },
      el("div", { class: "card-body", style: "padding:1rem" },
        el("p", { class: "stat-value" }, String(it.value)),
        el("p", { class: "stat-label" }, it.label)))));
}

/* ------------------------------------------------------------------ */
/* Overview tab                                                        */
/* ------------------------------------------------------------------ */

function overviewPanel(results) {
  const s = results.statistics;
  const root = el("div", { class: "grid-2" });

  const funnel = s.funnel.map((f, i) => ({
    label: f.stage, value: f.count, fill: EMERALD, fillOpacity: 1 - i * 0.18,
  }));
  root.appendChild(chartCard({
    title: "Screening funnel", icon: "Filter",
    desc: "From applications received to shortlisted candidates.",
    make: (box) => hbarChart(box, { items: funnel, labelWidth: 150 }),
  }));

  const radar = Object.values(s.category_averages)
    .filter((c) => c.avg !== null)
    .map((c) => ({
      label: c.label.replace("University ", "").replace(" Professional", "").replace("Training ", ""),
      value: Math.round((c.avg ?? 0) * 100),
    }));
  root.appendChild(chartCard({
    title: "Category averages", icon: "Gauge",
    desc: "Mean evidence strength per requirement category (0-100).",
    make: (box) => radarChart(box, { items: radar }),
  }));

  const histogram = s.score_histogram.map((h, i) => ({
    label: h.bucket, value: h.count,
    fill: i < 3 ? ROSE : i < 5 ? AMBER : EMERALD, fillOpacity: 0.85,
  }));
  root.appendChild(chartCard({
    title: "Score distribution", icon: "BarChart3", short: true,
    desc: "Candidates per overall score bucket.",
    make: (box) => vbarChart(box, { items: histogram }),
  }));

  const escalations = Object.entries(
    results.review_queue.reduce((acc, q) => { acc[q.kind] = (acc[q.kind] ?? 0) + 1; return acc; }, {}),
  ).map(([kind, count]) => ({
    label: kind.replace(/_/g, " "), value: count, color: KIND_COLORS[kind] ?? "#0d9488",
  }));
  root.appendChild(chartCard({
    title: "Human review signals", icon: "ShieldAlert", short: true,
    desc: `Calibrated floors catch uncertain machine decisions: ${results.review_queue.filter((q) => q.blocking).length} blocking, ${results.review_queue.filter((q) => !q.blocking).length} advisory.`,
    make: (box) => {
      if (escalations.length === 0) {
        box.appendChild(el("p", {
          style: "padding-top:2rem;text-align:center;font-size:14px;color:var(--muted)",
        }, "No escalations - all decisions above their floors."));
        return;
      }
      hbarChart(box, {
        items: escalations.map((e) => ({ label: e.label, value: e.value, fill: e.color })),
        barSize: 16, labelWidth: 160, tickSize: 9.5,
      });
    },
  }));

  /* coverage chips */
  const coverage = s.requirement_coverage.slice(0, 18).map((r) => {
    const tone = r.coverage_pct >= 60 ? "var(--teal-600)"
      : r.coverage_pct >= 30 ? "var(--amber-500)"
      : r.coverage_pct > 0 ? "var(--emerald-500)" : "var(--rose-500)";
    return el("div", { class: "coverage-chip" },
      el("span", { class: "dot", style: `background:${tone}` }),
      el("span", { class: "nm" }, r.skill),
      el("span", { class: "pct" }, `${r.coverage_pct}%`));
  });
  root.appendChild(el("div", { class: "card span-2", style: "grid-column: 1 / -1" },
    el("div", { class: "card-head tight" },
      el("h3", { class: "card-title sm" }, "Requirement coverage (evidence found per requirement)"),
      el("p", { class: "card-desc" },
        "Share of candidates with at least partial evidence for each skill - spot sourcing gaps at a glance."),
    ),
    el("div", { class: "card-body tight" }, el("div", { class: "coverage-chips" }, coverage)),
  ));
  return root;
}

/* ------------------------------------------------------------------ */
/* Ranking tab                                                         */
/* ------------------------------------------------------------------ */

function rankingPanel(results, state) {
  const byRef = Object.fromEntries(results.candidates.map((c) => [c.candidate_ref, c]));
  const ordered = [];
  let dropped = 0;
  for (const ref of results.ranking) {
    const c = byRef[ref];
    if (c) ordered.push(c);
    else dropped += 1; // corrupt/partial run: never silently hide the gap
  }

  const root = el("div", { class: "stack" });
  root.appendChild(el("div", { class: "card card-emerald" },
    el("div", { class: "card-head" },
      el("h2", { class: "card-title" }, icon("ListOrdered", 20), "Ranking - best candidates first"),
      el("p", { class: "card-desc" },
        "Descending by overall evidence score. Near-ties were checked with the compare primitive; the rank primitive validated the order."),
    ),
    el("div", { class: "card-body" },
      dropped > 0 ? el("p", {
        class: "alert alert-warn", style: "margin-bottom:0.5rem",
      }, `Warning: ${dropped} ranked reference${dropped === 1 ? "" : "s"} missing from the candidate list - this run may be partial.`) : null,
      ordered.map((c, i) => {
        const prev = i > 0 ? ordered[i - 1].overall : 999;
        const nearTie = prev - c.overall < 2.0 && i > 0;
        const sub = [];
        if (c.strengths?.length) sub.push(`Strengths: ${c.strengths.join(", ")}`);
        if (c.must_have_missing?.length) sub.push(`Missing must-haves: ${c.must_have_missing.join(", ")}`);
        if (c.profile_card?.seniority_estimate && c.profile_card.seniority_estimate !== "unknown") {
          sub.push(`${c.profile_card.seniority_estimate}${c.profile_card.experience_years != null ? ` (~${c.profile_card.experience_years.toFixed(0)} yrs)` : ""}`);
        }
        if (c.cohort) sub.push(`pctile ${c.cohort.percentile_overall.toFixed(0)}`);
        return el("button", {
          type: "button", class: "rank-row",
          onclick: () => openCandidateDialog(c, results, {}),
        },
          rankBadgeEl(c.rank),
          c.rank === 1 ? el("span", { style: "color:#f26c17;display:inline-flex" }, icon("Crown", 16)) : null,
          el("div", { class: "rank-main" },
            el("div", { class: "rank-title-row" },
              el("span", { class: "rank-name" }, c.folder_name),
              badge(c.band, "outline", `badge-11 ${BAND_CLASSES[c.band] ?? ""}`),
              c.shortlisted ? badge("shortlisted", "emerald", "badge-11") : null,
              c.must_have_missing?.length ? badge(`gaps: ${c.must_have_missing.length}`, "outline", "badge-11 badge-rose-soft") : null,
              c.noul_gates?.some((g) => g.blocking) ? badge("unreadable - review", "outline", "badge-11 badge-rose-soft") : null,
              nearTie ? badge("near-tie", "outline", "badge-11") : null,
            ),
            el("p", { class: "rank-sub" }, sub.join(" | ")),
          ),
          scoreBar(c.overall),
        );
      }),
    ),
  ));
  return root;
}

/* ------------------------------------------------------------------ */
/* Candidates tab (card grid)                                          */
/* ------------------------------------------------------------------ */

function candidatesPanel(results) {
  const byRef = Object.fromEntries(results.candidates.map((c) => [c.candidate_ref, c]));
  const ordered = results.ranking.map((r) => byRef[r]).filter(Boolean);
  return el("div", { class: "grid-3" }, ordered.map((c) =>
    el("button", {
      type: "button", class: "cand-card",
      onclick: () => openCandidateDialog(c, results, {}),
    },
      el("div", { class: "candidate-tile-head" },
        icon("UserRound", 16, "muted"),
        el("span", { class: "name", style: "flex:1" }, c.folder_name),
        badge(c.band, "outline", `badge-11 ${BAND_CLASSES[c.band] ?? ""}`)),
      el("p", { class: "assessment" }, c.overall_assessment),
      el("div", { style: "margin-top:0.75rem" }, scoreBar(c.overall)),
    )));
}

/* ------------------------------------------------------------------ */
/* Results shell (stat cards + tabs)                                   */
/* ------------------------------------------------------------------ */

export function ResultsView(state, actions) {
  const results = state.results;
  const root = el("div", { class: "stack" });
  root.appendChild(statCards(results));

  const tabs = createTabs(
    [
      { id: "overview", label: "Overview" },
      { id: "position", label: "Position report", icon: "Crown" },
      { id: "ranking", label: "Ranking", icon: "ListOrdered" },
      { id: "candidates", label: "Candidates" },
      { id: "review", label: "Review", badge: results.review_queue.length > 0 ? results.review_queue.length : null },
      { id: "audit", label: "Audit & export" },
    ],
    new Map([
      ["overview", () => overviewPanel(results)],
      ["position", () => PositionReport(results)],
      ["ranking", () => rankingPanel(results, state)],
      ["candidates", () => candidatesPanel(results)],
      ["review", () => Governance(state, actions)],
      ["audit", () => Governance(state, actions)],
    ]),
  );
  root.appendChild(tabs.root);
  return root;
}
