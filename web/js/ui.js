// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// Vanilla UI toolkit for Job Attune: DOM builder, lucide icon rendering,
// modal dialogs (focus-trapped), keyboard-accessible tabs, collapsibles,
// switch/progress primitives. Replaces the ~19 Radix UI components the
// Next.js frontend pulled in; only what this app actually uses is here.

import { ICONS } from "./icons.js";

/* ------------------------------------------------------------------ */
/* DOM builder                                                         */
/* ------------------------------------------------------------------ */

/**
 * el("div", {class: "x", onclick: fn, dataset: {...}}, child, child, ...)
 * Children may be Nodes, strings (text), numbers, null/undefined/false.
 */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs ?? {})) {
    if (value == null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key === "style" && typeof value === "object") Object.assign(node.style, value);
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else if (key === "text") node.textContent = value;
    else if (value === true) node.setAttribute(key, "");
    else node.setAttribute(key, value);
  }
  append(node, children);
  return node;
}

export function append(node, ...children) {
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    node.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

/* ------------------------------------------------------------------ */
/* Icons (lucide strokes, generated into icons.js)                     */
/* ------------------------------------------------------------------ */

export function icon(name, size = 16, cls = "") {
  const inner = ICONS[name];
  if (!inner) return el("span", { class: `ic-missing ${cls}` }, `(${name})`);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", size);
  svg.setAttribute("height", size);
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", `ic ${cls}`);
  svg.innerHTML = inner;
  return svg;
}

/** Replace [data-icon] placeholders inside a root node. */
export function hydrateIcons(root = document) {
  for (const holder of root.querySelectorAll("[data-icon]")) {
    const name = holder.dataset.icon;
    const size = Number(holder.dataset.size || 16);
    const extra = holder.dataset.iconClass || "";
    append(holder, icon(name, size, extra));
    delete holder.dataset.icon;
    delete holder.dataset.size;
    delete holder.dataset.iconClass;
  }
}

/* ------------------------------------------------------------------ */
/* Small styled element factories                                     */
/* ------------------------------------------------------------------ */

export function button({ variant = "primary", size = "", icon: ic, spinIcon = false, label, ...attrs }) {
  const cls = ["btn", variant === "primary" ? "btn-primary" : `btn-${variant}`,
    size === "sm" ? "btn-sm" : size === "xs" ? "btn-xs" : size === "icon" ? "btn-icon" : ""].filter(Boolean).join(" ");
  const btn = el("button", { type: "button", class: cls, ...attrs });
  if (ic) btn.appendChild(icon(ic, size === "sm" ? 14 : size === "xs" ? 12 : 16, spinIcon ? "spin" : ""));
  if (label != null) btn.appendChild(document.createTextNode(label));
  return btn;
}

export function badge(label, variant = "secondary", extra = "") {
  return el("span", { class: `badge badge-${variant} ${extra}`.trim() }, label);
}

export function input(attrs = {}) {
  return el("input", { class: "input", ...attrs });
}

export function textarea(attrs = {}) {
  return el("textarea", { class: "textarea", ...attrs });
}

export function labelFor(target, text) {
  return el("label", { class: "label", for: target }, text);
}

/** Styled native select (replaces the Radix select - same a11y for free). */
export function select(options, attrs = {}) {
  // The legacy `value` attribute does nothing on an empty <select>, so
  // apply it as a property only after the options exist.
  const { value, ...rest } = attrs;
  const sel = el("select", { class: "select", ...rest });
  for (const opt of options) {
    sel.appendChild(el("option", { value: opt.value, disabled: opt.disabled || undefined },
      opt.label));
  }
  if (value != null) sel.value = value;
  return sel;
}

/** Toggle switch built on a real checkbox (keyboard + SR accessible). */
export function switchInput({ checked = false, id, ariaLabel, onChange }) {
  const inputEl = el("input", { type: "checkbox", checked: checked || undefined, ...(id ? { id } : {}) });
  if (ariaLabel) inputEl.setAttribute("aria-label", ariaLabel);
  inputEl.addEventListener("change", () => onChange?.(inputEl.checked));
  const wrap = el("span", { class: "switch", role: "switch", "aria-checked": String(checked) });
  wrap.appendChild(inputEl);
  wrap.appendChild(el("span", { class: "track" }));
  wrap.appendChild(el("span", { class: "thumb" }));
  inputEl.addEventListener("change", () => wrap.setAttribute("aria-checked", String(inputEl.checked)));
  return wrap;
}

/**
 * Collapsible section (button[aria-expanded] + lazily rendered panel).
 * collapsible(triggerContent, () => Node, { open, onToggle })
 */
export function collapsible(triggerContent, renderBody, { open = false, onToggle } = {}) {
  const body = el("div", { class: "collapsible-content", hidden: "" });
  const trig = el("button", {
    type: "button", class: "collapsible-trigger", "aria-expanded": String(open),
    onclick: () => {
      const isOpen = trig.getAttribute("aria-expanded") === "true";
      trig.setAttribute("aria-expanded", String(!isOpen));
      body.hidden = isOpen;
      if (!isOpen && !body.dataset.rendered) {
        append(body, renderBody());
        body.dataset.rendered = "1";
      }
      onToggle?.(!isOpen);
    },
  });
  if (open) {
    body.hidden = false;
    append(body, renderBody());
    body.dataset.rendered = "1";
  }
  append(trig, triggerContent);
  trig.appendChild(icon("ChevronDown", 16, "chevron"));
  return el("div", { class: "collapsible" }, trig, body);
}

export function progressBar(value = 0) {
  const fill = el("div", { class: "progress-bar" });
  fill.style.width = `${Math.max(0, Math.min(100, value))}%`;
  return el("div", { class: "progress" }, fill);
}

export function separator() {
  return el("hr", { class: "separator" });
}

/* ------------------------------------------------------------------ */
/* Modal dialog (focus-trapped, Esc + overlay close)                   */
/* ------------------------------------------------------------------ */

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

let openDialogState = null;

/**
 * openDialog({ title, desc, wide, content, footer }) -> { close, root }
 * Content/footers are nodes or arrays of nodes.
 */
export function openDialog({ title, desc, wide = false, content, footer }) {
  if (openDialogState) openDialogState.close();
  const previouslyFocused = document.activeElement;

  const body = el("div", { class: "dialog-body" });
  append(body, content);

  const dialog = el("div", { class: `dialog ${wide ? "dialog-wide" : ""}`, role: "dialog", "aria-modal": "true" });
  // a Node title is used as-is (it may already be a .dialog-title); strings
  // and arrays are wrapped so callers stay terse
  const titleEl = title instanceof Node ? title : el("div", { class: "dialog-title" }, title);
  const head = el("div", { class: "dialog-head" },
    titleEl,
    desc ? el("p", { class: "dialog-desc" }, desc) : null,
  );
  const closeBtn = el("button", { type: "button", class: "dialog-close", "aria-label": "Close" },
    icon("X", 16));
  closeBtn.addEventListener("click", () => close());
  append(dialog, head, closeBtn, body);
  if (footer) append(dialog, el("div", { class: "dialog-foot" }, footer));

  const overlay = el("div", { class: "dialog-overlay" }, dialog);
  overlay.addEventListener("mousedown", (ev) => {
    if (ev.target === overlay) close();
  });

  function onKeyDown(ev) {
    if (ev.key === "Escape") { ev.preventDefault(); close(); return; }
    if (ev.key === "Tab") {
      const items = [...dialog.querySelectorAll(FOCUSABLE)].filter((n) => n.offsetParent !== null);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
      else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
    }
  }
  document.addEventListener("keydown", onKeyDown, true);

  function close() {
    document.removeEventListener("keydown", onKeyDown, true);
    overlay.remove();
    if (openDialogState?.close === close) openDialogState = null;
    previouslyFocused?.focus?.();
  }

  document.getElementById("dialog-root").appendChild(overlay);
  openDialogState = { close };
  const focusTarget = dialog.querySelector(FOCUSABLE);
  (focusTarget ?? dialog).focus();
  return { close, root: dialog, body };
}

/* ------------------------------------------------------------------ */
/* Tabs (role=tablist, arrow keys, Home/End)                           */
/* ------------------------------------------------------------------ */

/**
 * createTabs([
 *   { id, label, icon, badge },
 *   ...
 * ], panels: Map<id, Node|() => Node>) -> { root, select(id) }
 * Panels render lazily on first activation and stay mounted afterwards.
 */
export function createTabs(tabDefs, panels) {
  const tablist = el("div", { class: "tabs-list", role: "tablist" });
  const panelHost = el("div", { class: "tabs-panel" });
  const built = [];

  for (const def of tabDefs) {
    const tab = el("button", {
      type: "button", class: "tab", role: "tab", id: `tab-${def.id}`,
      "aria-selected": "false", tabindex: "-1",
      "aria-controls": `panel-${def.id}`,
    });
    if (def.icon) tab.appendChild(icon(def.icon, 14));
    tab.appendChild(document.createTextNode(def.label));
    if (def.badge != null) tab.appendChild(badge(def.badge, "outline", "badge-10 badge-amber-soft"));
    tab.addEventListener("click", () => select(def.id));
    tab.addEventListener("keydown", (ev) => {
      const idx = built.findIndex((t) => t.def.id === def.id);
      let next = null;
      if (ev.key === "ArrowRight") next = built[(idx + 1) % built.length];
      else if (ev.key === "ArrowLeft") next = built[(idx - 1 + built.length) % built.length];
      else if (ev.key === "Home") next = built[0];
      else if (ev.key === "End") next = built[built.length - 1];
      if (next) { ev.preventDefault(); select(next.def.id); next.tab.focus(); }
    });
    tablist.appendChild(tab);
    built.push({ def, tab, panel: null });
  }

  function select(id) {
    for (const { def, tab } of built) {
      const active = def.id === id;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? "0" : "-1";
    }
    clear(panelHost);
    const entry = built.find((t) => t.def.id === id);
    if (entry) {
      if (!entry.panel) {
        const src = panels.get(id);
        entry.panel = el("div", { class: "tab-panel", role: "tabpanel", id: `panel-${id}` },
          typeof src === "function" ? src() : src);
      }
      panelHost.appendChild(entry.panel);
    }
  }

  const root = el("div", {}, tablist, panelHost);
  select(tabDefs[0].id);
  return { root, select };
}
