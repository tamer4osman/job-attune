#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""E2E check of the Job Attune vanilla UI with Playwright + Chromium.

Drives the full wizard against the local Python server:
  1. load / and render step 1
  2. scan the sample folder, continue
  3. load the example template, start the run
  4. wait for the run monitor to finish
  5. verify all six result tabs render, open the candidate dialog,
     record a review decision, generate + download PDF exports
Screenshots land in /tmp/render/ for the visual QA pass.
"""

import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:3000"
SHOTS = pathlib.Path("/tmp/render")
SHOTS.mkdir(parents=True, exist_ok=True)

failures = []


def check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}{(' - ' + extra) if extra and not cond else ''}")
    if not cond:
        failures.append(name)


def shot(page, name):
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("console", lambda m: errors.append(f"console.error: {m.text}") if m.type == "error" else None)

    # ---- step 1: load + scan -----------------------------------------
    page.goto(BASE + "/", wait_until="load")
    page.wait_for_timeout(400)
    check("page title", page.title() == "Job Attune - Hire for aptitude", page.title())
    check("stepper renders 4 steps", page.locator(".step").count() == 4)
    # note: card titles render in CSS uppercase (Agenflow style) - compare
    # case-insensitively so the assertion tracks content, not presentation
    check("folder card renders", page.locator(".card-title").first.inner_text().lower().startswith("select the applicant"))

    page.fill("#folder", "attune-sample-data/candidates")
    page.click("text=Scan folder")
    page.wait_for_selector("text=Validation preview", timeout=15000)
    page.wait_for_timeout(300)
    n_cands = page.locator(".candidate-tile").count()
    check("scan found 6 candidates", n_cands == 6, str(n_cands))
    shot(page, "01-step1-scan")

    page.click("text=Continue to job profile")
    page.wait_for_selector("text=Company & job profile", timeout=5000)

    # ---- step 2: load example template + start run --------------------
    page.click("text=Load example")
    page.wait_for_timeout(600)
    job_title = page.input_value("#jtitle")
    check("example profile loaded", job_title == "Senior Data Engineer", job_title)
    n_skill_rows = page.locator(".skill-row").count()
    check("technical skills expanded with rows", n_skill_rows >= 6, str(n_skill_rows))
    shot(page, "02-step2-profile")

    page.click("text=Start screening run")
    page.wait_for_selector("text=Screening run", timeout=10000)
    check("run monitor visible", page.locator(".card-title").first.inner_text().lower().startswith("screening run"))

    # ---- step 3: wait for completion ----------------------------------
    deadline = time.time() + 180
    done = False
    while time.time() < deadline:
        if page.locator("text=View results").count() > 0:
            done = True
            break
        if page.locator("text=Screening run failed").count() > 0:
            break
        page.wait_for_timeout(500)
    check("run finished", done)
    shot(page, "03-step3-monitor")

    page.click("text=View results")
    page.wait_for_selector(".stat-grid", timeout=20000)
    page.wait_for_timeout(500)
    stats = page.locator(".stat-value").all_inner_texts()
    check("stat cards show 6 candidates", stats and stats[0] == "6", str(stats))
    check("charts render (svg present)", page.locator(".chart-box svg").count() >= 3,
          str(page.locator(".chart-box svg").count()))
    shot(page, "04-step4-overview")

    # ---- tabs ----------------------------------------------------------
    page.click("button[role='tab'] >> text=Position report")
    page.wait_for_selector("text=Position verdict", timeout=5000)
    check("verdict banner", page.locator("text=Strong front-runner").count() > 0)
    check("coverage matrix rows", page.locator("table.matrix tbody tr").count() >= 10)
    shot(page, "05-position-report")

    page.click("button[role='tab'] >> text=Ranking")
    page.wait_for_selector(".rank-row", timeout=5000)
    n_rank = page.locator(".rank-row").count()
    check("ranking shows 6 rows", n_rank == 6, str(n_rank))
    shot(page, "06-ranking")

    # candidate detail dialog
    page.locator(".rank-row").first.click()
    page.wait_for_selector(".dialog", timeout=5000)
    check("dialog shows candidate", page.locator(".dialog-title").inner_text().lower().startswith("#1"))
    check("requirement evidence cards", page.locator(".req-card").count() >= 10)
    shot(page, "07-candidate-detail")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    page.click("button[role='tab'] >> text=Candidates")
    page.wait_for_selector(".cand-card", timeout=5000)
    check("candidate cards grid", page.locator(".cand-card").count() == 6)

    # ---- review + audit tabs -------------------------------------------
    page.click("button[role='tab'] >> text=Review")
    page.wait_for_selector("text=Review queue", timeout=5000)
    n_review = page.locator(".review-item").count()
    check("review queue items", n_review > 0, str(n_review))
    shot(page, "08-review")

    page.fill("#governance-reviewer", "Playwright QA")
    page.locator(".review-item").first.locator("text=Acknowledge").click()
    page.wait_for_selector("text=Recorded: acknowledged", timeout=10000)
    check("review decision recorded", True)

    page.click("button[role='tab'] >> text=Audit & export")
    page.wait_for_selector("text=Human decision log", timeout=5000)
    check("decision log entry", page.locator(".decision-row").count() >= 1)
    check("replay PASS badge", page.locator("text=replay PASS").count() == 1)

    # generate + download PDFs
    with page.expect_download() as dl_info:
        page.click("text=Generate PDF reports")
        try:
            page.wait_for_selector("text=PDF reports generated", timeout=60000)
        except Exception:
            pass
        page.wait_for_selector(".download-row a", timeout=30000)
        page.locator(".download-row a").first.click()
    size = pathlib.Path(dl_info.value.path()).stat().st_size
    check("batch PDF downloaded", size > 10000, f"{size} bytes")
    shot(page, "09-audit-export")

    # ---- new run resets the wizard --------------------------------------
    page.click("#new-run-btn")
    page.wait_for_selector("text=Select the applicant main folder", timeout=5000)
    check("reset returns to step 1", True)

    js_errors = [e for e in errors if "favicon" not in e]
    check("no JS errors during the whole flow", len(js_errors) == 0, "; ".join(js_errors[:5]))

    browser.close()

print()
if failures:
    print(f"RESULT: {len(failures)} failure(s): {failures}")
    sys.exit(1)
print("RESULT: all checks passed")
