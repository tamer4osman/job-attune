#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Agenflow-style redesign checks: fonts, palette, layout integrity.

Run against a live server (any port): verifies the new skin actually
applied - self-hosted fonts loaded, orange/cream/ink palette active,
pill buttons, no horizontal overflow anywhere - while the DOM contract
the JS relies on stays intact.
"""

import sys

from playwright.sync_api import sync_playwright

PORT = sys.argv[1] if len(sys.argv) > 1 else "3000"
BASE = f"http://127.0.0.1:{PORT}"

failures = []


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok or not detail else f"  <- {detail}"))
    if not ok:
        failures.append(name)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(600)

    # ---- fonts actually loaded (self-hosted, no CDN) -------------------
    loaded = page.evaluate("""async () => {
      await document.fonts.ready;
      return {
        display: document.fonts.check('16px Boldonse'),
        body: document.fonts.check('16px "DM Sans"'),
        // every Playfair usage in the design is italic (labels/tagline)
        label: document.fonts.check('italic 16px "Playfair Display"'),
        count: document.fonts.size,
      };
    }""")
    check("Boldonse (display) loaded", loaded["display"])
    check("DM Sans (body) loaded", loaded["body"])
    check("Playfair Display (label) loaded", loaded["label"])

    # no external font/network requests: everything self-hosted
    hosts = page.evaluate(
        "() => performance.getEntriesByType('resource').map(r => new URL(r.name).host)"
        ".filter(h => h !== location.host)")
    check("zero external asset hosts (fully offline)", hosts == [], str(hosts[:4]))

    # ---- palette applied ------------------------------------------------
    style = page.evaluate("""() => {
      const gs = (sel, prop) => {
        const el = document.querySelector(sel);
        return el ? getComputedStyle(el)[prop] : null;
      };
      return {
        bodyBg: gs('body', 'backgroundColor'),
        headerBg: gs('.site-header', 'backgroundColor'),
        headerBorder: gs('.site-header', 'borderBottomColor'),
        titleFont: gs('.header-title', 'fontFamily'),
        subtitleFont: gs('.header-subtitle', 'fontFamily'),
        badgeLocalBg: gs('.badge-local', 'backgroundColor'),
        badgeLocalTransform: gs('.badge-local', 'transform'),
        stepCurrentBg: gs('.step[data-state="current"]', 'backgroundColor'),
        cardRadius: gs('.card', 'borderRadius'),
        scanBtnRadius: gs('.btn-primary', 'borderRadius'),
        scanBtnBg: gs('.btn-primary', 'backgroundColor'),
        scanBtnText: gs('.btn-primary', 'textTransform'),
        footerBg: gs('.site-footer', 'backgroundColor'),
        inputRadius: gs('#folder', 'borderRadius'),
      };
    }""")
    check("body background is cream #fefae7",
          style["bodyBg"] == "rgb(254, 250, 231)", str(style["bodyBg"]))
    check("header is white with ink border",
          style["headerBg"] == "rgb(255, 255, 255)" and style["headerBorder"] == "rgb(59, 0, 27)",
          f"{style['headerBg']} / {style['headerBorder']}")
    check("header title uses Boldonse", "Boldonse" in style["titleFont"], str(style["titleFont"]))
    check("subtitle uses Playfair Display italic",
          "Playfair" in style["subtitleFont"], str(style["subtitleFont"]))
    check("local badge is the orange sticker (rotated)",
          style["badgeLocalBg"] == "rgb(242, 108, 23)" and style["badgeLocalTransform"] != "none",
          f"{style['badgeLocalBg']} / {style['badgeLocalTransform']}")
    check("current step is orange", style["stepCurrentBg"] == "rgb(242, 108, 23)",
          str(style["stepCurrentBg"]))
    check("cards use 18px radius", style["cardRadius"] == "18px", str(style["cardRadius"]))
    check("primary button is a pill", style["scanBtnRadius"] == "999px", str(style["scanBtnRadius"]))
    check("primary button is orange", style["scanBtnBg"] == "rgb(242, 108, 23)",
          str(style["scanBtnBg"]))
    check("primary button text is uppercase", style["scanBtnText"] == "uppercase")
    check("footer is forest green #09352d",
          style["footerBg"] == "rgb(9, 53, 45)", str(style["footerBg"]))
    check("inputs are pills", style["inputRadius"] == "999px", str(style["inputRadius"]))

    # ---- layout integrity ------------------------------------------------
    overflow = page.evaluate("""() => {
      const bad = [];
      if (document.documentElement.scrollWidth > window.innerWidth + 1)
        bad.push('document');
      for (const el of document.querySelectorAll('.card-title, .header-title, .btn, .badge')) {
        if (el.scrollWidth > el.clientWidth + 2)
          bad.push(el.className.split(' ')[0] + ':' + el.textContent.trim().slice(0, 24));
      }
      return bad;
    }""")
    check("no horizontal overflow / clipped labels", overflow == [], str(overflow[:5]))

    # ---- run the wizard and re-check in the results view -----------------
    page.fill("#folder", "attune-sample-data/candidates")
    page.click("text=Scan folder")
    page.wait_for_selector("text=Validation preview", timeout=15000)
    page.click("text=Continue to job profile")
    page.wait_for_selector("text=Company & job profile", timeout=5000)
    page.click("text=Load example")
    page.wait_for_timeout(500)
    page.click("text=Start screening run")
    page.wait_for_selector("text=View results", timeout=120000)
    page.click("text=View results")
    page.wait_for_selector(".stat-grid", timeout=20000)
    page.wait_for_timeout(600)

    stat_font = page.evaluate(
        "() => getComputedStyle(document.querySelector('.stat-value')).fontFamily")
    check("stat values use Boldonse", "Boldonse" in stat_font, str(stat_font))
    tab_active = page.evaluate(
        "() => getComputedStyle(document.querySelector(\".tab[aria-selected='true']\")).backgroundColor")
    check("active tab is ink pill", tab_active == "rgb(59, 0, 27)", str(tab_active))
    svg_fills = page.evaluate(
        "() => [...document.querySelectorAll('.chart-box svg *')].map(e => e.getAttribute('fill'))"
        ".filter(f => f && f.startsWith('#'))")
    has_orange = any(f.lower() == "#f26c17" for f in svg_fills)
    check("charts render in the new orange palette", has_orange, str(svg_fills[:6]))

    # dialog skin
    page.click("button[role='tab'] >> text=Ranking")
    page.wait_for_selector(".rank-row", timeout=5000)
    page.locator(".rank-row").first.click()
    page.wait_for_selector(".dialog", timeout=5000)
    dlg_radius = page.evaluate(
        "() => getComputedStyle(document.querySelector('.dialog')).borderRadius")
    check("dialog uses 18px radius", dlg_radius == "18px", str(dlg_radius))
    page.keyboard.press("Escape")

    check("zero JS errors during the styled flow", errors == [], "; ".join(errors[:3]))
    browser.close()

print()
if failures:
    print(f"DESIGN RESULT: {len(failures)} failure(s): {failures}")
    sys.exit(1)
print("DESIGN RESULT: all style checks passed")
