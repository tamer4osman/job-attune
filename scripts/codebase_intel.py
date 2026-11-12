#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Codebase-intelligence gates for the Python and C sides of the repo.

`fallow` (wired separately in .github/workflows/codebase-intel.yml) covers the
JavaScript side. This script is the Python and C counterpart: it runs the
per-language equivalents of fallow's analyses and fails (exit 1) on any
regression, so CI can use it as a gate.

Hard gates (any finding fails, no baseline):
  python   ruff        curated hygiene rules (ruff.toml): unused imports and
                       variables, undefined names, unused `# noqa` directives,
                       import order                      == fallow dead-code
  python   vulture     dead code at >=60% confidence, whitelist for framework
                       hooks (.codebase-intel/vulture-whitelist.py)
  python   pylint      duplicate-code across modules at >=10 similar lines
                                                       == fallow dupes
  python   pip-audit   known CVEs in requirements.txt   == fallow audit
  c        cppcheck    error/warning/performance/portability findings
                       (.codebase-intel/cppcheck-suppressions.txt documents
                       the two accepted exceptions)
  c        flawfinder  any risk-level-5 hit

Ratchet gates (fail only on growth against .codebase-intel/ratchet-baselines.json,
mirroring `fallow health --baseline`): complexity bands from lizard, cppcheck
style count, flawfinder level>=4 count, jscpd clone counts for the C kernel.

Usage:
  python scripts/codebase_intel.py python     # Python gates only
  python scripts/codebase_intel.py c          # C gates only
  python scripts/codebase_intel.py python c   # both
  python scripts/codebase_intel.py c --update-baseline   # re-save ratchet file

Environment:
  CODEBASE_INTEL_STRICT=1  a missing tool is an error instead of a skip
                           (CI sets this; locally a missing analyzer is AMBER)
  CPPCHECK=/path/cppcheck  cppcheck binary to use (default: cppcheck on PATH)
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repo root (no absolute paths)
BASELINES = ROOT / ".codebase-intel" / "ratchet-baselines.json"

PY_PATHS = ["server.py", "attune-engine", "bench", "scripts"]
C_DIRS = [
    "vendor/omnidecide-c/odk-core",
    "vendor/omnidecide-c/odk-brain",
    "vendor/omnidecide-c/odk-spine",
    "vendor/omnidecide-c/include",
    "vendor/omnidecide-c/tools",
]

TOOL_TIMEOUT = 900  # seconds; cppcheck --check-level=exhaustive takes ~20s

results: list[tuple[str, str, str]] = []  # (grade, name, detail)


def grade(name: str, ok: bool, detail: str, warn_ok: bool = False) -> bool:
    g = "GREEN" if ok else ("AMBER" if warn_ok else "RED")
    results.append((g, name, detail))
    print(f"[{g}] {name}: {detail}")
    return ok or warn_ok


# --------------------------------------------------------------------------- #
# subprocess plumbing
# --------------------------------------------------------------------------- #
def run(cmd: list[str]) -> tuple[int, str, str]:
    """Run a tool from the repo root; returns (rc, stdout, stderr)."""
    try:
        p = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUT,
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"tool not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {TOOL_TIMEOUT}s: {' '.join(cmd[:3])}"


def tool_gate(name: str, cmd: list[str], fail_rcs: tuple[int, ...] = (1,)) -> bool:
    """Hard gate: the tool itself decides via its exit code."""
    strict = os.environ.get("CODEBASE_INTEL_STRICT") == "1"
    rc, out, err = run(cmd)
    if rc == 127:
        return grade(name, False, f"analyzer not installed ({cmd[0]})", warn_ok=not strict)
    if rc == 0:
        return grade(name, True, "clean")
    if rc in fail_rcs:
        return grade(name, False, first_lines(out or err, 8))
    return grade(name, False, f"exit {rc}: {first_lines(out or err, 4)}")


def first_lines(text: str, n: int) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()][:n]
    return " | ".join(lines) or "(no output)"


# --------------------------------------------------------------------------- #
# ratchet: fail on growth, require a re-save after improvement
# --------------------------------------------------------------------------- #
def load_baselines() -> dict:
    if BASELINES.exists():
        try:
            data = json.loads(BASELINES.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError as exc:
            sys.exit(f"codebase_intel: {BASELINES} is not valid JSON ({exc}); "
                     f"re-save it with --update-baseline")
    return {}


def ratchet(lang: str, current: dict[str, object]) -> bool:
    """Compare current metrics with the committed baseline; RED on growth.

    An improvement is GREEN locally but RED under CODEBASE_INTEL_STRICT=1 with
    a 're-save the baseline' hint - the same shrink-only contract as fallow's
    --fail-on-stale-baseline, so an accepted improvement is always locked in.
    """
    strict = os.environ.get("CODEBASE_INTEL_STRICT") == "1"
    base = load_baselines().get(lang, {})
    ok = True
    for key in sorted(current):
        val, old = current[key], base.get(key)
        label = f"ratchet {lang}.{key}"
        if old is None:
            ok &= grade(label, False, "no baseline entry (run --update-baseline)")
        elif val == old:
            ok &= grade(label, True, f"{val} == baseline")
        elif isinstance(val, int) and val > old:
            ok &= grade(label, False, f"grew {old} -> {val}")
        elif isinstance(val, float) and val > old + 1e-9:
            ok &= grade(label, False, f"grew {old} -> {val}")
        elif strict:
            ok &= grade(
                label, False, f"improved {old} -> {val}: re-run with --update-baseline and commit"
            )
        else:
            ok &= grade(label, True, f"improved {old} -> {val} (re-save the baseline)")
    return ok


# --------------------------------------------------------------------------- #
# metric collectors
# --------------------------------------------------------------------------- #
def lizard_bands(paths: list[str], language: str, thresholds: list[int]) -> dict[str, int]:
    """CCN bands via lizard's CSV output (column 1 is CCN)."""
    rc, out, _ = run(["lizard", "-l", language, "--csv"] + paths)
    if rc != 0:
        return {}
    ccns = [int(row[1]) for row in csv.reader(io.StringIO(out)) if len(row) > 9]
    bands: dict[str, int] = {"max_ccn": max(ccns) if ccns else 0}
    for t in thresholds:
        bands[f"ccn_ge_{t}"] = sum(1 for c in ccns if c >= t)
    return bands


def cppcheck_metrics() -> tuple[dict[str, int], list[str], str]:
    """One exhaustive run; returns (style metrics, hard findings, error)."""
    binary = os.environ.get("CPPCHECK", "cppcheck")
    cmd = [
        binary,
        "--enable=warning,style,performance,portability",
        "--std=c11",
        "--check-level=exhaustive",
        "--suppress=missingIncludeSystem",
        "--suppressions-list=.codebase-intel/cppcheck-suppressions.txt",
        *C_DIRS,
    ]
    rc, _, err = run(cmd)
    if rc == 127:
        return {}, [], f"cppcheck not available ({binary}); set CPPCHECK=... or install it"
    if rc != 0:
        return {}, [], f"cppcheck exited {rc}: {first_lines(err, 3)}"
    hard_pat = re.compile(r":\d+:\d+: (error|warning|performance|portability): ")
    hard = [ln for ln in err.splitlines() if hard_pat.search(ln)]
    style = sum(1 for ln in err.splitlines() if re.search(r":\d+:\d+: style: ", ln))
    return {"cppcheck_style": style}, hard, ""


def flawfinder_metrics() -> tuple[dict[str, int], list[str], str]:
    """Returns (level>=4 metrics, level>=5 hits, error)."""
    rc, out, _ = run(["flawfinder", "--minlevel=4", *C_DIRS])
    if rc == 127:
        return {}, [], "flawfinder not installed"
    if rc != 0:
        return {}, [], f"flawfinder exited {rc}"
    hit = re.compile(r"^\S+:\d+:\s+\[(\d+)\]")
    levels = [int(m.group(1)) for ln in out.splitlines() if (m := hit.match(ln))]
    ge4 = sum(1 for lvl in levels if lvl >= 4)
    ge5 = [ln for ln in out.splitlines() if (m := hit.match(ln)) and int(m.group(1)) >= 5]
    return {"flawfinder_ge_4": ge4}, ge5, ""


def jscpd_metrics() -> tuple[dict[str, object], str]:
    """Clone counts for the C kernel via jscpd (npx, token-based)."""
    rc, out, err = run(
        ["npx", "--yes", "jscpd@5.4.2", "--min-tokens", "110",
         "--silent", "--reporters", "consoleFull", *C_DIRS]
    )
    if rc == 127:
        return {}, "npx/node not available"
    m = re.search(r"Found (\d+) exact clones with (\d+)\(([\d.]+)%\) duplicated lines", out)
    if not m:
        return {}, f"jscpd summary not parseable (exit {rc}): {first_lines(out or err, 2)}"
    return {
        "jscpd_clones": int(m.group(1)),
        "jscpd_dup_lines": int(m.group(2)),
        "jscpd_dup_percent": float(m.group(3)),
    }, ""


# --------------------------------------------------------------------------- #
# language gates
# --------------------------------------------------------------------------- #
def gate_python(update: bool) -> bool:
    print("\n=== Python codebase intelligence =========================")
    ok = True

    ok &= tool_gate("ruff (hygiene)", ["ruff", "check", "."], fail_rcs=(1, 2))

    ok &= tool_gate(
        "vulture (dead code)",
        ["vulture", *PY_PATHS, ".codebase-intel/vulture-whitelist.py",
         "--min-confidence", "60"],
    )

    ok &= tool_gate(
        "pylint duplicate-code",
        ["pylint", "--disable=all", "--enable=duplicate-code", "--ignore-imports=y",
         "--min-similarity-lines=10", *PY_PATHS],
        fail_rcs=tuple(range(1, 32)),
    )

    # pip-audit: rc 1 = vulnerabilities, rc >= 2 = tool/transport trouble.
    rc, out, err = run(["pip-audit", "-r", "requirements.txt"])
    if rc == 127:
        ok &= grade("pip-audit (dependencies)", False, "pip-audit not installed",
                    warn_ok=os.environ.get("CODEBASE_INTEL_STRICT") != "1")
    elif rc == 0:
        ok &= grade("pip-audit (dependencies)", True, "no known vulnerabilities")
    elif rc == 1:
        ok &= grade("pip-audit (dependencies)", False, first_lines(out or err, 6))
    else:
        ok &= grade("pip-audit (dependencies)", False,
                    f"transport error (exit {rc}) - is the network up?",
                    warn_ok=os.environ.get("CODEBASE_INTEL_STRICT") != "1")

    bands = lizard_bands(PY_PATHS, "python", [11, 21, 31, 41])
    if bands:
        if update:
            save_baseline_section("python", bands)
        else:
            ok &= ratchet("python", bands)
    else:
        ok &= grade("lizard (complexity)", False, "lizard not installed or failed",
                    warn_ok=os.environ.get("CODEBASE_INTEL_STRICT") != "1")
    return ok


def gate_c(update: bool) -> bool:
    print("\n=== C kernel codebase intelligence ========================")
    ok = True
    strict = os.environ.get("CODEBASE_INTEL_STRICT") == "1"

    style, hard, err = cppcheck_metrics()
    if err:
        ok &= grade("cppcheck (static analysis)", False, err, warn_ok=not strict)
    else:
        if hard:
            ok &= grade("cppcheck (static analysis)", False, first_lines("\n".join(hard), 8))
        else:
            ok &= grade("cppcheck (static analysis)", True,
                        "no warning/performance/portability findings")
        if update:
            save_baseline_section("c", style)
        else:
            ok &= ratchet("c", style)

    ff, ge5, err = flawfinder_metrics()
    if err:
        ok &= grade("flawfinder (security, level 5)", False, err, warn_ok=not strict)
        ok &= grade("ratchet c.flawfinder_ge_4", False, err, warn_ok=not strict)
    else:
        ok &= grade("flawfinder (security, level 5)", not ge5,
                    first_lines("\n".join(ge5), 4) if ge5 else "no level-5 findings")
        if update:
            save_baseline_section("c", ff)
        else:
            ok &= ratchet("c", ff)

    bands = lizard_bands(C_DIRS, "c", [26, 51])
    if not bands:
        ok &= grade("lizard (complexity, C)", False, "lizard not installed or failed",
                    warn_ok=not strict)
    elif update:
        save_baseline_section("c", bands)
    else:
        ok &= ratchet("c", bands)

    jp, err = jscpd_metrics()
    if err:
        ok &= grade("jscpd (duplication)", False, err, warn_ok=not strict)
    elif update:
        save_baseline_section("c", jp)
    else:
        ok &= ratchet("c", jp)
    return ok


def save_baseline_section(lang: str, section: dict) -> None:
    data = load_baselines()
    merged = dict(data.get(lang, {}))
    merged.update(section)
    data[lang] = merged
    BASELINES.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[SAVE] baseline {lang}: {json.dumps(section, sort_keys=True)}")


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("langs", nargs="+", choices=["python", "c"], help="language gates to run")
    ap.add_argument("--update-baseline", action="store_true",
                    help="re-save the ratchet baseline from the current tree")
    args = ap.parse_args()

    ok = True
    for lang in args.langs:
        ok &= gate_python(args.update_baseline) if lang == "python" else gate_c(args.update_baseline)

    reds = [r for r in results if r[0] == "RED"]
    ambers = [r for r in results if r[0] == "AMBER"]
    print(f"\n{len(results)} checks: {len(results) - len(reds) - len(ambers)} green, "
          f"{len(ambers)} amber, {len(reds)} red")
    if args.update_baseline:
        print(f"baseline re-saved to {BASELINES.relative_to(ROOT)} - commit it with your change")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
