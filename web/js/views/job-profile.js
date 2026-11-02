// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// Step 2 - company & job profile editor. Port of
// src/components/attune/job-profile.tsx. Inputs mutate the shared profile
// state directly and only refresh derived labels (counts, badges), so
// typing never loses focus.

import { api, CATEGORY_KEYS, CATEGORY_LABELS, toEngineProfile, fromEngineProfile } from "../api.js";
import { el, button, badge, input, textarea, labelFor, select, switchInput, collapsible, icon, append, clear, openDialog } from "../ui.js";

const CATEGORY_ICONS = {
  soft_skills: ["HeartPulse", "var(--rose-600)"],
  technical_skills: ["Wrench", "var(--emerald-700)"],
  languages: ["Languages", "var(--teal-700)"],
  degrees: ["GraduationCap", "var(--amber-700)"],
  certifications: ["Award", "var(--lime-700)"],
  bootcamps: ["BookOpenCheck", "var(--cyan-700)"],
};

// open/closed state of the six category collapsibles (persists while the
// app runs; technical skills starts open, as in the React version)
const openState = { technical_skills: true };

export function JobProfileEditor(state, actions) {
  const root = el("div", { class: "stack" });
  let msg = null;

  function setMsg(text) {
    msg?.remove();
    msg = text ? el("p", { class: "inline-msg" }, text) : null;
    if (msg) root.insertBefore(msg, root.querySelector(".action-bar"));
  }

  /* ---------------- company & job card ------------------------------ */
  const companyName = input({ id: "cname", value: state.profile.company.name, placeholder: "NovaGrid Energy",
    oninput: (ev) => { state.profile.company.name = ev.target.value; } });
  const jobTitle = input({ id: "jtitle", value: state.profile.job.title, placeholder: "Senior Data Engineer",
    oninput: (ev) => { state.profile.job.title = ev.target.value; updateTotals(); } });
  const summary = textarea({ id: "csummary", rows: 2, placeholder: "What the company does, in two sentences.",
    oninput: (ev) => { state.profile.company.summary = ev.target.value; } });
  summary.value = state.profile.company.summary;
  const values = textarea({ id: "cvalues", rows: 3, placeholder: "safety first\nreliable engineering\nopen communication",
    oninput: (ev) => { state.profile.company.valuesText = ev.target.value; } });
  values.value = state.profile.company.valuesText;
  const jobDesc = textarea({ id: "jdesc", rows: 3, placeholder: "What the person will do.",
    oninput: (ev) => { state.profile.job.description = ev.target.value; } });
  jobDesc.value = state.profile.job.description;

  root.appendChild(el("div", { class: "card card-emerald" },
    el("div", { class: "card-head" },
      el("div", { class: "card-head-row" },
        el("div", {},
          el("h2", { class: "card-title" }, icon("Building2", 20), "Company & job profile"),
          el("p", { class: "card-desc" },
            "Who is hiring, what the role is, and which skills matter. Each skill gets its own field so the full requirements list fits."),
        ),
        el("div", { class: "scan-actions" },
          button({ variant: "outline", size: "sm", label: "Load example", icon: "Sparkles",
            onclick: () => loadTemplate("example-senior-data-engineer") }),
          button({ variant: "outline", size: "sm", label: "Templates", icon: "FileSignature",
            onclick: () => openTemplates() }),
        ),
      ),
    ),
    el("div", { class: "card-body grid-2", style: "gap:1rem" },
      el("div", { class: "field" }, labelFor("cname", "Company name"), companyName),
      el("div", { class: "field" }, labelFor("jtitle", "Job title"), jobTitle),
      el("div", { class: "field", style: "grid-column: 1 / -1" }, labelFor("csummary", "Company summary"), summary),
      el("div", { class: "field" }, labelFor("cvalues", "Company values (one per line or comma-separated)"), values),
      el("div", { class: "field" }, labelFor("jdesc", "Job description"), jobDesc),
    ),
  ));

  /* ---------------- requirement categories -------------------------- */
  const categoriesHost = el("div", { class: "grid-2", style: "gap:0.75rem" });
  root.appendChild(categoriesHost);

  const countBadges = {}; // key -> {skills, must}
  const bodies = {};      // key -> content node inside the collapsible

  for (const key of CATEGORY_KEYS) {
    const [icName, icColor] = CATEGORY_ICONS[key];
    const ic = icon(icName, 16);
    if (icColor) ic.style.color = icColor;

    const skillsBadge = badge("", "emerald-soft");
    const mustBadge = badge("", "outline", "badge-11 badge-amber-soft");
    mustBadge.style.display = "none";
    countBadges[key] = { skills: skillsBadge, must: mustBadge };

    const host = el("div", { class: "stack-sm" });
    bodies[key] = host;
    categoriesHost.appendChild(collapsible(
      [ic, el("span", { class: "strong", style: "flex:1" }, CATEGORY_LABELS[key]), skillsBadge, mustBadge],
      () => { renderCategory(key, host); return host; },
      {
        open: openState[key] === true,
        onToggle: (isOpen) => { openState[key] = isOpen; },
      },
    ));
  }

  function renderCategory(key, host) {
    while (host.firstChild) host.removeChild(host.firstChild);
    const rows = state.profile.categories[key];
    if (rows.length === 0) {
      host.appendChild(el("p", { class: "text-xs muted" }, "No skills yet - add the first one."));
    }
    for (let idx = 0; idx < rows.length; idx++) host.appendChild(skillRow(key, idx));
    host.appendChild(button({
      variant: "outline", size: "sm", label: "Add skill", icon: "Plus",
      class: "btn btn-outline btn-sm btn-dashed", style: "width:100%",
      onclick: () => {
        rows.push({ id: Date.now() + Math.random(), skill: "", weight: 1, mustHave: false, aliases: "" });
        renderCategory(key, host);
        updateBadges(key);
        updateTotals();
      },
    }));
  }
  function skillRow(key, idx) {
    const row = state.profile.categories[key][idx];
    const weightBadge = badge(`${row.weight}x`, "secondary", "text-xs");

    const skillInput = input({
      value: row.skill, placeholder: "Skill, e.g. Apache Airflow", class: "input input-sm",
      oninput: (ev) => { row.skill = ev.target.value; },
    });
    const aliasesInput = input({
      value: row.aliases, placeholder: "Aliases, comma-separated (e.g. airflow, dags)",
      class: "input input-dashed input-xs", style: "margin-top:0.5rem",
      oninput: (ev) => { row.aliases = ev.target.value; },
    });
    const slider = el("input", {
      type: "range", class: "slider", min: "0.5", max: "3", step: "0.5", value: String(row.weight),
      "aria-label": `Weight for ${row.skill || "skill"}`,
    });
    slider.addEventListener("input", () => {
      row.weight = Number(slider.value);
      weightBadge.textContent = `${row.weight}x`;
    });

    return el("div", { class: "skill-row" },
      el("div", { class: "skill-row-top" },
        skillInput,
        button({
          variant: "ghost", size: "sm", class: "btn btn-ghost btn-sm btn-icon", "aria-label": "Remove skill",
          icon: "Trash2",
          onclick: () => {
            state.profile.categories[key].splice(idx, 1);
            renderCategory(key, bodies[key]);
            updateBadges(key);
            updateTotals();
          },
        }),
      ),
      el("div", { class: "skill-row-meta" },
        el("div", { class: "weight-group" },
          el("span", { class: "weight-label" }, "Weight"), slider, weightBadge),
        el("div", { class: "musthave-group" },
          switchInput({
            checked: row.mustHave, ariaLabel: "Must-have",
            onChange: (v) => { row.mustHave = v; updateBadges(key); updateTotals(); },
          }),
          el("span", { class: "text-xs muted" }, "Must-have"),
        ),
      ),
      aliasesInput,
    );
  }

  function updateBadges(key) {
    const rows = state.profile.categories[key];
    const mustCount = rows.filter((r) => r.mustHave).length;
    countBadges[key].skills.textContent = `${rows.length} skills`;
    countBadges[key].must.style.display = mustCount > 0 ? "" : "none";
    countBadges[key].must.textContent = `${mustCount} must-have`;
  }

  /* ---------------- action bar + totals ------------------------------ */
  const totalsEl = el("p", { class: "text-sm muted" });
  const startBtn = button({
    variant: "primary", label: "Start screening run", icon: "Save",
    onclick: actions.startRun,
  });
  root.appendChild(el("div", { class: "action-bar" }, totalsEl, startBtn));

  function updateTotals() {
    const totalSkills = CATEGORY_KEYS.reduce((n, k) => n + state.profile.categories[k].length, 0);
    const totalMust = CATEGORY_KEYS.reduce((n, k) => n + state.profile.categories[k].filter((r) => r.mustHave).length, 0);
    clear(totalsEl);
    append(totalsEl,
      el("span", { class: "strong" }, String(totalSkills)), " skills across 6 categories, ",
      el("span", { class: "strong warn-text" }, String(totalMust)), " marked must-have.",
      !state.profile.job.title.trim() ? el("span", { class: "warn-text" }, " - add a job title first.") : null,
      state.profile.job.title.trim() && totalSkills === 0 ? el("span", { class: "warn-text" }, " - add at least one skill.") : null,
    );
    startBtn.disabled = actions.starting() || !state.profile.job.title.trim() || totalSkills === 0;
    startBtn.textContent = "";
    append(startBtn, icon("Save", 16), actions.starting() ? "Starting..." : "Start screening run");
  }

  for (const key of CATEGORY_KEYS) updateBadges(key);
  updateTotals();

  /* ---------------- templates ---------------------------------------- */
  async function loadTemplate(name) {
    try {
      const d = await api(`/api/template?name=${encodeURIComponent(name)}`);
      const converted = fromEngineProfile(d.profile);
      converted.profileName = d.profile.profileName ?? name;
      state.profile = converted;
      actions.render();
      setMsg(`Loaded template "${name}".`);
    } catch (err) {
      setMsg(err.message);
    }
  }

  async function saveTemplate(saveName) {
    if (!saveName.trim()) return;
    try {
      const engineProfile = toEngineProfile({ ...state.profile, profileName: saveName.trim() }, {}, true);
      await api("/api/template", { method: "POST", body: JSON.stringify({ action: "save", name: saveName.trim(), profile: engineProfile }) });
      setMsg(`Template "${saveName.trim()}" saved for reuse.`);
      return true;
    } catch (err) {
      setMsg(err.message);
      return false;
    }
  }

  function openTemplates() {
    let templates = [];
    let tplError = null;
    const msgLine = el("p", { class: "inline-msg" });
    const errLine = el("p", { class: "inline-msg error" });
    const nameInput = input({ id: "tplname", placeholder: "e.g. Senior DE spring" });
    const listSel = select([{ value: "", label: "Loading templates...", disabled: true }], {
      "aria-label": "Load a saved template",
      onchange: (ev) => { if (ev.target.value) loadTemplate(ev.target.value); },
    });

    const { body } = openDialog({
      title: "Profile templates",
      content: el("div", { class: "stack-sm" },
        msgLine, errLine,
        el("div", { class: "field" },
          labelFor("tplname", "Save current profile as"),
          el("div", { class: "scan-actions" },
            nameInput,
            button({ variant: "primary", size: "sm", label: "Save", onclick: async () => {
              if (await saveTemplate(nameInput.value)) { msgLine.textContent = `Template "${nameInput.value.trim()}" saved for reuse.`; nameInput.value = ""; }
            } }),
          ),
        ),
        listSel,
      ),
    });

    api("/api/template")
      .then((d) => {
        templates = d.templates;
        tplError = null;
        errLine.textContent = "";
        rebuildList();
      })
      .catch((err) => { errLine.textContent = err.message; });

    function rebuildList() {
      while (listSel.firstChild) listSel.removeChild(listSel.firstChild);
      if (templates.length === 0) {
        listSel.appendChild(el("option", { value: "", disabled: "" }, "No templates yet"));
        return;
      }
      listSel.appendChild(el("option", { value: "" }, "Load a saved template..."));
      for (const t of templates) listSel.appendChild(el("option", { value: t.name }, t.title));
      listSel.value = "";
    }
    rebuildList();
  }

  return root;
}
