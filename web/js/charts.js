// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 Tamer Osman
//
// Hand-rolled SVG charts for the Job Attune overview tab - the vanilla
// replacement for the Recharts dependency (funnel, radar, histogram,
// escalation bars). No external library: charts redraw on container resize
// via ResizeObserver and show a hover tooltip like Recharts did.

import { el, icon } from "./ui.js";

const NS = "http://www.w3.org/2000/svg";

/* Chart colors reference the CSS design tokens so they track theme changes. */
export const EMERALD = "var(--emerald-500)";
const TEAL = "var(--teal-500)";
export const AMBER = "var(--amber-500)";
export const ROSE = "var(--rose-500)";
const GRID = "var(--slate-200)";
const TEXT = "var(--slate-500)";

/* ------------------------------------------------------------------ */
/* plumbing                                                            */
/* ------------------------------------------------------------------ */

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

let tooltipEl = null;
function tooltip(text) {
  if (!tooltipEl) {
    tooltipEl = document.createElement("div");
    tooltipEl.className = "chart-tooltip";
    tooltipEl.style.display = "none";
    document.body.appendChild(tooltipEl);
  }
  tooltipEl.textContent = text;
  tooltipEl.style.display = "block";
}
function moveTooltip(ev) {
  if (!tooltipEl || tooltipEl.style.display === "none") return;
  const pad = 12;
  let x = ev.clientX + pad;
  let y = ev.clientY + pad;
  const rect = tooltipEl.getBoundingClientRect();
  if (x + rect.width > window.innerWidth - 8) x = ev.clientX - rect.width - pad;
  if (y + rect.height > window.innerHeight - 8) y = ev.clientY - rect.height - pad;
  tooltipEl.style.left = `${x}px`;
  tooltipEl.style.top = `${y}px`;
}
function hideTooltip() {
  if (tooltipEl) tooltipEl.style.display = "none";
}

function bindTip(shape, getText) {
  // getText may be a plain string or a callback resolving on mouseenter.
  shape.addEventListener("mouseenter", (ev) => {
    tooltip(typeof getText === "function" ? getText(ev) : getText);
    moveTooltip(ev);
  });
  shape.addEventListener("mousemove", moveTooltip);
  shape.addEventListener("mouseleave", hideTooltip);
}

/** Mount a chart that (re)draws itself into the container at its size. */
function responsive(container, draw) {
  const render = () => {
    const width = container.clientWidth || 480;
    const height = container.clientHeight || 200;
    container.querySelectorAll("svg").forEach((s) => s.remove());
    const svg = svgEl("svg", { width, height, viewBox: `0 0 ${width} ${height}` });
    draw(svg, width, height);
    container.appendChild(svg);
  };
  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(render).observe(container);
  } else {
    window.addEventListener("resize", render);
  }
  render();
  return container;
}

function niceMax(value) {
  if (value <= 5) return 5;
  const pow = Math.pow(10, Math.floor(Math.log10(value)));
  return Math.ceil(value / pow) * pow;
}

function text(svg, x, y, str, { size = 11, anchor = "middle", fill = TEXT, weight } = {}) {
  const t = svgEl("text", { x, y, "font-size": size, fill, "text-anchor": anchor });
  if (weight) t.setAttribute("font-weight", weight);
  t.textContent = str;
  svg.appendChild(t);
  return t;
}

/** Bar path with only the given corners rounded (r>0), horizontal or vertical. */
function barPath(x, y, w, h, r, side) {
  r = Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2);
  if (r <= 0 || w <= 0 || h <= 0) return `M${x},${y}h${w}v${h}h${-w}Z`;
  if (side === "right") {
    return `M${x},${y} H${x + w - r} A${r},${r} 0 0 1 ${x + w},${y + r} V${y + h - r} A${r},${r} 0 0 1 ${x + w - r},${y + h} H${x} Z`;
  }
  // top (vertical bars)
  return `M${x},${y + h} V${y + r} A${r},${r} 0 0 1 ${x + r},${y} H${x + w - r} A${r},${r} 0 0 1 ${x + w},${y + r} V${y + h} Z`;
}

/* ------------------------------------------------------------------ */
/* Horizontal bar chart (funnel, escalations)                          */
/* ------------------------------------------------------------------ */

/**
 * hbarChart(container, { items: [{label, value, fill, fillOpacity}],
 * barSize, labelWidth, tickSize })
 */
export function hbarChart(container, { items, barSize = 22, labelWidth = 150, tickSize = 10.5 }) {
  return responsive(container, (svg, width, height) => {
    const max = niceMax(Math.max(1, ...items.map((i) => i.value)));
    const padTop = 6, padBottom = 18, padRight = 24;
    const plotW = width - labelWidth - padRight;
    const n = items.length || 1;
    const rowH = (height - padTop - padBottom) / n;
    const bh = Math.min(barSize, rowH - 6);

    // vertical gridlines + x ticks
    const ticks = 5;
    for (let i = 0; i <= ticks; i++) {
      const val = (max / ticks) * i;
      const x = labelWidth + (plotW / ticks) * i;
      svg.appendChild(svgEl("line", { x1: x, y1: padTop, x2: x, y2: height - padBottom, stroke: GRID, "stroke-dasharray": "3 3" }));
      text(svg, x, height - 5, String(Math.round(val)), { size: tickSize });
    }
    items.forEach((item, i) => {
      const cy = padTop + rowH * i + rowH / 2;
      text(svg, labelWidth - 8, cy + 4, item.label, { size: tickSize, anchor: "end", fill: "var(--slate-700)" });
      const w = Math.max(0, (item.value / max) * plotW);
      const bar = svgEl("path", {
        d: barPath(labelWidth + 1, cy - bh / 2, w, bh, 6, "right"),
        fill: item.fill || EMERALD,
        "fill-opacity": item.fillOpacity ?? 1,
      });
      bindTip(bar, `${item.label} : ${item.value}`);
      svg.appendChild(bar);
    });
  });
}

/* ------------------------------------------------------------------ */
/* Vertical bar chart (score histogram)                                */
/* ------------------------------------------------------------------ */

export function vbarChart(container, { items, tickSize = 10 }) {
  return responsive(container, (svg, width, height) => {
    const max = niceMax(Math.max(1, ...items.map((i) => i.value)));
    const padL = 34, padR = 10, padT = 6, padB = 20;
    const plotW = width - padL - padR;
    const plotH = height - padT - padB;
    const ticks = 5;
    for (let i = 0; i <= ticks; i++) {
      const y = padT + plotH - (plotH / ticks) * i;
      svg.appendChild(svgEl("line", { x1: padL, y1: y, x2: width - padR, y2: y, stroke: GRID, "stroke-dasharray": "3 3" }));
      text(svg, padL - 6, y + 3.5, String(Math.round((max / ticks) * i)), { size: tickSize, anchor: "end" });
    }
    const n = items.length || 1;
    const slot = plotW / n;
    const bw = Math.min(48, slot * 0.62);
    items.forEach((item, i) => {
      const cx = padL + slot * i + slot / 2;
      text(svg, cx, height - 6, item.label, { size: tickSize });
      const h = (item.value / max) * plotH;
      const bar = svgEl("path", {
        d: barPath(cx - bw / 2, padT + plotH - Math.max(h, 0.5), bw, Math.max(h, 0.5), 6, "top"),
        fill: item.fill || EMERALD,
        "fill-opacity": item.fillOpacity ?? 0.85,
      });
      bindTip(bar, `${item.label} : ${item.value}`);
      svg.appendChild(bar);
    });
  });
}

/* ------------------------------------------------------------------ */
/* Radar chart (category averages)                                     */
/* ------------------------------------------------------------------ */

export function radarChart(container, { items, tickSize = 10 }) {
  return responsive(container, (svg, width, height) => {
    const cx = width / 2, cy = height / 2 + 2;
    const outer = Math.min(width, height) / 2 - 26; // room for labels
    const angle = (i) => -Math.PI / 2 + (2 * Math.PI * i) / items.length;
    const point = (i, r) => [cx + Math.cos(angle(i)) * r, cy + Math.sin(angle(i)) * r];

    if (!items.length) return;

    // rings at 25 / 50 / 75 / 100
    for (let ring = 1; ring <= 4; ring++) {
      const r = (outer * ring) / 4;
      const pts = items.map((_, i) => point(i, r).join(",")).join(" ");
      svg.appendChild(svgEl("polygon", { points: pts, fill: "none", stroke: GRID }));
    }
    // spokes + category labels (+ ring values on the first spoke)
    items.forEach((item, i) => {
      const [x, y] = point(i, outer);
      svg.appendChild(svgEl("line", { x1: cx, y1: cy, x2: x, y2: y, stroke: GRID }));
      const [lx, ly] = point(i, outer + 12);
      const anchor = Math.abs(lx - cx) < 4 ? "middle" : lx > cx ? "start" : "end";
      text(svg, lx, ly + 3.5, item.label, { size: tickSize, anchor });
    });
    for (let ring = 1; ring <= 4; ring++) {
      const [x, y] = point(0, (outer * ring) / 4);
      text(svg, x - 3, y - 2, String(25 * ring), { size: 9, anchor: "end" });
    }
    // data polygon
    const pts = items.map((it, i) => point(i, (Math.max(0, Math.min(100, it.value)) / 100) * outer).join(",")).join(" ");
    const poly = svgEl("polygon", {
      points: pts, fill: EMERALD, "fill-opacity": 0.28, stroke: EMERALD, "stroke-width": 2,
    });
    bindTip(poly, items.map((it) => `${it.label} : ${it.value}`).join("   ·   "));
    svg.appendChild(poly);
    items.forEach((it, i) => {
      const [x, y] = point(i, (Math.max(0, Math.min(100, it.value)) / 100) * outer);
      svg.appendChild(svgEl("circle", { cx: x, cy: y, r: 2.4, fill: EMERALD }));
    });
  });
}

/* ------------------------------------------------------------------ */
/* Overview helpers matching the old Recharts configs                  */
/* ------------------------------------------------------------------ */

export const KIND_COLORS = {
  unreadable_document: ROSE,
  must_have_missing: AMBER,
  shortlist_band: AMBER,
  tie_unresolved: AMBER,
  rank_conflict: AMBER,
  score_advisory: TEAL,
  noul_kernel_advisory: TEAL,
  low_confidence_extraction: TEAL,
};

export function chartCard({ title, desc, icon: iconName, short = false, make }) {
  const box = el("div", { class: `chart-box ${short ? "short" : ""}` });
  make(box);
  return el("div", { class: "card" },
    el("div", { class: "card-head tight" },
      el("h3", { class: "card-title sm" }, icon(iconName, 16), title),
      desc ? el("p", { class: "card-desc" }, desc) : null,
    ),
    el("div", { class: "card-body tight" }, box),
  );
}

// el() is shared with ui.js (charts.js already imports icon from there, so
// there is no import cycle); the local copy had drifted out of sync.
