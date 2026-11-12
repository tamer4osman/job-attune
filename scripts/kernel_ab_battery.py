#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Kernel tier A/B battery: native omnidecide-c 2.0.0 (ctypes) vs WASM 2.0.0.

Mirrors the methodology of job-attune docs/VERIFICATION-1.8.0.md §2:
all six primitives with engine-shaped inputs, plus error paths. Every
payload must be identical (primitive, result, confidence, probability,
distribution) and every error must raise the same exception type.

Usage: python3 scripts/kernel_ab_battery.py
"""
import os
import sys
import time
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
WASM_DIST = APP / "vendor" / "omnidecide-wasm" / "dist" / "omnidecide.wasm"

sys.path.insert(0, str(APP / "attune-engine"))
os.environ.setdefault("OMNIDECIDE_WASM", str(WASM_DIST))

import ckernel_native as ckernel  # noqa: E402  (native ctypes bridge, kernel 2.0.0)
import wasm_kernel  # noqa: E402  (wasmtime bridge, kernel 2.0.0)

RUBRIC = {"none": "no credible evidence found",
          "partial": "some indirect evidence",
          "good": "clear evidence",
          "strong": "repeated, concrete evidence"}

CV_EN = ("Senior Data Engineer with 8 years of experience. Built and operated "
         "Apache Spark pipelines processing 4 TB/day on AWS. Led a team of 5 "
         "engineers, ran stakeholder reviews quarterly, and mentored three "
         "juniors into senior roles. PostgreSQL, Kafka, Airflow, dbt.")
CV_DE = ("Erfahrener Data Engineer mit acht Jahren Berufserfahrung. Hatte die "
         "Verantwortung für Spark-Pipelines, lokale Stakeholder-Kommunikation "
         "und Mentoring von Junior-Kolleginnen und Kollegen.")
CV_ZH = ("资深数据工程师，八年经验。负责构建和维护 Apache Spark 数据管道，"
         "每天处理 4 TB 数据。带过五人团队，定期向业务干系人汇报，并指导三名初级工程师。")
BIG = ("retrievable evidence line with the keyword spark. " * 200)  # ~9.4k chars
BIG2 = ("additional context paragraph mentioning spark and airflow. " * 250)  # ~13.7k


def cases():
    """(name, callable(kernel) -> payload) payload cases."""
    return [
        ("choice shortlist strong", lambda k: k.evaluate_choice(
            "Decide whether this candidate should be shortlisted for the role "
            "based only on the documented evidence.",
            ["shortlist", "reject"],
            "Role: Senior Data Engineer\nMust-have status: all must-have "
            "requirements have supporting evidence\nOverall evidence score: "
            "84/100\nTop evidence:\n- Built Apache Spark pipelines processing "
            "4 TB/day\n- Led a team of 5 engineers")),
        ("choice shortlist weak", lambda k: k.evaluate_choice(
            "Decide whether this candidate should be shortlisted for the role "
            "based only on the documented evidence.",
            ["shortlist", "reject"],
            "Role: Senior Data Engineer\nMust-have status: MUST-HAVE GAPS: "
            "apache spark\nOverall evidence score: 31/100\nTop evidence:\n- "
            "Used Excel in a marketing internship")),
        ("choice zh unicode/zh", lambda k: k.evaluate_choice(
            "该候选人是否应该进入下一轮？",
            ["进入下一轮", "淘汰"],
            "数据工程师岗位。候选人八年 Spark 经验，带过五人团队，"
            "所有必备技能都有证据支持。")),
        ("choice single option", lambda k: k.evaluate_choice(
            "Pick the fallback.", ["proceed"], "No further evidence.")),
        ("choice empty context", lambda k: k.evaluate_choice(
            "Pick one.", ["a", "b"], "")),
        ("choice whitespace context", lambda k: k.evaluate_choice(
            "Pick one.", ["a", "b"], "   \n\t  ")),
        ("choice big context 9k", lambda k: k.evaluate_choice(
            "Decide whether this candidate should be shortlisted.",
            ["shortlist", "reject"], BIG)),
        ("choice big context 13k", lambda k: k.evaluate_choice(
            "Decide whether this candidate should be shortlisted.",
            ["shortlist", "reject"], BIG + BIG2)),
        ("choice german umlauts", lambda k: k.evaluate_choice(
            "Soll dieser Kandidat weiterkommen?",
            ["Weiter", "Ausscheiden"], CV_DE)),
        ("score category rubric", lambda k: k.evaluate_score(
            "Rate the strength of evidence for technical requirements of this role.",
            RUBRIC, CV_EN)),
        ("score list rubric", lambda k: k.evaluate_score(
            "Rate the evidence strength.",
            ["very low", "low", "medium", "high", "very high"], CV_EN)),
        ("score zh", lambda k: k.evaluate_score(
            "评估该候选人技术证据的强度。", RUBRIC, CV_ZH)),
        ("score big context", lambda k: k.evaluate_score(
            "Rate the strength of evidence.", RUBRIC, BIG + BIG2)),
        ("noul supported", lambda k: k.evaluate_noul(
            "The candidate has production Apache Spark experience.", CV_EN)),
        ("noul unsupported", lambda k: k.evaluate_noul(
            "The candidate has ten years of Fortran on mainframes.", CV_EN)),
        ("noul zh", lambda k: k.evaluate_noul(
            "该候选人带过团队。", CV_ZH)),
        ("noul empty context", lambda k: k.evaluate_noul(
            "The candidate knows Kafka.", "")),
        ("rank two candidates", lambda k: k.evaluate_rank(
            "Order these candidates for a senior data role.",
            ["Candidate A: 8y Spark, led 5", "Candidate B: 2y SQL, junior"],
            "Role: Senior Data Engineer")),
        ("rank four candidates", lambda k: k.evaluate_rank(
            "Order these candidates best-to-worst.",
            ["A: spark kafka airflow", "B: excel powerpoint",
             "C: postgres dbt spark", "D: fortran mainframe"],
            "Evidence-heavy senior data engineering role.")),
        ("rank zh", lambda k: k.evaluate_rank(
            "按适配度排序。", ["候选人甲：八年 Spark 经验", "候选人乙：应届毕业生"],
            "高级数据工程师岗位。")),
        ("compare clear", lambda k: k.evaluate_compare(
            "Which candidate fits the senior data role better?",
            ["A: 8y spark team lead", "B: 1y intern excel"],
            "Senior Data Engineer, evidence-heavy pipeline work required.")),
        ("compare near-tie", lambda k: k.evaluate_compare(
            "Which candidate fits the senior data role better?",
            ["A: 8y spark pipeline lead", "B: 8y spark pipeline lead, mentored 2"],
            "Senior Data Engineer role; mentoring valued at the margin.")),
        ("compare zh", lambda k: k.evaluate_compare(
            "哪位候选人更适配？", ["甲：八年 Spark 经验", "乙：两年 SQL 经验"],
            "高级数据工程师岗位。")),
        ("extract top_k 3", lambda k: k.evaluate_extract(
            "Extract evidence for requirement: Apache Spark", CV_EN, top_k=3)),
        ("extract top_k 1", lambda k: k.evaluate_extract(
            "Extract evidence for requirement: mentoring", CV_EN, top_k=1)),
        ("extract top_k 10", lambda k: k.evaluate_extract(
            "Extract all evidence lines mentioning spark", BIG, top_k=10)),
        ("extract zh", lambda k: k.evaluate_extract(
            "提取关于 Spark 的证据。", CV_ZH, top_k=3)),
        ("extract big context", lambda k: k.evaluate_extract(
            "Extract evidence lines mentioning spark.", BIG + BIG2, top_k=3)),
        ("score default rubric (empty list)", lambda k: k.evaluate_score(
            "Rate the evidence.", [], CV_EN)),
    ]


def error_cases():
    """(name, callable(kernel) -> raises)."""
    return [
        ("choice zero options", lambda k: k.evaluate_choice("x", [], "y")),
        ("rank one option", lambda k: k.evaluate_rank("x", ["only"], "y")),
        ("compare one option", lambda k: k.evaluate_compare("x", ["a"], "y")),
        ("compare three options", lambda k: k.evaluate_compare(
            "x", ["a", "b", "c"], "y")),
        ("noul empty statement", lambda k: k.evaluate_noul("   ", "y")),
        ("extract empty instruction", lambda k: k.evaluate_extract("  ", "y")),
        ("unknown language", lambda _k: DeterministicKernelMaker(language="nope")),
        ("invalid text mode", lambda _k: DeterministicKernelMaker(text_mode="ebcdic")),
        ("image channel", lambda k: k.evaluate_choice(
            "x", ["a", "b"], "y", image=b"pixels")),
        ("morph_light (wasm-only limit)", lambda _k: DeterministicKernelMaker(morph_light=1)),
    ]


#: Documented, by-design divergences (not battery failures):
#: the omnidecide-wasm 1.0.0 wrapper exposes mode+language only, so the
#: wasm bridge refuses a truthy morph_light while the native bridge
#: accepts and ignores it. engine.py never sets morph_light.
DOCUMENTED_DIFFS = {"morph_light (wasm-only limit)"}


def DeterministicKernelMaker(**kw):
    """Build a kernel through the respective bridge under test."""
    return BRIDGE_CLASS(**kw)


def payload_equal(a, b):
    if type(a) is not type(b):
        return False, f"type mismatch {type(a).__name__} vs {type(b).__name__}"
    if isinstance(a, dict):
        if set(a) != set(b):
            return False, f"keys {sorted(a)} vs {sorted(b)}"
        for key in a:
            ok, why = payload_equal(a[key], b[key])
            if not ok:
                return False, f"[{key}] {why}"
        return True, ""
    if isinstance(a, list):
        if len(a) != len(b):
            return False, f"len {len(a)} vs {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            ok, why = payload_equal(x, y)
            if not ok:
                return False, f"[{i}] {why}"
        return True, ""
    if isinstance(a, float) or isinstance(b, float):
        if a != b:
            return False, f"{a!r} vs {b!r}"
        return True, ""
    if a != b:
        return False, f"{a!r} vs {b!r}"
    return True, ""


import functools  # noqa: E402

print = functools.partial(print, flush=True)


def main() -> int:
    global BRIDGE_CLASS
    print(f"native bridge : {ckernel.KERNEL_ID} "
          f"(backend {ckernel.DeterministicDecisionKernel(use_cuda=False).backend})")
    print(f"wasm bridge   : omnidecide-c {wasm_kernel.DeterministicDecisionKernel.kernel_version()} "
          f"(backend {wasm_kernel.DeterministicDecisionKernel(use_cuda=False).backend})")
    print(f"wasm artifact : {WASM_DIST}")
    print()

    passed = failed = 0
    failures = []

    # --- payload battery ---------------------------------------------------
    for name, call in cases():
        BRIDGE_CLASS = ckernel.DeterministicDecisionKernel
        kn = ckernel.DeterministicDecisionKernel(use_cuda=False)
        kw = wasm_kernel.DeterministicDecisionKernel(use_cuda=False)
        try:
            pn = call(kn)
        except Exception as exc:  # a payload case must not raise
            pn, en = None, exc
        else:
            en = None
        try:
            pw = call(kw)
        except Exception as exc:
            pw, ew = None, exc
        else:
            ew = None
        kn.close()
        kw.close()
        if en is not None or ew is not None:
            failed += 1
            failures.append(f"PAYLOAD {name}: unexpected exception "
                            f"native={en!r} wasm={ew!r}")
            continue
        ok, why = payload_equal(pn, pw)
        if ok:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            failures.append(f"PAYLOAD {name}: {why}")
            print(f"  FAIL  {name}: {why}")

    # --- error battery ------------------------------------------------------
    for name, call in error_cases():
        BRIDGE_CLASS = ckernel.DeterministicDecisionKernel
        kn = BRIDGE_CLASS(use_cuda=False)
        try:
            call(kn)
            tn, mn = None, None
        except Exception as exc:
            tn, mn = type(exc).__name__, str(exc)
        finally:
            kn.close()
        BRIDGE_CLASS = wasm_kernel.DeterministicDecisionKernel
        kw = BRIDGE_CLASS(use_cuda=False)
        try:
            call(kw)
            tw, mw = None, None
        except Exception as exc:
            tw, mw = type(exc).__name__, str(exc)
        finally:
            kw.close()
        if tn is None and tw is None:
            failed += 1
            failures.append(f"ERROR {name}: neither bridge raised")
            print(f"  FAIL  {name}: neither bridge raised")
            continue
        if tn != tw:
            if name in DOCUMENTED_DIFFS:
                passed += 1
                print(f"  DOC   {name}: by-design difference "
                      f"(native {tn} / wasm {tw})")
                failures.append(f"DOC {name}: native {tn}({(mn or '')[:70]}) "
                                f"vs wasm {tw}({(mw or '')[:70]})")
                continue
            failed += 1
            failures.append(f"ERROR {name}: native {tn} vs wasm {tw}")
            print(f"  DIFF  {name}: native {tn}({(mn or '')[:60]}) "
                  f"vs wasm {tw}({(mw or '')[:60]})")
            continue
        same_msg = mn == mw
        passed += 1
        note = "" if same_msg else "  (message wording differs)"
        print(f"  PASS  {name}: {tn}{note}")
        if not same_msg:
            failures.append(f"NOTE {name}: message wording differs "
                            f"(native: {mn!r} | wasm: {mw!r})")

    # --- timing spot-check ---------------------------------------------------
    instr = "Decide whether this candidate should be shortlisted."
    opts = ["shortlist", "reject"]
    ctx = CV_EN * 3  # ~2.3 KB
    for label, cls in (("native", ckernel.DeterministicDecisionKernel),
                       ("wasm  ", wasm_kernel.DeterministicDecisionKernel)):
        k = cls(use_cuda=False)
        t0 = time.perf_counter()
        n = 200
        for _ in range(n):
            k.evaluate_choice(instr, opts, ctx)
        dt = time.perf_counter() - t0
        k.close()
        print(f"  TIME  {label}: {n / dt:8.0f} decisions/s (2.3 KB choice, 200 calls)")

    print()
    print(f"battery: {passed} pass / {failed} fail")
    for line in failures:
        print(f"  - {line}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
