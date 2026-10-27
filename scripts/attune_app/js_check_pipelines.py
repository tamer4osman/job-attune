#!/usr/bin/env python3
"""Job Attune JS/TS check pipelines, powered by Fallow (https://fallow.tools/docs/).

Adds JavaScript/TypeScript check pipelines to the existing Python tooling of the
Job Attune project. Each pipeline wraps one Fallow CLI analysis, parses its JSON
envelope, buckets findings by ownership zone, and grades the result
red / amber / green with file:line evidence.

Pipelines
---------
  dead-code   unused files, exports, dependencies          (fallow dead-code)
  circular    circular dependencies                        (fallow dead-code --circular-deps)
  unresolved  unresolved imports                           (fallow dead-code --unresolved-imports)
  dupes       copy-paste duplication                       (fallow dupes)
  health      complexity hotspots, maintainability         (fallow health)
  styling     CSS / Tailwind styling drift                 (fallow health --css)
  flags       feature-flag inventory (informational)       (fallow flags)

Grading policy (red / amber / green)
------------------------------------
  RED    must fix before release:
           - any unresolved import
           - any circular dependency
           - duplication rate above the configured threshold (default 10 %)
           - >= 25 dead-code findings inside app-owned files
           - an egregious complexity outlier in app-owned files
             (cyclomatic >= 40 or cognitive >= 40)
  AMBER  should review:
           - scaffold/vendor-zone findings (unused shadcn ui files, hooks, ...)
           - unused or misplaced dependencies
           - unused exports / types in app-owned files
           - complexity findings over threshold in app-owned files. Coverage-aware:
             this repo has no test harness, so fallow estimates CRAP from the
             static graph and every untested function trends 'critical'; the gate
             therefore keeps these as a refactor backlog instead of failing the run
  GREEN  category clean, or informational-only result.

Zones
-----
  app       src/app/**, src/components/attune/**, src/lib/attune*.ts
  scaffold  src/components/ui/**, src/hooks/**, src/lib/{utils,db}.ts (shadcn kit)
  infra     next.config.ts, postcss.config.mjs, eslint.config.mjs, tsconfig*.json,
            prisma/**, db/**, package.json dependency findings
  outside   everything else (should stay empty once ignorePatterns are set)

Usage
-----
  python3 scripts/attune_app/js_check_pipelines.py [options]

Options
-------
  --root PATH        project root (default: auto-detect two dirs up from this file)
  --config PATH      fallow config (default: fallow.attune.json next to this file)
  --pipelines NAMES  comma-separated subset to run (default: all)
  --output-dir PATH  where raw JSON envelopes are stored (default: <root>/scripts/attune_app/checks_out)
  --report PATH      markdown report path (default: <root>/download/attune-js-checks-report.md)
  --json-only        skip the markdown report, print the machine summary
  --fail-fast        stop after the first red pipeline

Exit codes: 0 = green/amber only, 1 = at least one red, 2 = tool/runtime failure.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

FALLOW_MIN_VERSION = "3.0.0"

GRADE_ORDER = {"green": 0, "amber": 1, "red": 2}

APP_ZONE = ("src/app/**", "src/components/attune/**", "src/lib/attune*.ts")
SCAFFOLD_ZONE = ("src/components/ui/**", "src/hooks/**", "src/lib/utils.ts", "src/lib/db.ts")
INFRA_ZONE = ("next.config.ts", "postcss.config.mjs", "eslint.config.mjs", "tsconfig*.json",
              "prisma/**", "db/**")

DUPLICATION_THRESHOLD_DEFAULT = 10.0  # percent, mirrors fallow.attune.json
CRITICAL_COMPLEXITY_SEVERITY = "critical"


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class Evidence:
    """One file:line-anchored finding, ready for the report tables."""
    zone: str
    path: str
    where: str
    kind: str
    detail: str
    severity: str  # error | warn | info | critical | high | moderate ...
    metrics: dict = field(default_factory=dict)


@dataclass
class PipelineResult:
    name: str
    title: str
    grade: str = "green"          # green | amber | red
    headline: str = ""
    command: str = ""
    duration_s: float = 0.0
    ok: bool = True               # fallow itself ran without crashing
    raw_summary: dict = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    error: str = ""

    def escalate(self, candidate: str) -> None:
        if GRADE_ORDER.get(candidate, 0) > GRADE_ORDER.get(self.grade, 0):
            self.grade = candidate


@dataclass
class CheckReport:
    root: str
    fallow_version: str
    config_path: str
    started_at: str
    results: list[PipelineResult] = field(default_factory=list)

    @property
    def overall(self) -> str:
        if not self.results:
            return "green"
        worst = max(GRADE_ORDER.get(r.grade, 0) for r in self.results)
        return {0: "green", 1: "amber", 2: "red"}[worst]

    def by_grade(self, grade: str) -> list[PipelineResult]:
        return [r for r in self.results if r.grade == grade]


# --------------------------------------------------------------------------
# Zone classification
# --------------------------------------------------------------------------

def classify_zone(rel_path: str) -> str:
    rel = rel_path.replace(os.sep, "/")
    for pattern in APP_ZONE:
        if fnmatch.fnmatch(rel, pattern):
            return "app"
    for pattern in SCAFFOLD_ZONE:
        if fnmatch.fnmatch(rel, pattern):
            return "scaffold"
    for pattern in INFRA_ZONE:
        if fnmatch.fnmatch(rel, pattern):
            return "infra"
    if rel == "package.json":
        return "infra"
    if rel.startswith("src/"):
        return "scaffold"
    return "outside"


# --------------------------------------------------------------------------
# Fallow invocation helpers
# --------------------------------------------------------------------------

def run_fallow(root: Path, config: Path, args: list[str], timeout: int = 240) -> dict:
    """Run one fallow command with JSON output and return the parsed envelope."""
    cmd = ["fallow", "-c", str(config), *args, "-f", "json", "-q"]
    proc = subprocess.run(
        cmd, cwd=str(root), capture_output=True, text=True, timeout=timeout, check=False,
    )
    if proc.returncode not in (0, 1):
        # fallow uses exit 1 for "findings exist" only with --fail-on-issues; other
        # non-zero codes are real failures.
        raise RuntimeError(
            f"fallow exited {proc.returncode}: {proc.stderr.strip()[:400] or proc.stdout.strip()[:400]}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"fallow returned invalid JSON ({exc}): {proc.stdout[:200]}") from exc


def get_fallow_version() -> str:
    proc = subprocess.run(["fallow", "--version"], capture_output=True, text=True, check=False)
    raw = (proc.stdout or proc.stderr).strip().splitlines()[0] if (proc.stdout or proc.stderr) else "unknown"
    return raw.removeprefix("fallow ").strip() or raw


def severity_rank(value: str) -> int:
    order = {"info": 0, "moderate": 1, "warn": 1, "high": 2, "error": 2, "critical": 3}
    return order.get(str(value).lower(), 1)


# --------------------------------------------------------------------------
# Evidence builders per pipeline
# --------------------------------------------------------------------------

def ev_from_dead_code(env: dict) -> tuple[list[Evidence], dict]:
    evidence: list[Evidence] = []
    sections = [
        ("unused_files", "unused file", "path"),
        ("unused_exports", "unused export", "path"),
        ("unused_types", "unused type", "path"),
        ("unused_dependencies", "unused dependency", "package.json"),
        ("unused_dev_dependencies", "unused dev dependency", "package.json"),
        ("test_only_dependencies", "test-only dependency", "package.json"),
        ("type_only_dependencies", "type-only dependency", "package.json"),
        ("unlisted_dependencies", "unlisted dependency", "path"),
        ("duplicate_exports", "duplicate export", "path"),
    ]
    counts = {}
    for key, label, _path_key in sections:
        items = env.get(key) or []
        counts[key] = len(items)
        for item in items:
            path = item.get("path", "?")
            where = f"line {item.get('line', '?')}" if item.get("line") else "-"
            if key in ("unused_exports", "unused_types"):
                detail = f"export '{item.get('export_name', '?')}' is not used anywhere"
            elif key == "unused_files":
                detail = "file is unreachable from any entry point"
            else:
                detail = f"package '{item.get('package_name', '?')}' ({item.get('location', 'dependencies')})"
            zone = classify_zone(path)
            if key in ("unused_dependencies", "unused_dev_dependencies", "test_only_dependencies",
                       "type_only_dependencies", "unlisted_dependencies"):
                grade_hint = "amber"
            elif key == "unused_exports" and zone == "app":
                grade_hint = "amber"
            else:
                grade_hint = "amber" if zone in ("app", "infra") else "scaffold-info"
            severity = "info" if grade_hint == "scaffold-info" else "warn"
            evidence.append(Evidence(
                zone=zone, path=path, where=where, kind=label, detail=detail, severity=severity,
            ))
    return evidence, counts


def ev_from_cycles(env: dict) -> tuple[list[Evidence], dict]:
    cycles = env.get("circular_dependencies") or []
    evidence = []
    for cyc in cycles:
        path = cyc.get("path") or (cyc.get("cycle") or ["?"])[0]
        chain = " -> ".join(cyc.get("cycle", [path]))
        evidence.append(Evidence(
            zone=classify_zone(path), path=path, where="-",
            kind="circular dependency", detail=chain, severity="error",
        ))
    return evidence, {"circular_dependencies": len(cycles)}


def ev_from_unresolved(env: dict) -> tuple[list[Evidence], dict]:
    items = env.get("unresolved_imports") or []
    evidence = []
    for item in items:
        path = item.get("path", "?")
        spec = item.get("specifier") or item.get("import") or "?"
        evidence.append(Evidence(
            zone=classify_zone(path), path=path,
            where=f"line {item.get('line', '?')}",
            kind="unresolved import", detail=f"'{spec}' cannot be resolved", severity="error",
        ))
    return evidence, {"unresolved_imports": len(items)}


def ev_from_dupes(env: dict, threshold: float) -> tuple[list[Evidence], dict]:
    groups = env.get("clone_groups") or []
    stats = env.get("stats") or {}
    rate = float(stats.get("duplication_percentage",
                           stats.get("duplication_rate_percent", 0.0)) or 0.0)
    evidence = []
    for group in groups:
        instances = group.get("instances") or []
        if not instances:
            continue
        first = instances[0]
        zone = classify_zone(first.get("file", ""))
        zones = sorted({classify_zone(i.get("file", "")) for i in instances})
        lines = sum(max(0, int(i.get("end_line", 0)) - int(i.get("start_line", 0)) + 1)
                    for i in instances)
        evidence.append(Evidence(
            zone=zones[0] if len(zones) == 1 else "/".join(zones),
            path=" + ".join(dict.fromkeys(i.get("file", "?") for i in instances)),
            where=", ".join(f"L{i.get('start_line', '?')}-{i.get('end_line', '?')}" for i in instances),
            kind="clone group",
            detail=f"{len(instances)} occurrences, ~{lines} duplicated lines, "
                   f"{group.get('token_count', '?')} tokens",
            severity="error" if (rate >= threshold and zone == "app") else "warn",
        ))
    stats_out = {
        "clone_groups": len(groups),
        "clone_families": len(env.get("clone_families") or []),
        "duplicated_lines": stats.get("duplicated_lines"),
        "duplication_rate_percent": rate,
        "threshold_percent": threshold,
    }
    return evidence, stats_out


def ev_from_health(env: dict) -> tuple[list[Evidence], dict]:
    findings = env.get("findings") or []
    evidence = []
    for f in findings:
        path = f.get("path", "?")
        zone = classify_zone(path)
        sev = str(f.get("effective_severity") or f.get("severity") or "warn").lower()
        raw = str(f.get("severity") or "")
        evidence.append(Evidence(
            zone=zone, path=path, where=f"L{f.get('line', '?')} {f.get('name', '')}".strip(),
            kind="complexity",
            detail=f"cyclomatic {f.get('cyclomatic', '?')}, cognitive {f.get('cognitive', '?')}, "
                   f"CRAP {f.get('crap', '?')}, {f.get('line_count', '?')} lines"
                   + (f" (raw severity {raw}, CRAP estimated without tests)" if raw else ""),
            severity=sev,
            metrics={
                "cyclomatic": f.get("cyclomatic"),
                "cognitive": f.get("cognitive"),
                "crap": f.get("crap"),
                "raw_severity": raw,
            },
        ))
    score = (env.get("health_score") or {})
    summary = env.get("summary") or {}
    stats = {
        "health_score": score.get("score"),
        "health_grade": score.get("grade"),
        "average_maintainability": summary.get("average_maintainability"),
        "functions_analyzed": summary.get("functions_analyzed"),
        "functions_above_threshold": summary.get("functions_above_threshold"),
        "penalties": score.get("penalties", {}),
    }
    return evidence, stats


def ev_from_styling(env: dict) -> tuple[list[Evidence], dict]:
    findings = env.get("styling_findings") or []
    evidence = []
    for f in findings:
        path = f.get("path", "?")
        zone = classify_zone(path)
        sev = str(f.get("effective_severity") or "warn").lower()
        detail = f"{f.get('code', 'css-finding')}"
        if f.get("sub_kind"):
            detail += f"/{f['sub_kind']}"
        if f.get("value"):
            detail += f" value '{f['value']}'"
        if f.get("fix_hint"):
            detail += f" - {f['fix_hint']}"
        evidence.append(Evidence(
            zone=zone, path=path, where=f"line {f.get('line', '?')}",
            kind="styling drift", detail=detail, severity=sev,
        ))
    sh = env.get("styling_health") or {}
    ca = env.get("css_analytics") or {}
    stats = {
        "styling_score": sh.get("score"),
        "styling_grade": sh.get("grade"),
        "styling_penalties": sh.get("penalties", {}),
        "styling_findings": len(findings),
        "tailwind_arbitrary_values": len(ca.get("tailwind_arbitrary_values") or []),
    }
    return evidence, stats


def ev_from_flags(env: dict) -> tuple[list[Evidence], dict]:
    flags = (env.get("flags") or env.get("findings") or [])
    evidence = []
    for f in flags:
        path = f.get("path", "?")
        evidence.append(Evidence(
            zone=classify_zone(path), path=path, where=f"line {f.get('line', '?')}",
            kind="feature flag", detail=str(f.get("name") or f.get("flag") or f.get("value", "")),
            severity="info",
        ))
    return evidence, {"flags": len(flags)}


# --------------------------------------------------------------------------
# Pipeline definitions
# --------------------------------------------------------------------------

@dataclass
class Pipeline:
    name: str
    title: str
    args_builder: Callable[[dict], list[str]]
    evidence_builder: Callable[[dict], tuple[list[Evidence], dict]]
    grade_fn: Callable[[PipelineResult, dict], None]


def _grade_dead_code(res: PipelineResult, _env: dict) -> None:
    app_infra = [e for e in res.evidence if e.zone in ("app", "infra")]
    app_dead = [e for e in res.evidence if e.zone == "app"]
    if len(app_dead) >= 25:
        # Roughly a quarter of the app's own surface is dead - needs a dedicated pass.
        res.escalate("red")
    elif app_infra:
        res.escalate("amber")
    if any(e.kind in ("unresolved import", "circular dependency") for e in res.evidence):
        res.escalate("red")
    if not res.evidence:
        res.headline = "no dead code findings"
    else:
        res.headline = f"{len(res.evidence)} findings ({len(app_infra)} in app/infra zones)"


def _grade_simple(res: PipelineResult, env: dict) -> None:
    if res.evidence:
        res.escalate("red")
        res.headline = f"{len(res.evidence)} blocking findings"
    else:
        res.headline = "clean"


def _grade_dupes(res: PipelineResult, env: dict) -> None:
    stats = res.stats
    rate = float(stats.get("duplication_rate_percent") or 0.0)
    threshold = float(stats.get("threshold_percent") or DUPLICATION_THRESHOLD_DEFAULT)
    app_groups = [e for e in res.evidence if "app" in e.zone]
    if rate >= threshold:
        res.escalate("red")
        res.headline = f"duplication rate {rate}% >= threshold {threshold}%"
    elif app_groups:
        res.escalate("amber")
        res.headline = f"rate {rate}% < {threshold}%, but {len(app_groups)} clone group(s) touch app code"
    else:
        res.headline = f"rate {rate}% < threshold {threshold}%, no app-zone clones"


def _grade_health(res: PipelineResult, _env: dict) -> None:
    """Coverage-aware complexity grading.

    This repo ships no test harness, so fallow estimates CRAP from the static graph
    (coverage_model: static_estimated). With zero runtime evidence every non-trivial
    function trends towards raw severity 'critical', which would grade the whole
    untested app red for one shared root cause. The gate therefore:
      - escalates to red only for egregious outliers (cyclomatic >= 40 or
        cognitive >= 40 in app-owned files),
      - keeps the remaining over-threshold functions amber as a refactor backlog,
      - reports raw severity + the estimation caveat in the evidence so the
        backlog can be re-scored once real coverage data exists.
    """
    app_findings = [e for e in res.evidence if e.zone == "app"]
    outliers = [e for e in app_findings
                if (e.metrics.get("cyclomatic") or 0) >= 40
                or (e.metrics.get("cognitive") or 0) >= 40]
    high_app = [e for e in app_findings if severity_rank(e.severity) >= severity_rank("high")]
    if outliers:
        res.escalate("red")
    elif high_app:
        res.escalate("amber")
    score = res.stats.get("health_score")
    grade = res.stats.get("health_grade")
    res.headline = (f"health {score} ({grade}); app-zone complexity findings: "
                    f"{len(outliers)} outliers / {len(high_app)} over-threshold "
                    f"/ {len(app_findings)} total")


def _grade_styling(res: PipelineResult, _env: dict) -> None:
    app_findings = [e for e in res.evidence if e.zone == "app"]
    grade = res.stats.get("styling_grade")
    if app_findings and severity_rank(app_findings[0].severity) >= severity_rank("error"):
        res.escalate("red")
    elif app_findings:
        res.escalate("amber")
    res.headline = (f"styling health {res.stats.get('styling_score')} ({grade}); "
                    f"{len(app_findings)} app-zone finding(s), {len(res.evidence)} total")


def _grade_flags(res: PipelineResult, _env: dict) -> None:
    res.headline = f"{len(res.evidence)} feature flag(s) detected (informational)"


def build_pipelines() -> list[Pipeline]:
    return [
        Pipeline(
            name="dead-code", title="Dead code & dependency hygiene",
            args_builder=lambda _prev: ["dead-code", "--top", "80"],
            evidence_builder=ev_from_dead_code, grade_fn=_grade_dead_code,
        ),
        Pipeline(
            name="circular", title="Circular dependencies",
            args_builder=lambda _prev: ["dead-code", "--circular-deps"],
            evidence_builder=ev_from_cycles, grade_fn=_grade_simple,
        ),
        Pipeline(
            name="unresolved", title="Unresolved imports",
            args_builder=lambda _prev: ["dead-code", "--unresolved-imports"],
            evidence_builder=ev_from_unresolved, grade_fn=_grade_simple,
        ),
        Pipeline(
            name="dupes", title="Code duplication",
            args_builder=lambda _prev: ["dupes", "--top", "30"],
            evidence_builder=lambda env: ev_from_dupes(env, DUPLICATION_THRESHOLD_DEFAULT),
            grade_fn=_grade_dupes,
        ),
        Pipeline(
            name="health", title="Complexity & maintainability",
            args_builder=lambda _prev: ["health", "--top", "60"],
            evidence_builder=ev_from_health, grade_fn=_grade_health,
        ),
        Pipeline(
            name="styling", title="CSS / Tailwind styling drift",
            args_builder=lambda _prev: ["health", "--css", "--top", "80"],
            evidence_builder=ev_from_styling, grade_fn=_grade_styling,
        ),
        Pipeline(
            name="flags", title="Feature flags (informational)",
            args_builder=lambda _prev: ["flags"],
            evidence_builder=ev_from_flags, grade_fn=_grade_flags,
        ),
    ]


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

GRADE_BADGE = {"green": "GREEN", "amber": "AMBER", "red": "RED"}


def run_pipelines(root: Path, config: Path, selected: list[str], output_dir: Path,
                  fail_fast: bool) -> tuple[list[PipelineResult], list[dict], list[dict]]:
    pipelines = build_pipelines()
    results: list[PipelineResult] = []
    raw_envs: list[dict] = []
    timings: list[dict] = []

    output_dir.mkdir(parents=True, exist_ok=True)
    version = get_fallow_version()

    for pipe in pipelines:
        if selected and pipe.name not in selected:
            continue
        result = PipelineResult(name=pipe.name, title=pipe.title)
        args = pipe.args_builder({})
        result.command = f"fallow -c {config} {' '.join(args)} -f json -q"
        started = time.monotonic()
        try:
            env = run_fallow(root, config, args)
            raw_envs.append({"pipeline": pipe.name, "envelope": env})
            (output_dir / f"{pipe.name}.json").write_text(json.dumps(env, indent=1))
            result.duration_s = round(time.monotonic() - started, 2)
            evidence, stats = pipe.evidence_builder(env)
            result.evidence = evidence
            result.stats = stats
            result.raw_summary = env.get("summary") or {}
            result.ok = True
            pipe.grade_fn(result, env)
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            result.ok = False
            result.error = str(exc)
            result.grade = "red"
            result.headline = "fallow run failed"
        results.append(result)
        timings.append({"pipeline": pipe.name, "seconds": result.duration_s, "ok": result.ok})
        if fail_fast and result.grade == "red":
            break

    return results, raw_envs, timings


# --------------------------------------------------------------------------
# Markdown report
# --------------------------------------------------------------------------

def _zone_counts(evidence: list[Evidence]) -> dict:
    counts: dict[str, int] = {}
    for e in evidence:
        counts[e.zone] = counts.get(e.zone, 0) + 1
    return dict(sorted(counts.items()))


def render_markdown(report: CheckReport, dup_threshold: float) -> str:
    lines: list[str] = []
    ap = lines.append
    stamp = report.started_at
    ap("# Job Attune - JavaScript/TypeScript Check Pipelines Report")
    ap("")
    ap(f"Generated: {stamp}  ")
    ap(f"Tool: Fallow {report.fallow_version} ([fallow.tools](https://fallow.tools/docs/))  ")
    ap(f"Config: `{os.path.relpath(report.config_path, report.root)}`  ")
    ap(f"Project root: `{report.root}`")
    ap("")
    overall = report.overall
    ap(f"## Overall verdict: **{GRADE_BADGE[overall]}**")
    ap("")
    if overall == "red":
        ap("At least one pipeline reports red. Fix the red items below, then re-run "
           "`python3 scripts/attune_app/js_check_pipelines.py` to confirm the gate goes green.")
    elif overall == "amber":
        ap("No blocking findings. Amber items are review candidates - mostly scaffold and "
           "dependency hygiene - and can be scheduled as cleanup work.")
    else:
        ap("All pipelines passed clean.")
    ap("")
    ap("## Verdict per pipeline")
    ap("")
    ap("| # | Pipeline | Verdict | Headline | Duration |")
    ap("|---|----------|---------|----------|----------|")
    for i, r in enumerate(report.results, 1):
        status = r.headline if r.ok else f"FAILED: {r.error[:80]}"
        ap(f"| {i} | {r.title} | {GRADE_BADGE[r.grade]} | {status} | {r.duration_s}s |")
    ap("")

    for r in report.results:
        ap("---")
        ap("")
        ap(f"## {r.title} - **{GRADE_BADGE[r.grade]}**")
        ap("")
        if not r.ok:
            ap(f"Fallow failed to run this pipeline: `{r.error}`")
            ap("")
            continue
        ap(f"Command: `{r.command}`")
        ap("")
        if r.stats:
            compact = {}
            for k, v in r.stats.items():
                if k not in ("penalties", "styling_penalties"):
                    compact[k] = v
            ap("Key metrics: " + ", ".join(f"`{k}`={v}" for k, v in compact.items() if v is not None))
            penalties = r.stats.get("penalties") or r.stats.get("styling_penalties") or {}
            if penalties:
                worst = sorted(penalties.items(), key=lambda kv: -kv[1])[:4]
                ap("")
                ap("Largest health-score penalties: " + ", ".join(
                    f"`{k}` -{v}" for k, v in worst if v))
            ap("")
        if not r.evidence:
            ap("No findings - this category is clean.")
            ap("")
            continue
        zones = _zone_counts(r.evidence)
        ap(f"Findings by zone: " + ", ".join(f"`{z}`={n}" for z, n in zones.items()) +
           " (app = Job Attune code, scaffold = shadcn kit & helpers, infra = config/package.json)")
        ap("")

        app_first = sorted(r.evidence, key=lambda e: (0 if e.zone == "app" else 1,
                                                      -severity_rank(e.severity), e.path))
        limit = 25
        ap("| Severity | Zone | Location | Finding |")
        ap("|----------|------|----------|---------|")
        for e in app_first[:limit]:
            loc = f"`{e.path}:{e.where}`" if e.where != "-" else f"`{e.path}`"
            ap(f"| {e.severity} | {e.zone} | {loc} | {e.kind} - {e.detail} |")
        if len(app_first) > limit:
            ap(f"| ... | | | {len(app_first) - limit} more findings in the raw JSON |")
        ap("")

    ap("---")
    ap("")
    ap("## Method")
    ap("")
    ap("- Pipelines are executed by `scripts/attune_app/js_check_pipelines.py` (Python), "
       "which wraps the Fallow CLI, parses its JSON envelopes, classifies every finding by "
       "ownership zone, and grades each pipeline red/amber/green.")
    ap(f"- Duplication gate: {dup_threshold}% (mirrors `fallow.attune.json`).")
    ap("- Raw Fallow envelopes are kept in `scripts/attune_app/checks_out/*.json` for replay.")
    ap("- Zone map: app = `src/app/**`, `src/components/attune/**`, `src/lib/attune*.ts`; "
       "scaffold = `src/components/ui/**`, `src/hooks/**`, `src/lib/utils.ts`, `src/lib/db.ts`; "
       "infra = config files, `package.json`, `prisma/**`, `db/**`.")
    ap("")
    return "\n".join(lines)


def render_console(report: CheckReport) -> str:
    out = []
    for r in report.results:
        badge = GRADE_BADGE[r.grade]
        mark = {"GREEN": "o", "AMBER": "~", "RED": "!"}[badge]
        line = f"[{mark}] {badge:<5} {r.title:<38} {r.headline}"
        out.append(line)
        if not r.ok:
            out.append(f"      error: {r.error}")
    overall = report.overall
    out.append("")
    out.append(f"OVERALL: {GRADE_BADGE[overall]} "
               f"({len(report.by_grade('red'))} red / {len(report.by_grade('amber'))} amber / "
               f"{len(report.by_grade('green'))} green)")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    default_root = here.parent.parent
    parser = argparse.ArgumentParser(description="Job Attune JS/TS check pipelines (Fallow-powered)")
    parser.add_argument("--root", default=str(default_root))
    parser.add_argument("--config", default=str(here / "fallow.attune.json"))
    parser.add_argument("--pipelines", default="")
    parser.add_argument("--output-dir", default=str(here / "checks_out"))
    parser.add_argument("--report", default=str(default_root / "download" / "attune-js-checks-report.md"))
    parser.add_argument("--json-only", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    config = Path(args.config).resolve()
    if not root.exists():
        print(f"project root not found: {root}", file=sys.stderr)
        return 2
    if not config.exists():
        print(f"fallow config not found: {config}", file=sys.stderr)
        return 2

    # Guard: refuse to scan a root that does not look like the Job Attune project.
    if not (root / "src" / "app").exists():
        print(f"root does not look like the Job Attune project (no src/app): {root}", file=sys.stderr)
        return 2

    selected = [s.strip() for s in args.pipelines.split(",") if s.strip()]
    output_dir = Path(args.output_dir)

    started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = CheckReport(
        root=str(root), fallow_version=get_fallow_version(), config_path=str(config), started_at=started,
    )
    results, raw_envs, timings = run_pipelines(root, config, selected, output_dir, args.fail_fast)
    report.results = results

    summary_payload = {
        "tool": "attune-js-check-pipelines",
        "powered_by": f"fallow {report.fallow_version}",
        "generated_at": started,
        "root": str(root),
        "config": str(config),
        "overall": report.overall,
        "pipelines": [
            {
                "name": r.name, "title": r.title, "grade": r.grade, "ok": r.ok,
                "headline": r.headline, "command": r.command, "duration_s": r.duration_s,
                "stats": r.stats,
                "evidence_count": len(r.evidence),
                "zones": _zone_counts(r.evidence),
                "top_findings": [
                    {"severity": e.severity, "zone": e.zone, "path": e.path,
                     "where": e.where, "kind": e.kind, "detail": e.detail}
                    for e in sorted(r.evidence, key=lambda e: -severity_rank(e.severity))[:15]
                ],
                "error": r.error or None,
            }
            for r in results
        ],
        "timings": timings,
    }

    if args.json_only:
        print(json.dumps(summary_payload, indent=1))
    else:
        print(render_console(report))
        md = render_markdown(report, DUPLICATION_THRESHOLD_DEFAULT)
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(md)
        raw_path = output_dir / "summary.json"
        raw_path.write_text(json.dumps(summary_payload, indent=1))
        print()
        print(f"raw envelopes : {output_dir}")
        print(f"summary JSON  : {raw_path}")
        print(f"markdown report: {report_path}")

    overall = report.overall
    tool_failures = [r for r in results if not r.ok]
    if tool_failures:
        return 2
    return 1 if overall == "red" else 0


if __name__ == "__main__":
    sys.exit(main())
