// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// Step 1 - select & validate the applicant folder. Port of
// src/components/attune/folder-picker.tsx.

import { api, fmtBytes } from "../api.js";
import { el, button, badge, input, labelFor, select, openDialog, icon, append, clear } from "../ui.js";

export function FolderPicker(state, actions) {
  const root = el("div", { class: "stack" });

  /* ---------------- card 1: path input + browse + scan -------------- */
  const pathInput = input({
    id: "folder", value: state.folderPath, placeholder: "/path/to/applicants",
    class: "input input-mono", "aria-label": "Main folder path",
    oninput: (ev) => { state.folderPath = ev.target.value; },
    onkeydown: (ev) => { if (ev.key === "Enter") actions.scan(state.folderPath); },
  });

  const scanBtn = button({
    variant: "primary", label: "Scan folder",
    icon: state.scanning ? "Loader2" : "Search", spinIcon: state.scanning,
    disabled: state.scanning || !state.folderPath.trim(),
    onclick: () => actions.scan(state.folderPath),
  });

  root.appendChild(el("div", { class: "card card-emerald" },
    el("div", { class: "card-head" },
      el("h2", { class: "card-title" }, icon("FolderOpen", 20), "Select the applicant main folder"),
      el("p", { class: "card-desc" },
        "One sub-folder per candidate, each holding a CV (PDF) and an optional cover letter. Everything is processed locally - no uploads, no cloud."),
    ),
    el("div", { class: "card-body stack-sm" },
      el("div", { class: "scan-toolbar" },
        el("div", { class: "grow" }, pathInput),
        el("div", { class: "scan-actions" },
          button({ variant: "outline", label: "Browse", icon: "Folder", onclick: () => openBrowse(state.folderPath) }),
          scanBtn,
        ),
      ),
      el("div", { class: "file-row", style: "color: var(--muted); font-size: 12px" },
        icon("ShieldCheck", 14, ""), "Local-first: files are read from disk and never leave this machine."),
      state.scanError ? el("div", { class: "alert alert-destructive", role: "alert" },
        icon("AlertTriangle", 16), el("div", {}, state.scanError)) : null,
    ),
  ));

  /* ---------------- card 2: validation preview ---------------------- */
  if (state.scanned) {
    const scanned = state.scanned;
    const allTagged = scanned.candidates.every((c) => c.files.every((f) => f.role !== "unclassified"));
    const notes = scanned.notes.map((n, i) =>
      el("div", { class: "alert alert-warn", key: i },
        icon("AlertTriangle", 16),
        el("div", {}, typeof n === "string" ? n : `${n.folder}: ${n.note}`)));

    const tiles = scanned.candidates.map((c) => {
      const fileRows = c.files.map((f) => {
        const sel = select(
          [
            { value: "cv", label: "CV" },
            { value: "cover", label: "Cover letter" },
          ],
          {
            "aria-label": `Role for ${f.relPath}`, value: f.role,
            class: `select ${f.role === "unclassified" ? "select-amber" : ""}`,
            onchange: (ev) => actions.onRoleChange(f.relPath, ev.target.value),
          },
        );
        return el("div", { class: "file-row" },
          icon("FileText", 14, ""),
          el("span", { class: "fname" }, f.name),
          el("span", { class: "fsize" }, fmtBytes(f.sizeBytes)),
          sel,
        );
      });
      return el("div", { class: "candidate-tile" },
        el("div", { class: "candidate-tile-head" },
          icon("UserRound", 16, "muted"),
          el("span", { class: "name" }, c.folder),
          !c.hasCv ? badge("no CV", "outline", "badge-11 badge-rose-soft") : null,
          c.hasCv && !c.hasCover ? badge("no cover letter", "outline", "badge-11 badge-amber-soft") : null,
        ),
        el("hr", { class: "separator" }),
        el("div", {}, fileRows),
      );
    });

    root.appendChild(el("div", { class: "card card-emerald" },
      el("div", { class: "card-head" },
        el("h2", { class: "card-title" }, "Validation preview"),
        el("p", { class: "card-desc" },
          `${scanned.candidates.length} candidate${scanned.candidates.length === 1 ? "" : "s"} detected in `,
          el("span", { class: "mono text-xs" }, scanned.folder),
          ". Re-tag a file if the automatic classification missed."),
      ),
      el("div", { class: "card-body stack-sm" },
        ...notes,
        el("div", { class: "grid-3" }, tiles),
        el("div", { class: "action-bar", style: "padding: 0.5rem 0; border: 0; box-shadow: none; background: transparent" },
          el("p", { class: "text-xs muted" },
            allTagged ? "All files classified." : "Some files are unclassified - tag them above."),
          button({
            variant: "primary", label: "Continue to job profile", icon: "ArrowRight",
            disabled: scanned.candidates.length === 0 || !allTagged,
            onclick: actions.confirm,
          }),
        ),
      ),
    ));
  }

  /* ---------------- browse dialog ----------------------------------- */
  async function openBrowse(start) {
    const { body } = openDialog({
      title: [icon("FolderOpen", 16), "Choose the main folder"],
      wide: false,
      content: el("div", { class: "flex-center", style: "height:10rem;display:flex;align-items:center;justify-content:center" },
        icon("Loader2", 24, "spin"),
      ),
    });
    let browse;
    try {
      try {
        browse = await api("/api/browse", { method: "POST", body: JSON.stringify({ path: start ?? "" }) });
      } catch {
        // fallback: start from the project root if the typed path is unreadable
        browse = await api("/api/browse", { method: "POST", body: JSON.stringify({ path: "" }) });
      }
    } catch (err) {
      renderBrowseError(body, err.message);
      return;
    }
    renderBrowse(body, browse);
  }

  function renderBrowseError(body, message) {
    clear(body);
    append(body, el("div", {
      class: "error-text", style: "height:10rem;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:0.5rem;font-size:14px",
    }, icon("AlertTriangle", 20), message));
  }

  function renderBrowse(body, browse) {
    clear(body);
    const list = el("div", { class: "browse-list" });
    if (browse.directories.length === 0) {
      list.appendChild(el("p", { class: "text-xs muted", style: "padding:0.75rem" }, "No sub-directories."));
    }
    for (const d of browse.directories) {
      list.appendChild(el("button", {
        type: "button", class: "browse-item",
        onclick: async () => {
          clear(list);
          list.appendChild(el("p", { class: "text-xs muted", style: "padding:0.75rem" }, "Loading..."));
          try {
            const next = await api("/api/browse", { method: "POST", body: JSON.stringify({ path: d.path }) });
            renderBrowse(body, next);
          } catch (err) {
            renderBrowseError(body, err.message);
          }
        },
      }, icon("Folder", 16), el("span", { class: "nm" }, d.name)));
    }
    append(body, el("div", { class: "stack-sm" },
      el("div", { class: "browse-path" }, browse.path),
      el("div", { class: "scan-actions" },
        button({
          variant: "outline", size: "sm", label: "Up", icon: "FolderUp",
          disabled: !browse.parent,
          onclick: () => openBrowseRefresh(body, browse.parent),
        }),
        button({
          variant: "primary", size: "sm", label: "Use this folder", icon: "CheckCircle2",
          onclick: () => { state.folderPath = browse.path; pathInput.value = browse.path; closeTopDialog(); },
        }),
      ),
      list,
    ));
  }

  async function openBrowseRefresh(body, path) {
    clear(body);
    append(body, el("div", { style: "height:10rem;display:flex;align-items:center;justify-content:center" }, icon("Loader2", 24, "spin")));
    try {
      renderBrowse(body, await api("/api/browse", { method: "POST", body: JSON.stringify({ path }) }));
    } catch (err) {
      renderBrowseError(body, err.message);
    }
  }

  function closeTopDialog() {
    document.querySelector(".dialog-overlay .dialog-close")?.click();
  }


  return root;
}
