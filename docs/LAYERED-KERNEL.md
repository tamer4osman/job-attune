<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->
# Layered Decision Kernel — native first, WASM when needed

Since v1.2.0 Job Attune ships its decision kernel in two interchangeable
tiers behind one import seam. The default path keeps **full native speed**;
the second tier is a **portable fallback** that runs the *same* kernel
compiled to WebAssembly, so the engine works on machines with no C
toolchain at all. Neither tier is mandatory for the other — WASM reliance
is never required on a machine that has the native library.

## Architecture

```
engine.py ---- import ckernel ----> ckernel.py (kernel resolver)
                                        |
                  +---------------------+------------------------+
                  |  Tier 1: native fast path              |  Tier 2: portable fallback
                  |  ckernel_native.py (ctypes)            |  wasm_kernel.py (wasmtime)
                  |  -> vendor/omnidecide-c/build/         |  -> vendor/omnidecide-wasm/
                  |     libomnidecide.so/.dylib/.dll       |     dist/omnidecide.wasm
                  |  full native speed                     |  identical decisions,
                  |  needs a one-time C build              |  zero C toolchain
                  +----------------------------------------+
```

`engine.py` still says `import ckernel` and still uses exactly two
symbols (`ckernel.DeterministicDecisionKernel`, `ckernel.KERNEL_ID`).
The resolver re-exports both from whichever tier it loads, so the scoring
pipeline is untouched by the swap — the same zero-edit seam the kernel
itself has always provided.

## The two tiers

| | Tier 1 — native | Tier 2 — WASM fallback |
|---|---|---|
| Module | `attune-engine/ckernel_native.py` | `attune-engine/wasm_kernel.py` |
| Artifact | `vendor/omnidecide-c/build/libomnidecide.so` (`.dylib` / `omnidecide.dll`) built via `scripts/build-kernel.sh` | `vendor/omnidecide-wasm/dist/omnidecide.wasm` (vendored, ready to run) |
| Kernel version | omnidecide-c **2.0.0** (vendored tree) | omnidecide-c **2.0.0** (official omnidecide-wasm dist of the same snapshot) |
| Extra dependency | a C11 compiler (build time only) | `pip install wasmtime` |
| Kernel-level speed | fastest (baseline) | ≈ 3× slower on kernel micro-benchmarks |
| Whole-run impact | baseline | ≈ +10% on a 14-candidate run (kernel time is a small share of the run) |
| Concurrency | per-run process isolation (server spawns one engine per run) | one wasmtime `Store`+`Instance` per kernel instance, matching the per-run model |

Both tiers execute the omnidecide-c **2.0.0** decision engine — the same
0.35/0.35/0.30 lexical blend, calibration scales and rounding. Upstream
guarantees 2.0.0 replays 1.x decisions byte-identically, and the release
pipeline verifies tier equivalence empirically: a 39-case A/B battery across
all six primitives (payloads and
error paths, English/German/Chinese, 13.7k-char contexts, near-tie
compares) plus a full-engine run whose **spine-normalized scoring view**
must be byte-identical across tiers: everything that constitutes a score,
a ranking or a human review item. (Raw `pass1_sha256` values may
legitimately differ once the spine is active — the native tier alone
carries `content_tag` annotations and spine-only review items, and the
spine block itself is native-tier provenance; `scripts/kernel_results_diff.py`
implements the normalized comparison, v1.3.2.)

## Selection policy — `$ATTUNE_KERNEL`

| Policy | Behavior |
|---|---|
| `auto` *(default)* | Load the native tier if the library is present and loadable; otherwise fall back to the WASM tier. The native-side reason is recorded in `ckernel.FALLBACK_REASON` and echoed once on stderr (`[ckernel] backend=... kernel=... fallback_reason=...`) so run logs stay auditable. |
| `native` | Native tier only. Fail **loudly** if the library is missing — determinism-sensitive operators pin the backend and get no silent downgrade. |
| `wasm` | WASM tier only (portable mode: no C compiler anywhere). |

### Environment variables

| Variable | Meaning |
|---|---|
| `ATTUNE_KERNEL` | `auto` (default) \| `native` \| `wasm` |
| `OMNIDECIDE_C_LIB` | Absolute path to a native library, overriding the default search (`vendor/omnidecide-c/build/`, then `/usr/local/lib`). |
| `OMNIDECIDE_WASM` | Absolute path to `omnidecide.wasm`, overriding the vendored dist location. |
| `ATTUNE_TEXT_MODE` / `ATTUNE_LANGUAGE` | Multilingual text-layer config (unchanged; honored by both tiers). |

## Version provenance

Run manifests record `omnidecide_version` = `ckernel.KERNEL_ID`
(e.g. `omnidecide-c 2.0.0`). The resolver does not trust the vendored
header blindly:

- **native** — the version is re-derived from the header co-located with
  the library it actually loaded (so an `OMNIDECIDE_C_LIB` override
  reports the override's version), and the binary is positively
  identified at runtime: the spine API (`odk_spine_*`) exists only in
  2.0.0+, so its presence proves which binary is loaded
  (`api_level: "2.x (odk_spine_* present)"`).
- **wasm** — the version is probed live inside the module
  (`odkw_version`).

## Using portable mode

```bash
pip install wasmtime            # the only extra dependency
python3 attune-engine/engine.py --folder ... --profile ... --run-dir ...
# (no build step at all - the vendored .wasm ships in the tree)
```

Or pin it explicitly: `ATTUNE_KERNEL=wasm python3 attune-engine/engine.py ...`
The web app (`server.py`) needs nothing special — it spawns `engine.py`,
which resolves the tier itself.

## Design notes

- **Why not WASM-only?** The native tier is 3× faster at the kernel level
  and keeps the general-case cost at zero (no runtime, no wheel). WASM is
  the safety net, not the main road.
- **Why a resolver module instead of editing engine.py?** The kernel seam
  (`ckernel`) is the contract engine.py was written against; re-exporting
  the active tier behind it keeps the diff to the scoring pipeline empty,
  which is exactly what the A/B verification requires.
- **`morph_light`** cannot be enabled on the WASM tier (the
  omnidecide-wasm wrapper exposes mode + language only). engine.py never
  sets it; the WASM bridge raises `NotImplementedError` instead of
  silently changing behavior.
- **One stderr line per run** (`[ckernel] backend=...`) is the only
  observable difference in the engine's output channels; stdout/progress
  protocols are unchanged.

Upstream compatibility documents: `vendor/omnidecide-c/docs/UPGRADE-2.0.md`
and `vendor/omnidecide-wasm/README.md` (dist provenance).
