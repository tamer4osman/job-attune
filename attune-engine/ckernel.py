#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""omnidecide kernel resolver - native-first with a WASM fallback tier.

engine.py imports ``ckernel`` exactly as before; this module is the seam
that keeps that import true while shipping two interchangeable kernel
backends (docs/LAYERED-KERNEL.md):

    engine.py ---- import ckernel ----> this resolver
                                          |
                     +--------------------+---------------------+
                     |  Tier 1: native fast path                |  Tier 2: portable fallback
                     |  ckernel_native.py -> libomnidecide.so/  |  wasm_kernel.py -> wasmtime
                     |  .dll/.dylib (built from the vendored    |  -> vendor/omnidecide-wasm/
                     |  omnidecide-c 2.0.0 tree)                |     dist/omnidecide.wasm
                     |  full native speed                       |  identical decisions, zero
                     |                                          |  C toolchain required
                     +------------------------------------------+

Selection policy - $ATTUNE_KERNEL (default "auto"):

    auto    native if loadable, otherwise WASM; the reason the native
            tier was skipped is recorded in FALLBACK_REASON and echoed
            once on stderr so run logs stay auditable
    native  native only: fail LOUDLY if the library is missing (no
            silent downgrade - determinism-sensitive operators pin the
            backend)
    wasm    WASM only (portable mode: no C compiler anywhere)

Both tiers implement the exact same module surface and the exact same
``DeterministicDecisionKernel`` contract (six evaluate methods returning
the five-key payload), so engine.py needs zero changes - and, because
every tier runs the omnidecide-c 2.0.0 decision engine (native build or
the official omnidecide-wasm dist of the same snapshot), decisions are
byte-identical across tiers (see verification/ in this release).

Version provenance: the native bridge parses the version from the
VENDORED header; this resolver re-derives it from the header co-located
with the library it actually loads (an $OMNIDECIDE_C_LIB override may
point elsewhere) and positively identifies 2.x binaries at runtime via
the spine API (odk_spine_* exists only in 2.0.0+).  The WASM bridge
probes odkw_version live inside the module.
"""

from __future__ import annotations

import ctypes
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

#: Repo root (the parent of attune-engine/) - keeps the tree relocatable.
ATTUNE = Path(__file__).resolve().parent.parent

ENV_KERNEL = "ATTUNE_KERNEL"        # auto | native | wasm
ENV_C_LIB = "OMNIDECIDE_C_LIB"      # native library override (ckernel_native honors it)
ENV_WASM = "OMNIDECIDE_WASM"        # omnidecide.wasm path override (wasm_kernel honors it)
#: Dist locations tried in order when $OMNIDECIDE_WASM is unset.
WASM_DIST_CANDIDATES = [
    ATTUNE / "vendor" / "omnidecide-wasm" / "dist" / "omnidecide.wasm",
]

#: Make both bridges importable no matter which entry point runs.
_ENGINE_DIR = Path(__file__).resolve().parent
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))


class KernelBackendUnavailable(RuntimeError):
    """No kernel backend could be loaded under the current policy.

    (The bridge-specific OmniDecideKernelUnavailable /
    OmniDecideInferenceError classes are re-exported from whichever tier
    is active, so callers that import them from this module get exactly
    the classes the active bridge raises.)"""


# --------------------------------------------------------------------------- #
# Tier 1 - native discovery (mirrors ckernel_native.py's search order)
# --------------------------------------------------------------------------- #

def _native_lib_filename() -> str:
    if sys.platform == "win32":
        return "omnidecide.dll"
    if sys.platform == "darwin":
        return "libomnidecide.dylib"
    return "libomnidecide.so"


def _native_candidates() -> List[Path]:
    override = os.environ.get(ENV_C_LIB)
    if override:
        return [Path(override).expanduser()]
    filename = _native_lib_filename()
    return [
        ATTUNE / "vendor" / "omnidecide-c" / "build" / filename,
        # conventional install target (make install prefix)
        Path("/usr/local/lib") / filename,
    ]


def _find_native_lib() -> Optional[Path]:
    for path in _native_candidates():
        if path.is_file():
            return path
    return None


def _parse_version_header(header: Path) -> Optional[str]:
    try:
        match = re.search(r'#define\s+ODK_LIBRARY_VERSION\s+"([^"]+)"',
                          header.read_text(encoding="utf-8"))
        return match.group(1) if match else None
    except OSError:
        return None


def _header_version_for(lib: Path) -> Tuple[Optional[str], str]:
    """Version of the tree the loaded library was built/installed from.

    Search: build-tree layout (<tree>/build/lib -> <tree>/include),
    sibling include dir, install-tree layout (/usr/local/lib ->
    /usr/local/include), then the vendored header (what ckernel_native
    itself quotes)."""
    candidates = [
        lib.parent.parent / "include" / "omnidecide.h",
        lib.parent / "include" / "omnidecide.h",
        lib.parent / "omnidecide.h",
        Path("/usr/local/include") / "omnidecide.h",
        ATTUNE / "vendor" / "omnidecide-c" / "include" / "omnidecide.h",
    ]
    for header in candidates:
        version = _parse_version_header(header)
        if version:
            return version, str(header)
    return None, ""


def _runtime_api_level(lib: ctypes.CDLL) -> str:
    """Positive runtime identification of the loaded binary.

    The kernel freezes its decision evidence stamp at "1.0.0" (so 1.x
    decisions replay bit-identically on 2.x) and the raw C API exposes no
    version function - but the spine API (odk_spine_*) exists only in
    2.0.0+, so its presence proves which binary was actually loaded."""
    try:
        lib.odk_spine_validate_scheme
        return "2.x (odk_spine_* present)"
    except AttributeError:
        return "1.x (no odk_spine_* symbols)"


def _try_native() -> Tuple[Optional[Any], Dict[str, Any]]:
    """Import the ctypes bridge; return (module, info) or (None, reason)."""
    lib_path = _find_native_lib()
    if lib_path is None:
        searched = ", ".join(str(p) for p in _native_candidates())
        return None, {"error": f"no native library found (searched: {searched})"}
    try:
        import ckernel_native  # the ctypes bridge; raises OmniDecideKernelUnavailable
    except Exception as exc:  # dlopen failure, symbol mismatch, ...
        return None, {"error": f"{type(exc).__name__}: {exc}",
                      "library": str(lib_path)}
    # ckernel_native.KERNEL_VERSION reads the VENDORED header, which may
    # not be the tree this library came from ($OMNIDECIDE_C_LIB override).
    # Re-derive from the header co-located with the loaded binary.
    version, header = _header_version_for(lib_path)
    info = {
        "backend": "native-c",
        "library": str(lib_path),
        "version": version or ckernel_native.KERNEL_VERSION,
        "version_source": header or "vendored header (via ckernel_native)",
        "api_level": _runtime_api_level(ctypes.CDLL(str(lib_path))),
    }
    return ckernel_native, info


# --------------------------------------------------------------------------- #
# Tier 2 - WASM availability (real probe: instantiate + close one kernel)
# --------------------------------------------------------------------------- #

def _resolve_wasm_path() -> Path:
    env = os.environ.get(ENV_WASM)
    if env:
        return Path(env).expanduser()
    for candidate in WASM_DIST_CANDIDATES:
        if candidate.is_file():
            os.environ[ENV_WASM] = str(candidate)  # keep wasm_kernel consistent
            return candidate
    return WASM_DIST_CANDIDATES[0]  # standard "not found" error downstream


def _try_wasm() -> Tuple[Optional[Any], Dict[str, Any]]:
    wasm_path = _resolve_wasm_path()
    try:
        import wasm_kernel
    except ImportError as exc:
        hint = ""
        if "wasmtime" in str(exc).lower() or exc.name == "wasmtime":
            hint = (" (the WASM tier needs the wasmtime wheel: "
                    "pip install wasmtime)")
        return None, {"error": f"{type(exc).__name__}: {exc}{hint}",
                      "module": str(wasm_path)}
    except Exception as exc:
        return None, {"error": f"{type(exc).__name__}: {exc}",
                      "module": str(wasm_path)}
    if not wasm_path.is_file():
        return None, {"error": f"omnidecide.wasm not found at {wasm_path}",
                      "module": str(wasm_path)}
    try:
        probe = wasm_kernel.DeterministicDecisionKernel(use_cuda=False)
        runtime_backend = probe.backend
        probe.close()
    except Exception as exc:
        return None, {"error": f"{type(exc).__name__}: {exc}",
                      "module": str(wasm_path)}
    info = {
        "backend": "wasm",
        "module": str(wasm_path),
        "version": wasm_kernel.KERNEL_VERSION,   # probed live via odkw_version
        "version_source": "runtime (odkw_version)",
        "runtime_backend": runtime_backend,
    }
    return wasm_kernel, info


# --------------------------------------------------------------------------- #
# Policy resolution
# --------------------------------------------------------------------------- #

def resolve(policy: Optional[str] = None) -> Tuple[Any, Dict[str, Any], Optional[str]]:
    """Return (bridge_module, backend_info, fallback_reason).

    fallback_reason is None unless the auto policy had to descend from the
    native tier to the WASM tier (then it carries the native-side error)."""
    chosen = (policy or os.environ.get(ENV_KERNEL) or "auto").strip().lower()
    if chosen not in ("auto", "native", "wasm"):
        raise ValueError(
            f"unknown {ENV_KERNEL} policy {chosen!r} - expected auto|native|wasm")

    native_reason: Optional[str] = None
    if chosen in ("auto", "native"):
        module, info = _try_native()
        if module is not None:
            return module, info, None
        native_reason = info["error"]
        if chosen == "native":
            raise KernelBackendUnavailable(
                f"{ENV_KERNEL}=native is pinned but the native kernel is "
                f"unavailable: {native_reason} (build libomnidecide via "
                f"scripts/build-kernel.sh, or clear the pin to use the "
                f"WASM fallback)")
    module, info = _try_wasm()
    if module is not None:
        return module, info, native_reason
    raise KernelBackendUnavailable(
        f"no kernel backend available under {ENV_KERNEL}={chosen}: "
        f"native: {native_reason or 'not attempted (policy=wasm)'}; "
        f"wasm: {info['error']}")


# --------------------------------------------------------------------------- #
# Module surface (exactly what engine.py expects from ckernel, plus provenance)
# --------------------------------------------------------------------------- #

_BRIDGE, _INFO, _FALLBACK = resolve()

KERNEL_NAME: str = _BRIDGE.KERNEL_NAME
#: True version of the LOADED kernel (header co-located with the native
#: library, or the live odkw_version probe for WASM) - both tiers ship the
#: omnidecide-c 2.0.0 decision engine.
KERNEL_VERSION: str = _INFO["version"]
#: Human-readable identity recorded in run manifests, e.g. "omnidecide-c 2.0.0".
KERNEL_ID: str = f"{KERNEL_NAME} {KERNEL_VERSION}"

TEXT_MODES = _BRIDGE.TEXT_MODES
SUPPORTED_LANGUAGE_CODES = _BRIDGE.SUPPORTED_LANGUAGE_CODES
ENV_TEXT_MODE = _BRIDGE.ENV_TEXT_MODE
ENV_LANGUAGE = _BRIDGE.ENV_LANGUAGE

DeterministicDecisionKernel = _BRIDGE.DeterministicDecisionKernel
#: Re-exported from the ACTIVE bridge, so `from ckernel import
#: OmniDecideKernelUnavailable` yields exactly the class the active tier raises.
OmniDecideKernelUnavailable = _BRIDGE.OmniDecideKernelUnavailable
OmniDecideInferenceError = _BRIDGE.OmniDecideInferenceError

#: Which tier is active: "native-c" or "wasm".
BACKEND: str = _INFO["backend"]
#: Full provenance record for logs / run manifests.
BACKEND_INFO: Dict[str, Any] = dict(_INFO)
#: Why the native tier was not used (None when native is active or policy=wasm).
FALLBACK_REASON: Optional[str] = _FALLBACK

__all__ = [
    "KERNEL_NAME", "KERNEL_VERSION", "KERNEL_ID",
    "SUPPORTED_LANGUAGE_CODES", "TEXT_MODES",
    "DeterministicDecisionKernel",
    "OmniDecideKernelUnavailable", "OmniDecideInferenceError",
    "BACKEND", "BACKEND_INFO", "FALLBACK_REASON", "resolve",
    "KernelBackendUnavailable",
]


def resolution() -> Dict[str, Any]:
    """One dict describing the loaded backend, for logs and manifests."""
    return {
        "backend": BACKEND,
        "kernel_id": KERNEL_ID,
        "fallback_reason": FALLBACK_REASON,
        **BACKEND_INFO,
    }


# One stderr line so every run log records which tier produced its
# decisions (stdout stays clean for the engine's progress protocol).
sys.stderr.write(
    "[ckernel] backend={backend} kernel={kernel} {where} api={api} "
    "fallback_reason={reason}\n".format(
        backend=BACKEND,
        kernel=KERNEL_ID,
        where=(f"library={BACKEND_INFO['library']} "
               if "library" in BACKEND_INFO else
               f"module={BACKEND_INFO.get('module', '?')} "),
        api=BACKEND_INFO.get("api_level", "n/a (wasm runtime)"),
        reason=FALLBACK_REASON or "none"))


if __name__ == "__main__":  # pragma: no cover - operator smoke entry
    import json
    print(json.dumps(resolution(), indent=2))
    kernel = DeterministicDecisionKernel(use_cuda=False)
    payload = kernel.evaluate_choice(
        "How should we fix the outage?",
        ["restart the service", "reinstall the operating system",
         "wait for the weekend"],
        "The service stopped responding. Restarting the service restored "
        "normal operation within seconds.")
    print(f"smoke decision: {payload['result']} "
          f"(confidence {payload['confidence']:.2f})")
    kernel.close()
