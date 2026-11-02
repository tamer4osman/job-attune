// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// Review + Audit & export tabs. Port of src/components/attune/governance.tsx.
// Both tabs render the same governance panel (reviewer name and pseudonymous
// toggle are shared app-level state, exactly like the lifted React state).

import { api, downloadReport } from "../api.js";
import { el, button, badge, input, labelFor, switchInput, icon, separator, append } from "../ui.js";

const KIND_BADGE = {
  unreadable_document: { label: "blocking", cls: "badge-rose-soft" },
  shortlist_band: { label: "review band", cls: "badge-amber-soft" },
  tie_unresolved: { label: "near-tie", cls: "badge-amber-soft" },
  rank_conflict: { label: "rank conflict", cls: "badge-amber-soft" },
  score_advisory: { label: "advisory", cls: "badge-teal-soft" },
  noul_kernel_advisory: { label: "advisory", cls: "badge-teal-soft" },
  low_confidence_extraction: { label: "advisory", cls: "badge-teal-soft" },
};

/** Live Governance panels (Review + Audit tabs render one each). After a
 * state refresh every mounted panel re-reads decisions/exports - the
 * vanilla equivalent of the React re-render both instances got. */
const refreshers = new Set();

function refreshAllGovernance() {
  for (const fn of refreshers) fn();
}

export function Governance(state, actions) {
  const results = state.results;
  const byRef = Object.fromEntries(results.candidates.map((c) => [c.candidate_ref, c]));
  let resolving = false;
  let busy = false;
  const msg = el("p", { class: "inline-msg" });

  const root = el("div", { class: "gov-grid" });

  /* ---------------- review queue (left column) ----------------------- */
  const reviewerInput = input({
    id: "governance-reviewer", value: state.reviewer, class: "input input-sm",
    placeholder: "Your name (recorded with each decision)",
    oninput: (ev) => { state.reviewer = ev.target.value; },
  });

  const reviewerLabel = labelFor("governance-reviewer", "Reviewer");
  reviewerLabel.classList.add("text-xs");

  const queueList = el("div", { class: "stack-sm" });
  if (results.review_queue.length === 0) {
    queueList.appendChild(el("p", { style: "font-size:14px;color:var(--muted)" }, "Nothing flagged."));
  }
  results.review_queue.forEach((q) => {
    const entry = KIND_BADGE[q.kind] ?? { label: q.kind, cls: "badge-slate-soft" };
    const cand = q.candidate_ref ? byRef[q.candidate_ref] : null;
    queueList.appendChild(el("div", { class: "review-item" },
      el("div", { class: "review-item-head" },
        badge(entry.label, "outline", `badge-10 ${entry.cls}`),
        el("span", { class: "who" }, cand ? cand.folder_name : q.kind),
        el("span", { class: "meta" }, `${q.primitive} | conf ${q.confidence?.toFixed(2)} vs floor ${q.floor?.toFixed(2)}`),
      ),
      el("p", {}, q.detail),
      el("div", { class: "review-item-actions" },
        button({ variant: "outline", size: "xs", label: "Acknowledge", onclick: () => resolve(q, "acknowledge") }),
        button({ variant: "outline", size: "xs", label: "Manual review", onclick: () => resolve(q, "escalate_manual") }),
      ),
    ));
  });

  root.appendChild(el("div", { class: "card", style: "min-width:0" },
    el("div", { class: "card-head" },
      el("h3", { class: "card-title sm" }, icon("AlertTriangle", 16, ""), "Review queue"),
      el("p", { class: "card-desc" },
        "Items the calibrated confidence floors flagged. Blocking items gate exports; advisory items inform the recruiter."),
    ),
    el("div", { class: "card-body" },
      el("div", { style: "display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem" },
        reviewerLabel,
        reviewerInput),
      el("div", { class: "review-scroll" }, queueList),
    ),
  ));

  /* ---------------- right column: export + manifest ------------------ */
  const rightCol = el("div", { class: "stack", style: "min-width:0" });

  const exportList = el("div", { class: "stack-sm" });
  const filesReady = el("span", { class: "text-xs muted" });
  const renderExports = () => {
    clear(exportList);
    filesReady.textContent = state.exports.length > 0 ? `${state.exports.length} files ready` : "";
    for (const f of state.exports) {
      exportList.appendChild(el("div", { class: "download-row" },
        icon("Download", 14),
        el("a", {
          href: "#", onclick: async (ev) => {
            ev.preventDefault();
            try { await downloadReport(results.run_id, f.file); }
            catch (err) { msg.textContent = err.message; msg.classList.add("error"); }
          },
        }, f.kind === "batch" ? "Batch report (ranking + all candidates)" : `Candidate ${f.ref}`),
        el("span", { class: "hash" }, (f.sha256 ?? "").slice(0, 8)),
      ));
    }
  };
  renderExports();

  const pseudoSwitch = switchInput({
    checked: state.pseudonymous, id: "pseudo", ariaLabel: "Pseudonymous reports",
    onChange: (v) => { state.pseudonymous = v; },
  });
  const pseudoLabel = labelFor("pseudo", "Pseudonymous reports (refs only, no folder names)");
  pseudoLabel.classList.add("text-xs");

  rightCol.appendChild(el("div", { class: "card" },
    el("div", { class: "card-head" },
      el("h3", { class: "card-title sm" }, icon("FileDown", 16), "PDF report export"),
      el("p", { class: "card-desc" }, "Batch report with full ranking + one report per candidate. Pseudonymous by default."),
    ),
    el("div", { class: "card-body stack-sm" },
      el("div", { style: "display:flex;align-items:center;gap:0.5rem" },
        pseudoSwitch,
        pseudoLabel),
      el("div", { style: "display:flex;flex-wrap:wrap;align-items:center;gap:0.5rem" },
        button({
          variant: "primary", label: "Generate PDF reports", icon: "FileCheck2", spinIcon: false,
          onclick: exportPdfs,
        }),
        filesReady,
      ),
      msg,
      exportList,
    ),
  ));

  const manifest = results.audit?.manifest;
  const det = results.determinism;

  const kv = (k, v) => el("div", { class: "kv-row" },
    el("span", { class: "k" }, k), el("span", { class: "v" }, String(v ?? "")));

  rightCol.appendChild(el("div", { class: "card" },
    el("div", { class: "card-head" },
      el("h3", { class: "card-title sm" }, icon("Fingerprint", 16), "Run manifest & determinism"),
      el("p", { class: "card-desc" }, "GDPR audit basis: replay-safe, local-only, fully hashed."),
    ),
    el("div", { class: "card-body", style: "font-size:12px" },
      el("div", { style: "display:flex;flex-wrap:wrap;align-items:center;gap:0.5rem" },
        badge([icon("ShieldCheck", 12), ` replay ${det?.identical ? "PASS" : "FAIL"}`],
          det?.identical ? "emerald" : "rose-solid"),
        el("span", { class: "mono", style: "font-size:10px;color:var(--slate-500)" },
          `${(det?.pass1_sha256 ?? "").slice(0, 16)}...`)),
      separator(),
      kv("OmniDecide version", manifest?.omnidecide_version),
      kv("Engine version", manifest?.engine_version),
      kv("Floors data version", manifest?.floors_data_version),
      kv("Main folder", manifest?.main_folder),
      kv("Profile sha256", (manifest?.profile_sha256 ?? "").slice(0, 20) + "..."),
      kv("Engine runtime", `${manifest?.elapsed_seconds ?? 0}s`),
      separator(),
      el("p", { class: "muted" }, "Floors in effect (editable floors-as-data):"),
      el("div", { class: "floors" },
        Object.entries(manifest?.floors_table ?? {}).map(([k, v]) =>
          badge(`${k} ${v}`, "secondary", "badge-10 mono"))),
    ),
  ));

  root.appendChild(rightCol);

  /* ---------------- decision log (full width) ------------------------ */
  const decisionLog = el("div", { class: "stack-sm" });
  function renderDecisionLog() {
    clear(decisionLog);
    if (state.decisions.length === 0) {
      decisionLog.appendChild(el("p", { style: "font-size:14px;color:var(--muted)" }, "No human decisions recorded yet."));
      return;
    }
    for (const d of state.decisions) {
      const cand = d.candidate_ref ? byRef[d.candidate_ref] : null;
      decisionLog.appendChild(el("div", { class: "decision-row" },
        badge(d.action, "secondary", "badge-10"),
        el("span", { class: "strong" }, cand ? cand.folder_name : (d.kind ?? "-")),
        el("span", { class: "muted" }, d.decision ?? ""),
        el("span", { style: "color:var(--slate-400)" }, `by ${d.reviewer}`),
        el("span", { class: "when" }, d.at),
      ));
    }
  }
  renderDecisionLog();
  root.appendChild(el("div", { class: "card span-2" },
    el("div", { class: "card-head" },
      el("h3", { class: "card-title sm" }, icon("CheckCircle2", 16), "Human decision log"),
      el("p", { class: "card-desc" }, "Sign-offs and review resolutions - appended, immutable, JSONL on disk."),
    ),
    el("div", { class: "card-body" }, decisionLog),
  ));

  /* ---------------- actions ------------------------------------------ */
  refreshers.add(() => { renderExports(); renderDecisionLog(); });

  async function resolve(item, decision) {
    if (resolving) return; // audit JSONL is append-only: never double-append
    resolving = true;
    msg.classList.remove("error");
    try {
      await api("/api/audit", {
        method: "POST",
        body: JSON.stringify({
          run_id: results.run_id, action: "resolve", kind: item.kind,
          candidate_ref: item.candidate_ref, decision, reviewer: state.reviewer,
        }),
      });
      await actions.refreshAudit();
      refreshAllGovernance();
      msg.textContent = `Recorded: ${decision === "acknowledge" ? "acknowledged" : "escalated for manual review"}.`;
    } catch (err) {
      msg.textContent = err.message;
      msg.classList.add("error");
    } finally {
      resolving = false;
    }
  }

  async function exportPdfs(ev) {
    if (busy) return;
    busy = true;
    msg.classList.remove("error");
    const btn = ev.currentTarget;
    btn.disabled = true;
    try {
      await api("/api/report", { method: "POST", body: JSON.stringify({ run_id: results.run_id, pseudonymous: state.pseudonymous }) });
      msg.textContent = "PDF reports generated - download them below.";
      await actions.refreshAudit();
      refreshAllGovernance();
    } catch (err) {
      msg.textContent = err.message;
      msg.classList.add("error");
    } finally {
      busy = false;
      btn.disabled = false;
    }
  }

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  return root;
}
