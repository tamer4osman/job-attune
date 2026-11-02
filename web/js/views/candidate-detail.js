// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// Candidate detail modal. Port of src/components/attune/candidate-detail.tsx:
// full evidence audit for one candidate + recruiter sign-off. The dialog is
// assembled by one builder per section (below) so each stays reviewable on
// its own; openCandidateDialog only wires them together.

import { api } from "../api.js";
import { el, button, badge, input, labelFor, icon, openDialog, append, separator } from "../ui.js";

function levelClass(level) {
  return {
    strong: "badge-emerald-soft",
    good: "badge-teal-soft",
    partial: "badge-amber-soft",
    weak: "badge-slate-soft",
    none: "badge-rose-soft",
  }[level] ?? "badge-slate-soft";
}

function verdictClass(verdict) {
  return {
    met: "badge-emerald-soft",
    partial: "badge-amber-soft",
    missing: "badge-rose-soft",
  }[verdict ?? ""] ?? "badge-slate-soft";
}

function tierClass(tier) {
  return {
    A: "band-strong",
    B: "band-potential",
    C: "band-weak",
  }[tier ?? ""] ?? "badge-slate-soft";
}

export function openCandidateDialog(candidate, results, { onDecided } = {}) {
  const c = candidate;

  const titleRow = el("div", { class: "dialog-title" },
    icon("ListOrdered", 20),
    `#${c.rank} ${c.folder_name}`,
    badge(`${c.overall.toFixed(1)} / 100 - ${c.band}`, "outline", "badge-11 badge-emerald-soft"),
    c.shortlisted ? badge("shortlisted", "emerald") : null,
    c.tier ? badge(`tier ${c.tier}`, "outline", `badge-11 ${tierClass(c.tier)}`) : null,
  );

  const content = el("div", { class: "stack" });
  overallAssessment(content, c);
  profileCard(content, c);
  interviewPrompts(content, c);
  skillsInventory(content, c);
  categoryBreakdown(content, c);
  content.appendChild(separator());
  requirementEvidence(content, c);
  content.appendChild(separator());
  decisionAndFiles(content, c);
  content.appendChild(separator());
  content.appendChild(signOffBox(c, results, onDecided));

  const { close } = openDialog({
    title: titleRow,
    desc: ["Ref ", el("span", { class: "mono" }, c.candidate_ref), " (pseudonymous) - full evidence audit below."],
    wide: true,
    content: el("div", { class: "dialog-scroll" }, content),
    footer: button({ variant: "outline", size: "sm", label: "Close", onclick: () => close() }),
  });
  return { close };
}

/* overall assessment, review note and unreadable-CV warning */
function overallAssessment(content, c) {
  content.appendChild(el("div", {
    class: "mini-card",
    style: "border-color: rgb(6 78 59 / 0.1); background: rgb(236 253 245 / 0.4); color: var(--slate-800); line-height: 1.6; font-size: 14px",
  },
    el("p", { class: "strong", style: "color: var(--emerald-900); margin-bottom: 0.25rem; display: flex; align-items: center; gap: 0.375rem" },
      icon("ScrollText", 16), "Overall assessment"),
    c.overall_assessment,
  ));

  if (c.review_note) {
    content.appendChild(el("div", { class: "alert", style: "background: var(--slate-50)" },
      icon("BadgeCheck", 16, ""),
      el("span", {}, el("b", {}, "Review note: "), c.review_note)));
  }

  if (c.noul_gates?.some((g) => g.blocking)) {
    content.appendChild(el("div", { class: "alert alert-destructive" },
      icon("AlertTriangle", 16),
      "CV could not be read automatically - treat this assessment as incomplete."));
  }
}

/* profile card (v1.1.0 enrichment) */
function profileCard(content, c) {
  if (!c.profile_card) return;
  const pc = c.profile_card;
  const grid = el("div", { class: "mini-grid" });

  grid.appendChild(el("div", { class: "mini-card" },
    el("h4", {}, "Experience & seniority"),
    el("p", {},
      pc.experience_years != null
        ? `~${pc.experience_years.toFixed(1)} years (${(pc.experience_basis || "").replace(/_/g, " ")})`
        : "not detected",
      " | ", pc.seniority_estimate,
      pc.seniority_signal ? ` - ${pc.seniority_signal}` : "",
    ),
    pc.career_timeline?.length ? el("p", { class: "mono", style: "font-size:10px;color:var(--slate-400);margin-top:0.25rem" },
      pc.career_timeline.map((t) => t.span).join(" | ")) : null,
    pc.tenure ? el("p", { style: "font-size:11px;color:var(--slate-500);margin-top:0.25rem" },
      `Tenure: ${pc.tenure.positions} spans, avg ${Math.round(pc.tenure.avg_months)} mo, longest ${Math.round(pc.tenure.longest_months)} mo`) : null,
  ));

  grid.appendChild(el("div", { class: "mini-card" },
    el("h4", {}, "Education & languages"),
    el("p", {}, pc.education?.length ? pc.education.map((e) => `${e.level}: ${e.detail}`).join(" | ") : "no degrees detected"),
    el("p", {}, pc.languages?.length ? pc.languages.map((l) => `${l.language} ${l.level}/${l.band}`).join(" | ") : "no language levels detected"),
  ));

  grid.appendChild(el("div", { class: "mini-card" },
    el("h4", {}, "Certifications"),
    el("p", {}, pc.certifications?.length ? pc.certifications.join(" | ") : "none detected"),
  ));

  if (c.cohort) {
    grid.appendChild(el("div", { class: "mini-card", style: "border-color: var(--emerald-200); background: rgb(236 253 245 / 0.5)" },
      el("h4", { style: "display:flex;align-items:center;gap:0.25rem;color:var(--emerald-900)" }, icon("Gauge", 14), "Cohort standing"),
      el("p", { style: "color: rgb(6 78 59 / 0.8)" },
        `percentile ${c.cohort.percentile_overall.toFixed(0)} | ${c.cohort.delta_vs_mean >= 0 ? "+" : ""}${c.cohort.delta_vs_mean.toFixed(1)} pts vs mean | ${c.cohort.delta_vs_best >= 0 ? "+" : ""}${c.cohort.delta_vs_best.toFixed(1)} vs best`),
    ));
  }
  content.appendChild(el("div", {},
    el("p", { class: "strong", style: "margin-bottom:0.5rem;font-size:14px;display:flex;align-items:center;gap:0.375rem" },
      icon("UserRound", 16, ""), "Applicant profile (auto-extracted)"),
    grid,
  ));

  if (pc.achievements?.length) {
    content.appendChild(el("div", { class: "mini-card" },
      el("p", { style: "display:flex;align-items:center;gap:0.375rem;font-size:12px;font-weight:600;color:var(--slate-700)" },
          icon("Sparkles", 14, ""), "Quantified achievements"),
      el("ul", { class: "achieve-list" }, pc.achievements.map((a) => el("li", {}, `“${a}”`))),
    ));
  }
  if (pc.risk_flags?.length) {
    for (const rf of pc.risk_flags) {
      content.appendChild(el("p", { class: "risk-note" },
        icon("AlertTriangle", 14),
        el("span", {}, el("b", {}, `${rf.flag.replace(/_/g, " ")}: `), rf.detail)));
    }
  }
}

/* interview prompts */
function interviewPrompts(content, c) {
  if (!c.interview_prompts?.length) return;
  content.appendChild(el("div", { class: "mini-card", style: "background: var(--slate-50)" },
    el("p", { class: "strong", style: "margin-bottom:0.375rem;font-size:14px;display:flex;align-items:center;gap:0.375rem" },
      icon("MessagesSquare", 16), "Interview prompts"),
    el("ol", { style: "list-style:decimal inside;font-size:12px;line-height:1.45;color:var(--slate-600)" },
      c.interview_prompts.map((p) => el("li", {}, p))),
  ));
}

/* skills inventory */
function skillsInventory(content, c) {
  if (!c.skills_inventory?.length) return;
  content.appendChild(el("div", {},
    el("p", { class: "strong", style: "margin-bottom:0.375rem;font-size:14px;display:flex;align-items:center;gap:0.375rem" },
      icon("Layers", 16), "Skills inventory (beyond the requirements)"),
    el("div", { style: "display:flex;flex-wrap:wrap;gap:0.375rem" },
      c.skills_inventory.map((s) => badge(
        [s.skill, el("span", { style: "color:var(--slate-400);margin-left:0.25rem" }, `×${s.mentions}`)],
        "secondary", "badge-10"))),
  ));
}

/* category breakdown + values fit + score decomposition */
function categoryBreakdown(content, c) {
  const catBlock = el("div", {});
  catBlock.appendChild(el("p", { class: "strong", style: "margin-bottom:0.5rem;font-size:14px" }, "Category breakdown"));
  for (const cat of c.categories) {
    catBlock.appendChild(el("div", { class: "cat-row" },
      el("span", { class: "lbl" }, cat.label),
      el("div", { class: "track" }, el("div", { class: "fill", style: `width:${cat.avg * 100}%` })),
      el("span", { class: "num" }, `${Math.round(cat.avg * 100)}%`),
      cat.score_advisory ? badge("kernel advisory", "outline", "badge-10 warn-text") : null,
    ));
  }
  if (c.values_fit !== null && c.values_fit !== undefined) {
    catBlock.appendChild(el("p", { class: "text-xs muted", style: "margin-top:0.5rem" },
      `Company values fit: ${Math.round(c.values_fit * 100)}% of value phrases covered`,
      c.values_per_phrase?.length ? ` (${c.values_per_phrase.map((v) => `${v.phrase}: ${Math.round(v.coverage * 100)}%`).join(", ")})` : ""));
  }
  if (c.score_decomposition?.contributions?.length) {
    const decomp = el("div", { class: "mini-card", style: "background: rgb(248 250 252 / 0.6); margin-top: 0.75rem" },
      el("p", { style: "font-size:12px;font-weight:600;color:var(--slate-700);margin-bottom:0.375rem" }, "Score decomposition (points of 100)"));
    for (const d of c.score_decomposition.contributions) {
      decomp.appendChild(el("div", { class: "decomp-row" },
        el("span", { class: "lbl" }, d.label),
        el("div", { class: "track" }, el("div", { class: "fill", style: `width:${Math.min(100, d.points)}%` })),
        el("span", { class: "num" }, d.points.toFixed(1))));
    }
    if (c.score_decomposition.values_fit_points > 0) {
      decomp.appendChild(el("div", { class: "decomp-row" },
        el("span", { class: "lbl" }, "Company values fit"),
        el("div", { class: "track" }, el("div", { class: "fill", style: `width:${Math.min(100, c.score_decomposition.values_fit_points)}%; background: rgb(245 158 11 / 0.7)` })),
        el("span", { class: "num" }, c.score_decomposition.values_fit_points.toFixed(1))));
    }
    decomp.appendChild(el("p", { style: "font-size:11px;color:var(--slate-600);margin-top:0.25rem" },
      "Total: ", el("b", { class: "tabular" }, c.score_decomposition.sum_points.toFixed(1)), " / 100",
      c.score_decomposition.note ? el("span", { class: "warn-text" }, ` - ${c.score_decomposition.note}`) : null));
    catBlock.appendChild(decomp);
  }
  content.appendChild(catBlock);
}

/* requirement evidence */
function requirementEvidence(content, c) {
  const reqBlock = el("div", {});
  const reqHead = el("div", { style: "display:flex;flex-wrap:wrap;align-items:center;gap:0.5rem;margin-bottom:0.5rem" },
    el("p", { class: "strong", style: "font-size:14px" }, "Requirement evidence"));
  if (c.verdict_summary) {
    const vs = c.verdict_summary;
    append(reqHead,
      badge(`${vs.met} met`, "emerald-soft"),
      badge(`${vs.partial} partial`, "amber-soft"),
      badge(`${vs.missing} missing`, "rose-soft"),
      el("span", { class: "muted" }, `| ${vs.completeness_pct.toFixed(0)}% complete`));
  }
  reqBlock.appendChild(reqHead);
  for (const r of c.requirements) {
    const metaBits = [r.category_label];
    if (r.exact > 0) metaBits.push(`exact match in ${r.exact_source}`);
    if (r.mentions > 0) metaBits.push(`${r.mentions} mention${r.mentions > 1 ? "s" : ""}`);
    reqBlock.appendChild(el("div", { class: "req-card" },
      el("div", { class: "req-head" },
        el("span", { class: "skill" }, r.skill),
        r.must_have ? badge("must-have", "outline", "badge-10 badge-amber-soft") : null,
        badge(`${r.level} (${r.evidence_score.toFixed(2)})`, "secondary", `badge-10 ${levelClass(r.level)}`),
        r.verdict ? el("span", { class: `verdict-pill ${verdictClass(r.verdict)}` }, r.verdict) : null,
        el("span", { class: "meta" }, metaBits.join(" | ")),
      ),
      r.snippets?.length ? el("ul", { class: "req-snippets" },
        r.snippets.slice(0, 2).map((s) => el("li", {}, icon("FileText", 12), `“${s}”`))) : null,
    ));
  }
  content.appendChild(reqBlock);
}

/* choice + files */
function decisionAndFiles(content, c) {
  content.appendChild(el("div", { class: "mini-grid" },
    el("div", { class: "mini-card" },
      el("p", { class: "strong", style: "display:flex;align-items:center;gap:0.375rem;margin-bottom:0.25rem;font-size:12px" },
        icon("GitCompareArrows", 14), "Shortlist decision (choice)"),
      el("p", { class: "muted" },
        "decision: ", el("span", { class: "mono" }, c.choice.decision),
        ` at confidence ${c.choice.confidence.toFixed(2)}`,
        c.choice.escalate ? ` - below floor ${c.choice.floor?.toFixed(2) ?? "0.73"}, in review band` : ""),
    ),
    el("div", { class: "mini-card" },
      el("p", { class: "strong", style: "display:flex;align-items:center;gap:0.375rem;margin-bottom:0.25rem;font-size:12px" },
        icon("FileText", 14), "Files"),
      c.files.map((f) => el("p", { class: "mono muted", style: "font-size:12px" },
        `${f.name}: ${f.chars} chars${f.short_document ? " (short)" : ""}${!f.readable ? " (unreadable)" : ""}`)),
    ),
  ));
}

/* sign-off */
function signOffBox(c, results, onDecided) {
  const reviewerInput = input({ id: "reviewer", placeholder: "Your name", class: "input input-sm", style: "width:10rem" });
  const signMsg = el("p", { class: "inline-msg", style: "margin-top:0.5rem" });

  async function signOff(decision) {
    try {
      await api("/api/audit", {
        method: "POST",
        body: JSON.stringify({
          run_id: results.run_id,
          action: "signoff",
          candidate_ref: c.candidate_ref,
          decision,
          reviewer: reviewerInput.value,
          note: `Rank #${c.rank}, overall ${c.overall}`,
        }),
      });
      signMsg.textContent = `Recorded: ${decision === "endorse" ? "endorsed" : "rejected"} by ${reviewerInput.value || "anonymous"} - written to the audit trail.`;
      onDecided?.();
    } catch (err) {
      signMsg.textContent = err.message;
    }
  }

  return el("div", { class: "mini-card", style: "border-color: rgb(6 78 59 / 0.1)" },
    el("p", { class: "strong", style: "margin-bottom:0.5rem;font-size:14px;display:flex;align-items:center;gap:0.375rem" },
      icon("Signature", 16), "Recruiter sign-off (GDPR audit trail)"),
    el("div", { style: "display:flex;flex-wrap:wrap;align-items:flex-end;gap:0.5rem" },
      el("div", { class: "field" }, labelFor("reviewer", "Reviewer"), reviewerInput),
      button({
        variant: "primary", size: "sm", label: "Endorse", icon: "CheckCircle2",
        onclick: () => signOff("endorse"),
      }),
      button({
        variant: "danger-outline", size: "sm", label: "Reject",
        onclick: () => signOff("reject"),
      }),
    ),
    signMsg,
  );
}
