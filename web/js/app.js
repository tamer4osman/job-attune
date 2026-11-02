// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// App bootstrap + top-level state. Port of src/app/page.tsx: the four-step
// wizard (candidates -> job profile -> run -> results) with the stepper,
// header "New run" control and the results workspace.

import { api, toEngineProfile, EMPTY_PROFILE } from "./api.js";
import { el, icon, hydrateIcons, clear, append } from "./ui.js";
import { FolderPicker } from "./views/folder-picker.js";
import { JobProfileEditor } from "./views/job-profile.js";
import { RunMonitor } from "./views/run-monitor.js";
import { ResultsView } from "./views/results.js";

const STEPS = [
  { id: 1, label: "Candidates", icon: "FolderOpen" },
  { id: 2, label: "Job profile", icon: "FileSignature" },
  { id: 3, label: "Run", icon: "BrainCircuit" },
  { id: 4, label: "Results", icon: "BarChart3" },
];

const state = {
  step: 1,
  folderPath: "attune-sample-data/candidates",
  scanned: null,
  scanning: false,
  scanError: null,
  folder: "",
  roleOverrides: {},
  profile: EMPTY_PROFILE(),
  runId: null,
  starting: false,
  startError: null,
  results: null,
  resultsError: null,
  decisions: [],
  exports: [],
  reviewer: "",
  pseudonymous: true,
};

const main = document.getElementById("main");
const stepperHost = document.getElementById("stepper");
const newRunBtn = document.getElementById("new-run-btn");
let cleanup = null; // poller teardown of the run monitor, if mounted

/* ------------------------------------------------------------------ */
/* Actions                                                             */
/* ------------------------------------------------------------------ */

const actions = {
  async scan(path) {
    state.scanning = true;
    state.scanError = null;
    render();
    try {
      const data = await api("/api/scan", { method: "POST", body: JSON.stringify({ folder: path }) });
      state.scanned = data;
      state.folder = data.folder;
    } catch (err) {
      state.scanned = null;
      state.scanError = err.message;
    } finally {
      state.scanning = false;
      render();
    }
  },

  onRoleChange(relPath, role) {
    state.roleOverrides[relPath] = role;
    const scanned = state.scanned;
    if (!scanned) return;
    for (const c of scanned.candidates) {
      let hasCv = false, hasCover = false;
      for (const f of c.files) {
        const eff = f.relPath === relPath ? role : f.role;
        if (eff === "cv") hasCv = true;
        if (eff === "cover") hasCover = true;
      }
      c.hasCv = hasCv;
      c.hasCover = hasCover;
      for (const f of c.files) if (f.relPath === relPath) f.role = role;
    }
    render();
  },

  confirm() {
    state.step = 2;
    render();
  },

  async startRun() {
    if (state.starting) return; // double-submit guard: never spawn two engines
    state.starting = true;
    state.startError = null;
    render();
    try {
      const engineProfile = toEngineProfile(state.profile, state.roleOverrides, true);
      const d = await api("/api/run", {
        method: "POST",
        body: JSON.stringify({ folder: state.folder, profile: engineProfile }),
      });
      state.results = null;
      state.exports = [];
      state.runId = d.runId;
      state.step = 3;
    } catch (err) {
      state.startError = err.message;
    } finally {
      state.starting = false;
      render();
    }
  },

  async onDone() {
    state.resultsError = null;
    if (!state.runId) {
      state.step = 4;
      render();
      return;
    }
    try {
      await loadResults(state.runId);
    } catch (err) {
      if (state.runId !== null) state.resultsError = err.message;
    }
    state.step = 4;
    render();
  },

  async refreshAudit() {
    if (state.runId) await loadResults(state.runId).catch(() => {});
  },

  reset() {
    state.step = 1;
    state.scanned = null;
    state.results = null;
    state.runId = null;
    state.exports = [];
    state.decisions = [];
    state.roleOverrides = {};
    state.resultsError = null;
    state.startError = null;
    render();
  },

  render,

  starting: () => state.starting,
};

async function loadResults(runId) {
  const d = await api(`/api/run/results?run_id=${encodeURIComponent(runId)}`);
  if (state.runId !== runId) return; // stale response guard (reset/new run)
  state.results = d.results;
  state.decisions = d.decisions ?? [];
  state.exports = d.exports ?? [];
}

/* ------------------------------------------------------------------ */
/* Rendering                                                           */
/* ------------------------------------------------------------------ */

function renderStepper() {
  clear(stepperHost);
  const li = STEPS.map((s, i) => {
    const stepState = state.step === s.id ? "current" : state.step > s.id ? "done" : "todo";
    const btn = el("button", {
      type: "button", class: "step", "data-state": stepState,
      "aria-current": stepState === "current" ? "step" : undefined,
      disabled: stepState === "todo" || undefined,
      onclick: stepState === "done" ? () => { state.step = s.id; render(); } : undefined,
    },
      stepState === "done" ? icon("CheckCircle2", 16) : icon(s.icon, 16),
      el("span", { class: "step-label" }, s.label));
    return el("li", { style: "display:flex;align-items:center;gap:0.5rem" }, btn,
      i < STEPS.length - 1 ? el("span", { class: "step-sep", "aria-hidden": "true" }) : null);
  });
  append(stepperHost, li);

  const showNewRun = !!(state.results || state.runId);
  newRunBtn.classList.toggle("hidden", !showNewRun);
}

function renderMain() {
  cleanup?.();
  cleanup = null;
  clear(main);

  if (state.step === 1) {
    main.appendChild(FolderPicker(state, actions));
  } else if (state.step === 2) {
    const wrap = el("div", { class: "stack" });
    if (state.startError) wrap.appendChild(el("p", { class: "error-text", style: "font-size:14px" }, state.startError));
    wrap.appendChild(JobProfileEditor(state, actions));
    if (state.starting) wrap.appendChild(el("p", { class: "ok-text", style: "font-size:14px" }, "Starting engine..."));
    main.appendChild(wrap);
  } else if (state.step === 3) {
    const monitor = RunMonitor(state, actions);
    cleanup = monitor.destroy;
    main.appendChild(monitor.root);
  } else if (state.step === 4 && !state.results) {
    main.appendChild(el("div", {
      class: "card", style: "max-width:28rem;margin:0 auto;text-align:center",
    },
      el("div", { class: "card-body stack-sm" },
        el("p", { class: "strong error-text", style: "font-size:14px" }, "Results could not be loaded"),
        el("p", { class: "text-xs muted" }, state.resultsError ?? "The run has no results yet."),
        el("div", { style: "display:flex;justify-content:center;gap:0.5rem" },
          buttonOutline("Retry", actions.onDone),
          buttonOutline("New run", actions.reset)),
      )));
  } else if (state.step === 4 && state.results) {
    main.appendChild(ResultsView(state, actions));
  }
}

function buttonOutline(label, onclick) {
  const btn = el("button", { type: "button", class: "btn btn-outline", onclick }, label);
  return btn;
}

function render() {
  renderStepper();
  renderMain();
}

/* ------------------------------------------------------------------ */
/* Boot                                                                */
/* ------------------------------------------------------------------ */

newRunBtn.addEventListener("click", actions.reset);
hydrateIcons(document);
render();
