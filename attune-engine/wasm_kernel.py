#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""WASM tier of the layered kernel: omnidecide-c 2.0.0 behind WebAssembly.

Portable fallback tier imported by the ``attune-engine/ckernel.py``
resolver when no native ``libomnidecide.so/.dll/.dylib`` can be loaded
(or when $ATTUNE_KERNEL=wasm pins the portable mode).  It runs the SAME
decision kernel from the vendored ``omnidecide-wasm`` dist
(kernel 2.0.0, ``vendor/omnidecide-wasm/dist/omnidecide.wasm``) through
the ``wasmtime`` Python runtime, so no C toolchain is needed anywhere.

Contract (identical to ckernel.py, so engine.py needs zero changes):

    DeterministicDecisionKernel(use_cuda=False, text_mode=..., language=...)
        .evaluate_choice(instruction, options, context)   -> payload dict
        .evaluate_score (instruction, rubric,  context)   -> payload dict
        .evaluate_noul  (statement,           context)    -> payload dict
        .evaluate_rank  (instruction, options, context)   -> payload dict
        .evaluate_compare(instruction, options, context)  -> payload dict
        .evaluate_extract(instruction, context, top_k=3)  -> payload dict

    payload = {"primitive": str, "result": ...,
               "confidence": float, "probability": float,
               "distribution": {str: float}}

How it works: the WASM module exports the C interop layer (odk_wasm.c):
``odkw_kernel_create(mode, language)`` returns a handle; ``odkw_evaluate``
runs one decision and returns a malloc'd, NUL-terminated JSON envelope
(the upstream five-key payload, C-authored, byte-identical to the native
wrapper build). This bridge marshals UTF-8 strings into the wasm32 linear
memory exactly like the reference JavaScript API does, parses the envelope
and maps it onto the engine's payload contract. Errors arrive as
``{"error":{"status":n,"message":...}}`` envelopes and raise
OmniDecideInferenceError, mirroring the ctypes bridge.

Differences vs the ctypes bridge (documented, none reachable by engine.py):
  - ``morph_light`` cannot be enabled: the omnidecide-wasm 1.0.0 wrapper
    exposes mode+language only. The engine never sets it; a truthy value
    raises NotImplementedError (fail loud, no silent behavior change).
  - Kernel identity is "omnidecide-c 2.0.0" (the version the dist was
    built from). Upstream guarantees 2.0.0 replays 1.x decisions
    byte-identically; the release A/B battery
    (scripts/kernel_ab_battery.py) verifies it empirically.
  - One wasmtime Store+Instance per kernel instance: the C wrapper module
    is single-threaded (its words), so per-run isolation also gives a
    ThreadingHTTPServer concurrent runs without a global lock.
"""

# pylint: disable=duplicate-code
# R0801: The Windows DLL-directory bootstrap block (add_dll_directory loop)
# is duplicated across ckernel_native.py, spine_kernel.py and this module.
# This is intentional -- each kernel bridge must set up the same Windows DLL
# search path before loading its respective shared library.

from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional

import wasmtime
from text_mode import resolve_text_mode

__all__ = [
    "KERNEL_NAME",
    "SUPPORTED_LANGUAGE_CODES",
    "TEXT_MODES",
    "DeterministicDecisionKernel",
    "OmniDecideKernelUnavailable",
    "OmniDecideInferenceError",
]

KERNEL_NAME = "omnidecide-c"


def _probe_kernel_version() -> str:
    """Read the kernel version from the WASM module itself (odkw_version),
    mirroring the ctypes bridge's single-source version probe."""
    try:
        host = _WasmHost()
        return host.read_cstring(host.version(host.store))
    except Exception:
        return "unknown"


#: Same table as the ctypes bridge. The wrapper validates mode/language
#: through the kernel's own odk_lang_from_code, so unknown codes fail at
#: kernel creation exactly like the native path.
TEXT_MODES = {"ascii": 0, "unicode": 1}
SUPPORTED_LANGUAGE_CODES = (
    "und", "en", "zh", "hi", "es", "ar", "fr", "bn", "pt", "id", "ur", "auto",
)

ENV_TEXT_MODE = "ATTUNE_TEXT_MODE"
ENV_LANGUAGE = "ATTUNE_LANGUAGE"

DEFAULT_WASM_PATH = (
    Path(__file__).resolve().parent.parent
    / "vendor" / "omnidecide-wasm" / "dist" / "omnidecide.wasm"
)


class OmniDecideKernelUnavailable(RuntimeError):
    """The omnidecide WASM module could not be loaded or the kernel
    handle could not be created."""


class OmniDecideInferenceError(RuntimeError):
    """Raised when a kernel evaluation call returns a non-OK status."""


# --------------------------------------------------------------------------- #
# WASM module loading (one Engine+Module per process, Store per kernel)
# --------------------------------------------------------------------------- #

_ENGINE = wasmtime.Engine()
_MODULE: Optional[wasmtime.Module] = None


def _load_module(wasm_path: Optional[Path]) -> wasmtime.Module:
    global _MODULE
    if _MODULE is not None and wasm_path is None:
        return _MODULE
    path = Path(wasm_path) if wasm_path else Path(
        os.environ.get("OMNIDECIDE_WASM") or DEFAULT_WASM_PATH)
    if not path.is_file():
        raise OmniDecideKernelUnavailable(
            f"omnidecide.wasm not found at {path}. Set OMNIDECIDE_WASM or "
            "place the omnidecide-wasm dist at vendor/omnidecide-wasm/dist/."
        )
    try:
        module = wasmtime.Module.from_file(_ENGINE, str(path))
    except Exception as exc:  # compile error / not a wasm module
        raise OmniDecideKernelUnavailable(
            f"failed to compile {path}: {exc}") from exc
    # The module declares exactly one import: Emscripten's heap-resize
    # hook. Under wasmtime the linear memory grows natively, so a stub
    # that reports success is faithful to ALLOW_MEMORY_GROWTH=1.
    expected = [(imp.module, imp.name) for imp in module.imports]
    if expected != [("env", "emscripten_resize_heap")]:
        raise OmniDecideKernelUnavailable(
            f"unexpected WASM imports {expected} - module/profile mismatch")
    if wasm_path is None:
        _MODULE = module
    return module


class _WasmHost:
    """One Store+Instance = one live kernel handle, fully isolated."""

    def __init__(self, wasm_path: Optional[Path] = None) -> None:
        module = _load_module(wasm_path)
        self.store = wasmtime.Store(_ENGINE)
        resize = wasmtime.Func(
            self.store,
            wasmtime.FuncType([wasmtime.ValType.i32()], [wasmtime.ValType.i32()]),
            lambda _requested: 1,
        )
        try:
            instance = wasmtime.Instance(self.store, module, [resize])
        except Exception as exc:
            raise OmniDecideKernelUnavailable(
                f"WASM instantiation failed: {exc}") from exc
        ex = instance.exports(self.store)
        self.mem: wasmtime.Memory = ex["memory"]
        self.malloc = ex["malloc"]
        self.free = ex["free"]
        self.kernel_create = ex["odkw_kernel_create"]
        self.kernel_free = ex["odkw_kernel_free"]
        self.kernel_count = ex["odkw_kernel_count"]
        self.evaluate = ex["odkw_evaluate"]
        self.version = ex["odkw_version"]
        self.backend = ex["odkw_backend"]
        self.last_status = ex["odkw_last_status"]
        self.last_error = ex["odkw_last_error"]
        self.odkw_free = ex["odkw_free"]
        # Run Emscripten static initializers (the JS glue does this too).
        ex["__wasm_call_ctors"](self.store)

    # -- linear-memory helpers (mirror js/omnidecide.js) ------------------- #
    def write_cstring(self, text: str) -> int:
        data = text.encode("utf-8") + b"\0"
        ptr = self.malloc(self.store, len(data))
        if not ptr:
            raise OmniDecideKernelUnavailable(
                "out of memory writing string argument")
        self.mem.write(self.store, data, ptr)
        return ptr

    def read_cstring(self, ptr: int) -> str:
        end = self.mem.data_len(self.store)
        window = self.mem.read(self.store, ptr, min(end, ptr + (1 << 20)))
        return window.split(b"\0", 1)[0].decode("utf-8")

    def write_str_array(self, items: List[str]) -> tuple:
        ptrs = [self.write_cstring(item) for item in items]
        array_ptr = 0
        if ptrs:
            array_ptr = self.malloc(self.store, 4 * len(ptrs))
            if not array_ptr:
                raise OmniDecideKernelUnavailable(
                    "out of memory writing options array")
            self.mem.write(
                self.store, struct.pack("<%dI" % len(ptrs), *ptrs), array_ptr)
        return array_ptr, ptrs

    def release(self, *ptrs: int) -> None:
        for ptr in ptrs:
            if ptr:
                self.free(self.store, ptr)


#: Kernel identity recorded in run manifests, e.g. "omnidecide-c 2.0.0".
KERNEL_VERSION = _probe_kernel_version()
KERNEL_ID = f"{KERNEL_NAME} {KERNEL_VERSION}"


# --------------------------------------------------------------------------- #
# Language / mode resolution (same rules as ckernel.py)
# --------------------------------------------------------------------------- #

def _resolve_text_mode(value: Any) -> str:
    """Validate a text-mode selection ("ascii" | "unicode").

    ``None`` falls back to $ATTUNE_TEXT_MODE, then to "unicode"
    (the default). See text_mode.py for the shared implementation."""
    return resolve_text_mode(value, ENV_TEXT_MODE, TEXT_MODES)


def _resolve_language(value: Any) -> str:
    code = (str(value).strip().lower() if value is not None
            else (os.environ.get(ENV_LANGUAGE) or "und").strip().lower())
    if code not in SUPPORTED_LANGUAGE_CODES:
        raise ValueError(
            f"unknown language {code!r} - expected one of "
            f"{', '.join(SUPPORTED_LANGUAGE_CODES)} (set {ENV_LANGUAGE} or pass language=...)"
        )
    return code


class DeterministicDecisionKernel:
    """wasmtime facade over the omnidecide WASM kernel; exposes the exact
    class/method/payload contract the engine was written against (see
    ckernel.py)."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        use_cuda: Optional[bool] = None,
        text_mode: Optional[str] = None,
        language: Optional[str] = None,
        morph_light: Optional[int] = None,
        wasm_path: Optional[Path] = None,
    ) -> None:
        if morph_light is not None and int(morph_light):
            raise NotImplementedError(
                "the omnidecide-wasm 1.0.0 wrapper does not expose "
                "morph_light; the engine never enables it"
            )
        self.text_mode: str = _resolve_text_mode(text_mode)
        self.language: str = _resolve_language(language)
        self._host = _WasmHost(wasm_path)
        mode_ptr = self._host.write_cstring(self.text_mode)
        lang_ptr = self._host.write_cstring(self.language)
        try:
            self._handle = self._host.kernel_create(self._host.store,
                                                    mode_ptr, lang_ptr)
            if not self._handle:
                message = self._host.read_cstring(
                    self._host.last_error(self._host.store))
                raise OmniDecideKernelUnavailable(
                    f"odkw_kernel_create failed: status "
                    f"{self._host.last_status(self._host.store)} {message}")
        finally:
            self._host.release(mode_ptr, lang_ptr)
        self._closed = False

    # -- lifecycle ---------------------------------------------------------- #
    def close(self) -> None:
        if not self._closed:
            self._host.kernel_free(self._host.store, self._handle)
            self._closed = True

    def __del__(self) -> None:  # pragma: no cover - GC timing varies
        try:
            self.close()
        except Exception:
            pass

    # -- introspection ------------------------------------------------------- #
    @property
    def backend(self) -> str:
        return self._host.read_cstring(self._host.backend(self._host.store))

    @property
    def providers(self) -> List[str]:
        return []

    @staticmethod
    def kernel_version() -> str:
        host = _WasmHost()
        return host.read_cstring(host.version(host.store))

    # -- internal helpers ---------------------------------------------------- #
    @staticmethod
    def _check_no_image(image: Any) -> None:
        if image is not None:
            raise TypeError(
                "the omnidecide WASM bridge does not support the image "
                "channel (the engine passes extracted PDF text only)"
            )

    def _eval(
        self,
        primitive: str,
        instruction: str,
        options: Optional[List[str]],
        context: str,
        top_k: int = 1,
    ) -> Dict[str, Any]:
        host = self._host
        prim_ptr = instr_ptr = ctx_ptr = array_ptr = env_ptr = 0
        opt_ptrs: List[int] = []
        try:
            prim_ptr = host.write_cstring(primitive)
            instr_ptr = host.write_cstring(instruction or "")
            ctx_ptr = host.write_cstring(context or "")
            if options is not None:
                array_ptr, opt_ptrs = host.write_str_array(options)
            env_ptr = host.evaluate(
                host.store, self._handle, prim_ptr, instr_ptr,
                array_ptr, len(opt_ptrs), ctx_ptr, top_k,
                0, 0, 0, 0,  # output caps: kernel defaults (never touch numbers)
            )
            if not env_ptr:
                raise OmniDecideInferenceError(
                    host.read_cstring(host.last_error(host.store))
                    or f"odk status {host.last_status(host.store)}")
            envelope_text = host.read_cstring(env_ptr)
        finally:
            if env_ptr:
                host.odkw_free(host.store, env_ptr)
            host.release(array_ptr, *opt_ptrs)
            host.release(ctx_ptr, instr_ptr, prim_ptr)
        try:
            envelope = json.loads(envelope_text)
        except json.JSONDecodeError as exc:
            raise OmniDecideInferenceError(
                f"malformed envelope from wrapper: {exc}") from exc
        if "error" in envelope:
            raise OmniDecideInferenceError(
                str(envelope["error"].get("message") or envelope["error"]))
        return {
            "primitive": envelope["primitive"],
            "result": envelope["result"],
            "confidence": round(float(envelope["confidence"]), 4),
            "probability": round(float(envelope["probability"]), 4),
            "distribution": {
                key: round(float(value), 4)
                for key, value in envelope["distribution"].items()
            },
        }

    # -- the six primitives --------------------------------------------------- #
    def evaluate_choice(
        self,
        instruction: str,
        options: List[str],
        context: str,
        image: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Select the option best supported by the evidence channel."""
        self._check_no_image(image)
        if not options:
            raise OmniDecideInferenceError(
                "choice evaluation requires at least one option")
        cleaned = [str(option) for option in options]
        return self._eval("choice", instruction, cleaned, context)

    def evaluate_score(
        self,
        instruction: str,
        rubric: Any,
        context: str,
        image: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Place the evidence on an ordered rubric scale; result in [0, 1]."""
        self._check_no_image(image)
        if isinstance(rubric, dict):
            levels = list(rubric.keys())
        else:
            levels = [str(level) for level in (rubric or [])]
        levels = [level.strip() for level in levels if str(level).strip()]
        if not levels:
            levels = ["very low", "low", "medium", "high", "very high"]
        return self._eval("score", instruction, levels, context)

    def evaluate_noul(
        self,
        statement: str,
        context: str,
        image: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Binary affirmation: is *statement* supported by the evidence?"""
        self._check_no_image(image)
        if not statement or not str(statement).strip():
            raise OmniDecideInferenceError(
                "noul evaluation requires a non-empty statement")
        return self._eval("noul", statement, None, context)

    def evaluate_rank(
        self,
        instruction: str,
        options: List[str],
        context: str,
        image: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Order all options best-to-worst ("a > b > c")."""
        self._check_no_image(image)
        if len(options) < 2:
            raise OmniDecideInferenceError(
                "rank evaluation requires at least two options")
        cleaned = [str(option) for option in options]
        return self._eval("rank", instruction, cleaned, context)

    def evaluate_compare(
        self,
        instruction: str,
        options: List[str],
        context: str,
        image: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Head-to-head comparison of exactly two options with tie detection."""
        self._check_no_image(image)
        if len(options) != 2:
            raise OmniDecideInferenceError(
                "compare evaluation requires exactly two options")
        cleaned = [str(option) for option in options]
        return self._eval("compare", instruction, cleaned, context)

    def evaluate_extract(
        self,
        instruction: str,
        context: str,
        image: Optional[Any] = None,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """Retrieve the ``top_k`` context snippets most relevant to *instruction*."""
        self._check_no_image(image)
        if not instruction or not str(instruction).strip():
            raise OmniDecideInferenceError(
                "extract evaluation requires a non-empty instruction")
        return self._eval("extract", instruction, None, context,
                          max(1, min(10, int(top_k))))


if __name__ == "__main__":  # pragma: no cover - smoke entry
    kernel = DeterministicDecisionKernel(use_cuda=False)
    print(f"{KERNEL_NAME} {DeterministicDecisionKernel.kernel_version()}, "
          f"backend={kernel.backend}")
    payload = kernel.evaluate_choice(
        "How should we fix the outage?",
        ["restart the service", "reinstall the operating system",
         "wait for the weekend"],
        "The service stopped responding. "
        "Restarting the service restored normal operation within seconds.",
    )
    print(f"{payload['result']} (confidence {payload['confidence']:.2f})")
    kernel.close()
