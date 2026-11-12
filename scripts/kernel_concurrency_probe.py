#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Concurrency + cold-start probe for both kernel tiers.

The job-attune server is a ThreadingHTTPServer: concurrent runs must not
interfere. The native tier is a per-process ctypes library (one engine
spawn per run); the WASM tier gives each DeterministicDecisionKernel its
own wasmtime Store+Instance. 8 threads x 10 decisions per tier must all
return the identical payload.
"""
import os
import sys
import threading
import time
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP / "attune-engine"))
os.environ.setdefault(
    "OMNIDECIDE_WASM",
    str(APP / "vendor" / "omnidecide-wasm" / "dist" / "omnidecide.wasm"))

import ckernel_native  # noqa: E402
import wasm_kernel  # noqa: E402

INSTR = "Decide whether this candidate should be shortlisted."
OPTS = ["shortlist", "reject"]
CTX = ("Role: Senior Data Engineer. Built Apache Spark pipelines processing "
       "4 TB/day; led a team of 5 engineers; mentored three juniors.") * 8


def eval_once(cls):
    k = cls(use_cuda=False)
    payload = k.evaluate_choice(INSTR, OPTS, CTX)
    k.close()
    return payload


def probe_tier(label, cls) -> bool:
    t0 = time.perf_counter()
    payload = eval_once(cls)
    cold_ms = (time.perf_counter() - t0) * 1000
    print(f"[{label}] first decision (incl. lifecycle): {cold_ms:.0f} ms "
          f"-> {payload['result']} @ {payload['confidence']}")

    expected = payload
    errors = []

    def worker():
        try:
            for _ in range(10):
                got = eval_once(cls)
                if got != expected:
                    errors.append(got)
        except Exception as exc:
            errors.append(exc)

    t0 = time.perf_counter()
    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    dt = time.perf_counter() - t0
    total = 8 * 10
    print(f"[{label}] concurrency: {total} decisions across 8 threads in "
          f"{dt * 1000:.0f} ms ({total / dt:.0f} decisions/s)")
    print(f"[{label}] mismatches/errors: {len(errors)}")
    for err in errors[:3]:
        print(f"  {err!r}")
    return not errors


def main() -> int:
    ok_native = probe_tier("native", ckernel_native.DeterministicDecisionKernel)
    ok_wasm = probe_tier("wasm", wasm_kernel.DeterministicDecisionKernel)
    print("VERDICT:", "PASS" if (ok_native and ok_wasm) else "FAIL")
    return 0 if (ok_native and ok_wasm) else 1


if __name__ == "__main__":
    sys.exit(main())
