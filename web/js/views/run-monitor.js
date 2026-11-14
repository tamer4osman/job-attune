// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// Step 3 - live progress of the screening run. Port of
// src/components/attune/run-monitor.tsx: polls /api/run/status every 900 ms,
// tolerates 5 consecutive failures, hands off to the results step 600 ms
// after "done" (a reset inside that window cancels the hand-off).

import { api } from "../api.js";
import { el, button, icon, progressBar, append, clear } from "../ui.js";

const STAGE_ORDER = ["boot", "scan", "gates", "evidence", "scoring", "decisions", "verify", "done"];

const STAGE_LABELS = {
  boot: "Engine starting",
  scan: "Scanning candidate folders",
  gates: "Text extraction + readability gates",
  evidence: "Evidence extraction (OmniDecide extract)",
  scoring: "Scoring + aggregation",
  decisions: "Shortlist / tie-break / ranking",
  verify: "Determinism verification (second pass)",
  done: "Complete",
};

const MAX_POLL_FAILURES = 5;

export function RunMonitor(state, actions) {
  const runId = state.runId;
  let stopped = false;
  let finished = false;
  let failed = null;
  let failures = 0;
  let timer = null;
  let interval = null;

  const card = el("div", { class: "card card-emerald" });
  const head = el("div", { class: "card-head" },
    el("h2", { class: "card-title" }, icon("Cpu", 20), "Screening run in progress"),
    el("p", { class: "card-desc" },
      "Run ID ", el("span", { class: "mono" }, runId),
      " - the pipeline executes fully locally and runs twice to prove deterministic replay."),
  );
  const body = el("div", { class: "card-body stack" });
  append(card, head, body);

  const stageLabel = el("span", { class: "strong" }, "Starting engine...");
  const pctLabel = el("span", { class: "muted" }, "0%");
  const progress = progressBar(0);
  const message = el("p", { class: "text-xs muted" }, "Booting the OmniDecide kernel...");
  const stageGrid = el("div", { class: "stage-grid" });
  const stageNodes = {};
  for (const k of STAGE_ORDER) {
    if (k === "boot" || k === "done") continue;
    const node = el("div", { class: "stage stage-todo" }, el("span", { class: "dot" }), STAGE_LABELS[k]);
    stageNodes[k] = node;
    stageGrid.appendChild(node);
  }
  const viewBtn = button({ variant: "primary", label: "View results", icon: "ArrowRight", class: "hidden", onclick: actions.onDone });

  body.appendChild(el("div", { class: "stack-sm" },
    el("div", { style: "display:flex;align-items:center;justify-content:space-between;font-size:14px" },
      stageLabel, pctLabel),
    progress,
    message,
  ));
  body.appendChild(stageGrid);
  body.appendChild(el("div", { style: "display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:0.5rem" },
    el("div", { class: "file-row", style: "color: var(--muted); font-size: 12px" },
      icon("ShieldCheck", 14),
      "Six OmniDecide primitives in use: noul, extract, score, choice, compare, rank"),
    viewBtn,
  ));

  function renderProgress(p) {
    stageLabel.textContent = STAGE_LABELS[p.stage] ?? p.stage;
    pctLabel.textContent = `${Math.round(p.pct ?? 0)}%`;
    progress.firstChild.style.width = `${Math.max(0, Math.min(100, p.pct ?? 0))}%`;
    message.textContent = p.message ?? "Booting the OmniDecide kernel...";
    const idx = STAGE_ORDER.indexOf(p.stage);
    const effective = idx === -1 ? 0 : idx;
    const doneIdx = STAGE_ORDER.indexOf("done");
    for (const k of Object.keys(stageNodes)) {
      const kIdx = STAGE_ORDER.indexOf(k);
      const isDone = effective >= doneIdx || effective > kIdx;
      const isActive = !isDone && effective === kIdx;
      const node = stageNodes[k];
      node.className = `stage ${isDone ? "stage-done" : isActive ? "stage-active" : "stage-todo"}`;
      const mark = node.firstChild;
      if (isDone) {
        node.replaceChild(icon("CheckCircle2", 14), mark);
      } else if (isActive) {
        node.replaceChild(icon("Loader2", 14, "spin"), mark);
      } else if (!(mark instanceof SVGElement)) {
        node.replaceChild(el("span", { class: "dot" }), mark);
      }
    }
  }

  function renderFailed(messageText) {
    const title = head.querySelector(".card-title");
    clear(title); // drop the spinner icon and stale "in progress" text
    title.appendChild(icon("AlertTriangle", 20));
    title.appendChild(document.createTextNode("Screening run failed."));
    card.classList.add("band-weak");
    clear(body);
    body.appendChild(el("div", {
      class: "alert alert-destructive", role: "alert",
    }, icon("AlertTriangle", 16), el("div", {}, messageText)));
    body.appendChild(el("div", { style: "display:flex;align-items:center;justify-content:space-between;gap:0.5rem" },
      el("div", { class: "file-row", style: "color: var(--muted); font-size: 12px" },
        icon("ShieldCheck", 14), "Six OmniDecide primitives in use: noul, extract, score, choice, compare, rank"),
      null));
  }

  async function tick() {
    if (stopped || finished || failed !== null) return;
    try {
      const p = await api(`/api/run/status?run_id=${encodeURIComponent(runId)}`);
      if (stopped) return;
      failures = 0;
      renderProgress(p);
      if (p.stage === "error") {
        failed = p.message || "The screening run failed.";
        renderFailed(failed);
      } else if (p.stage === "done") {
        finished = true;
        viewBtn.classList.remove("hidden");
        // guard the delayed hand-off: a reset inside the 600 ms window must
        // not yank the wizard back to the results step
        timer = setTimeout(() => { if (!stopped) actions.onDone(); }, 600);
      }
    } catch {
      failures += 1;
      if (!stopped && failures >= MAX_POLL_FAILURES) {
        failed = `Lost contact with the run after ${MAX_POLL_FAILURES} failed polls - it may have crashed.`;
        renderFailed(failed);
      }
    }
  }

  tick();
  interval = setInterval(tick, 900);

  function destroy() {
    stopped = true;
    clearInterval(interval);
    if (timer) clearTimeout(timer);
  }

  return { root: card, destroy };
}
