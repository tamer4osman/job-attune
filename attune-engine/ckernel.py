#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""omnidecide-c kernel bridge - the C11 decision kernel behind the Python API.

The engine scores through the **omnidecide-c** C11 kernel (vendored under
``download/omnidecide-c/``); this bridge is the only kernel path.  This
module loads ``libomnidecide.so`` via ctypes and exposes
the exact class/method/payload contract the engine was written against, so
the engine code above the kernel is untouched:

    DeterministicDecisionKernel(use_cuda=False)
        .evaluate_choice(instruction, options, context)      -> payload dict
        .evaluate_score (instruction, rubric,  context)      -> payload dict
        .evaluate_noul  (statement,           context)       -> payload dict
        .evaluate_rank  (instruction, options, context)      -> payload dict
        .evaluate_compare(instruction, options, context)     -> payload dict
        .evaluate_extract(instruction, context, top_k=3)     -> payload dict

Payload shape (the engine's five-key contract):

    {"primitive": str, "result": bool|float|str|list[str],
     "confidence": float, "probability": float, "distribution": {str: float}}

Numerical equivalence: omnidecide-c 1.0.0 is the C port of the same
deterministic embedded engine (same 0.35/0.35/0.30 lexical blend, 0.7/0.3
context/directional fusion, 6.0 choice-family and 8.0 noul calibration
scales, 0.02 compare tie margin, 240-char extract snippets, 20,000-char
context limit, identical English stopword list).  Values are rounded to four
decimals inside the C result struct (round(..., 4) semantics).
The A/B harness (scripts/verify_kernel_swap.py) proved the C port agrees
bit-for-bit with the original embedded engine on the demo corpus and the
bench corpora at migration time (see docs/VERIFICATION-1.8.0.md for the
historical evidence record).

Differences vs the original embedded-engine contract, by design:
  - ``use_cuda`` is accepted and ignored: the C kernel has a single
    deterministic code path (``backend`` is always "embedded-fallback").
  - The ``image`` channel is not wired through (the engine never passes
    images; it scores extracted PDF text only).  Passing a non-None image
    raises TypeError instead of silently ignoring evidence.
"""

from __future__ import annotations

import ctypes
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

__all__ = [
    "KERNEL_NAME",
    "KERNEL_VERSION",
    "KERNEL_ID",
    "SUPPORTED_LANGUAGE_CODES",
    "TEXT_MODES",
    "DeterministicDecisionKernel",
    "OmniDecideKernelUnavailable",
]

KERNEL_NAME = "omnidecide-c"

#: Text-layer modes exposed by the bridge (omnidecide-c odk_kernel_config).
#: "ascii"  = ODK_TEXT_ASCII_COMPAT (legacy byte-for-byte semantics, the
#:            historical default of this engine)
#: "unicode" = ODK_TEXT_UNICODE (NFC + Unicode case folding + script-aware
#:            segmentation; required for evidence written in non-Latin scripts;
#:            byte-identical on pure-ASCII input per docs/TEXT-MODES.md)
TEXT_MODES = {"ascii": 0, "unicode": 1}

#: Language codes accepted by odk_lang_from_code (docs/LANGUAGES.md).
#: "und" keeps the generic baseline (the historical default); "auto" enables
#: the deterministic detector. The nine non-English packs are UNREVIEWED by
#: native speakers upstream - enabling one is an explicit, audited choice.
SUPPORTED_LANGUAGE_CODES = (
    "und", "en", "zh", "hi", "es", "ar", "fr", "bn", "pt", "id", "ur", "auto",
)

#: Opt-in multilingual configuration (see DeterministicDecisionKernel). The
#: constructor kwargs take precedence; these environment variables are the
#: process-level fallback used by engine.py (ATTUNE_TEXT_MODE /
#: ATTUNE_LANGUAGE). Both default to the legacy behavior, so a run that
#: sets neither is bit-identical to every previous release.
ENV_TEXT_MODE = "ATTUNE_TEXT_MODE"
ENV_LANGUAGE = "ATTUNE_LANGUAGE"

#: Repo root (the parent of attune-engine/) - keeps the tree relocatable.
_BRIDGE_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_C_TREE = _BRIDGE_ROOT / "download" / "omnidecide-c"


class OmniDecideKernelUnavailable(RuntimeError):
    """The omnidecide-c shared library could not be loaded."""


# Error type for kernel evaluation failures (same name as the historical
# omnidecide library exception, kept so callers that catch the family by
# type keep working).
class OmniDecideInferenceError(RuntimeError):
    """Raised when a kernel evaluation call returns a non-OK status."""


def _parse_header_version() -> str:
    """Read ODK_LIBRARY_VERSION from the vendored header (single source)."""
    header = _DEFAULT_C_TREE / "include" / "omnidecide.h"
    try:
        match = re.search(r'#define\s+ODK_LIBRARY_VERSION\s+"([^"]+)"', header.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    except OSError:
        pass
    return "unknown"


KERNEL_VERSION = _parse_header_version()
#: Human-readable identity recorded in run manifests, e.g. "omnidecide-c 1.0.0".
KERNEL_ID = f"{KERNEL_NAME} {KERNEL_VERSION}"


# --------------------------------------------------------------------------- #
# Shared-library loading
# --------------------------------------------------------------------------- #

def _candidate_paths() -> List[Path]:
    """Search order: OMNIDECIDE_C_LIB override, then the vendored build."""
    override = os.environ.get("OMNIDECIDE_C_LIB")
    if override:
        return [Path(override).expanduser()]
    return [
        _DEFAULT_C_TREE / "build" / "libomnidecide.so",
        # conventional install target (make install prefix)
        Path("/usr/local/lib/libomnidecide.so"),
    ]


def _load_library() -> ctypes.CDLL:
    tried: List[str] = []
    for path in _candidate_paths():
        if path.is_file():
            try:
                return ctypes.CDLL(str(path))
            except OSError as exc:
                raise OmniDecideKernelUnavailable(
                    f"libomnidecide.so found at {path} but failed to load: {exc}"
                ) from exc
        tried.append(str(path))
    raise OmniDecideKernelUnavailable(
        "libomnidecide.so not found. Build it with: "
        "cc -std=c11 -ffp-contract=off -O2 -fPIC -shared -Iinclude -Isrc "
        "src/*.c -lm -o build/libomnidecide.so   (run inside download/omnidecide-c/). "
        f"Searched: {', '.join(tried)}"
    )


_LIB = _load_library()

# ---- C ABI constants (include/omnidecide.h) -------------------------------- #
_ODK_VALUE_NONE, _ODK_VALUE_BOOL, _ODK_VALUE_NUMBER, _ODK_VALUE_STRING, \
    _ODK_VALUE_LIST = 0, 1, 2, 3, 4
_ODK_ERROR_MAX = 256


class _DistEntry(ctypes.Structure):
    _fields_ = [("key", ctypes.c_char_p), ("value", ctypes.c_double)]


class _Distribution(ctypes.Structure):
    _fields_ = [("entries", ctypes.POINTER(_DistEntry)), ("count", ctypes.c_size_t)]


class _OdkResult(ctypes.Structure):
    _fields_ = [
        ("primitive", ctypes.c_char_p),
        ("kind", ctypes.c_int),
        ("boolean", ctypes.c_int),
        ("number", ctypes.c_double),
        ("string", ctypes.c_char_p),
        ("items", ctypes.POINTER(ctypes.c_char_p)),
        ("item_count", ctypes.c_size_t),
        ("confidence", ctypes.c_double),
        ("probability", ctypes.c_double),
        ("distribution", _Distribution),
    ]


class _OdkError(ctypes.Structure):
    _fields_ = [("code", ctypes.c_int), ("text", ctypes.c_char * _ODK_ERROR_MAX)]


_VOID_P = ctypes.c_void_p
_CHAR_PP = ctypes.POINTER(ctypes.c_char_p)

_LIB.odk_kernel_create.restype = _VOID_P
_LIB.odk_kernel_create.argtypes = []

# odk_kernel_config (include/omnidecide.h) - field order and types must match
# the C struct exactly; a zeroed struct selects every documented default, so
# the bridge only fills the fields it explicitly configures.
class _OdkKernelConfig(ctypes.Structure):
    _fields_ = [
        ("text_mode", ctypes.c_int),        # odk_text_mode
        ("stopwords", ctypes.c_int),        # odk_stopword_pack
        ("profile", ctypes.c_int),          # odk_input_profile
        ("context_max", ctypes.c_size_t),
        ("chunk_source_max", ctypes.c_size_t),
        ("max_chunks", ctypes.c_size_t),
        ("snippet_max", ctypes.c_size_t),
        ("over_limit", ctypes.c_int),       # odk_over_limit_strategy
        ("max_ranked", ctypes.c_size_t),
        ("max_snippet_chars", ctypes.c_size_t),
        ("max_total_chars", ctypes.c_size_t),
        ("max_work", ctypes.c_size_t),
        ("language", ctypes.c_int),         # odk_language
        ("morph_light", ctypes.c_int),
    ]


_LIB.odk_kernel_create_ex.restype = _VOID_P
_LIB.odk_kernel_create_ex.argtypes = [ctypes.POINTER(_OdkKernelConfig)]
_LIB.odk_lang_from_code.restype = ctypes.c_int
_LIB.odk_lang_from_code.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_int)]
_LIB.odk_lang_to_code.restype = ctypes.c_char_p
_LIB.odk_lang_to_code.argtypes = [ctypes.c_int]
_LIB.odk_kernel_language.argtypes = [_VOID_P]
_LIB.odk_kernel_language.restype = ctypes.c_int
_LIB.odk_kernel_text_mode.argtypes = [_VOID_P]
_LIB.odk_kernel_text_mode.restype = ctypes.c_int
_LIB.odk_kernel_free.argtypes = [_VOID_P]
_LIB.odk_kernel_free.restype = None
_LIB.odk_result_release.argtypes = [ctypes.POINTER(_OdkResult)]
_LIB.odk_result_release.restype = None
_LIB.odk_kernel_backend.argtypes = [_VOID_P]
_LIB.odk_kernel_backend.restype = ctypes.c_char_p

for _fn in ("odk_evaluate_choice", "odk_evaluate_rank", "odk_evaluate_compare"):
    getattr(_LIB, _fn).argtypes = [
        _VOID_P, ctypes.c_char_p, _CHAR_PP, ctypes.c_size_t,
        ctypes.c_char_p, _VOID_P, _VOID_P,
    ]
    getattr(_LIB, _fn).restype = ctypes.c_int
_LIB.odk_evaluate_score.argtypes = [
    _VOID_P, ctypes.c_char_p, _CHAR_PP, ctypes.c_size_t, ctypes.c_char_p, _VOID_P, _VOID_P,
]
_LIB.odk_evaluate_score.restype = ctypes.c_int
_LIB.odk_evaluate_noul.argtypes = [_VOID_P, ctypes.c_char_p, ctypes.c_char_p, _VOID_P, _VOID_P]
_LIB.odk_evaluate_noul.restype = ctypes.c_int
_LIB.odk_evaluate_extract.argtypes = [
    _VOID_P, ctypes.c_char_p, ctypes.c_char_p, _VOID_P, ctypes.c_int, _VOID_P,
]
_LIB.odk_evaluate_extract.restype = ctypes.c_int


# --------------------------------------------------------------------------- #
# Kernel wrapper
# --------------------------------------------------------------------------- #

def _lang_enum(code: str) -> int:
    """ISO code -> odk_language enum value, via the kernel's own converter
    (single source of truth; the enum is ABI-stable upstream)."""
    ok = ctypes.c_int(0)
    enum_value = _LIB.odk_lang_from_code(code.encode("utf-8"), ctypes.byref(ok))
    if not ok.value:
        raise ValueError(f"kernel rejected language code {code!r}")
    return int(enum_value)


def _resolve_text_mode(value: Any) -> str:
    """Validate a text-mode selection ("ascii" | "unicode").

    ``None`` falls back to $ATTUNE_TEXT_MODE, then to "unicode"
    (the default: scoring-identical on pure-ASCII input and required for
    non-Latin scripts to carry kernel evidence).
    ATTUNE_TEXT_MODE=ascii restores the byte-frozen ASCII behavior."""
    mode = (str(value).strip().lower() if value is not None
            else (os.environ.get(ENV_TEXT_MODE) or "unicode").strip().lower())
    if mode not in TEXT_MODES:
        raise ValueError(
            f"unknown text mode {mode!r} - expected one of {sorted(TEXT_MODES)} "
            f"(set {ENV_TEXT_MODE} or pass text_mode=...)"
        )
    return mode


def _resolve_language(value: Any) -> str:
    """Validate a language code through the kernel's own converter.

    ``None`` falls back to $ATTUNE_LANGUAGE, then to "und" (the generic
    baseline). Unknown codes are rejected here (odk_lang_from_code would
    silently map them to UND, which would hide a config typo)."""
    code = (str(value).strip().lower() if value is not None
            else (os.environ.get(ENV_LANGUAGE) or "und").strip().lower())
    if code not in SUPPORTED_LANGUAGE_CODES:
        raise ValueError(
            f"unknown language {code!r} - expected one of "
            f"{', '.join(SUPPORTED_LANGUAGE_CODES)} (set {ENV_LANGUAGE} or pass language=...)"
        )
    ok = ctypes.c_int(0)
    _LIB.odk_lang_from_code(code.encode("utf-8"), ctypes.byref(ok))
    if not ok.value:
        raise ValueError(f"kernel rejected language code {code!r}")
    return code


class DeterministicDecisionKernel:
    """ctypes facade over the omnidecide-c kernel; exposes the exact
    class/method/payload contract the engine was written against.

    Multilingual support (unicode default):
    ``text_mode`` and ``language`` configure the kernel through
    ``odk_kernel_create_ex``. The default text mode is "unicode"
    (scoring-identical on pure-ASCII input; the only mode in which
    non-Latin scripts contribute kernel evidence); "ascii" remains
    available for the byte-frozen legacy behavior. Every selection is
    validated against the kernel's own language converter. ``language``
    (default "und" = generic) enables that language's pack (stopwords,
    script normalization - see docs/LANGUAGES.md upstream)."""

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        use_cuda: Optional[bool] = None,
        text_mode: Optional[str] = None,
        language: Optional[str] = None,
        morph_light: Optional[int] = None,
    ) -> None:
        """Create the C kernel handle.

        ``cache_dir`` / ``use_cuda`` exist for signature parity and are
        ignored: the C kernel has exactly one (deterministic, CPU)
        execution path.

        ``text_mode`` ("ascii" | "unicode") and ``language`` (ISO code from
        SUPPORTED_LANGUAGE_CODES) select the kernel's text layer and language
        pack; ``None`` falls back to $ATTUNE_TEXT_MODE /
        $ATTUNE_LANGUAGE and then to the defaults ("unicode" / "und").
        ``morph_light`` switches the light matching morphology
        (off by default).
        """
        self._use_cuda: Optional[bool] = use_cuda
        self.text_mode: str = _resolve_text_mode(text_mode)
        self.language: str = _resolve_language(language)
        self._morph_light: int = 0 if morph_light is None else (1 if int(morph_light) else 0)
        legacy = (self.text_mode == "ascii" and self.language == "und" and not self._morph_light)
        if legacy:
            # Historical default construction: byte-identical path.
            self._handle = _LIB.odk_kernel_create()
        else:
            cfg = _OdkKernelConfig()
            ctypes.memset(ctypes.byref(cfg), 0, ctypes.sizeof(cfg))
            cfg.text_mode = TEXT_MODES[self.text_mode]
            cfg.language = _lang_enum(self.language)
            cfg.morph_light = self._morph_light
            self._handle = _LIB.odk_kernel_create_ex(ctypes.byref(cfg))
        if not self._handle:
            raise OmniDecideKernelUnavailable("odk_kernel_create returned NULL")
        self._closed = False

    # -- lifecycle ---------------------------------------------------------- #
    def close(self) -> None:
        if not self._closed and self._handle:
            _LIB.odk_kernel_free(self._handle)
            self._closed = True

    def __del__(self) -> None:  # pragma: no cover - GC timing varies
        try:
            self.close()
        except Exception:
            pass

    # -- introspection ------------------------------------------------------- #
    @property
    def backend(self) -> str:
        return _LIB.odk_kernel_backend(self._handle).decode("utf-8")

    @property
    def providers(self) -> List[str]:
        return []

    # -- internal helpers ---------------------------------------------------- #
    @staticmethod
    def _utf8(value: Any) -> bytes:
        return str(value).encode("utf-8")

    @staticmethod
    def _str_array(items: List[str]):
        encoded = [item.encode("utf-8") for item in items]
        return (ctypes.c_char_p * len(encoded))(*encoded)

    def _eval(self, fn, *args) -> Dict[str, Any]:
        out = _OdkResult()
        err = _OdkError()
        status = fn(self._handle, *args, ctypes.byref(out), ctypes.byref(err))
        if status != 0:  # ODK_OK == 0
            message = err.text.decode("utf-8", "replace") or f"odk status {err.code}"
            raise OmniDecideInferenceError(message)
        try:
            return self._to_payload(out)
        finally:
            _LIB.odk_result_release(ctypes.byref(out))

    @staticmethod
    def _to_payload(res: _OdkResult) -> Dict[str, Any]:
        if res.kind == _ODK_VALUE_BOOL:
            result: Any = bool(res.boolean)
        elif res.kind == _ODK_VALUE_NUMBER:
            result = round(res.number, 4)
        elif res.kind == _ODK_VALUE_STRING:
            result = res.string.decode("utf-8")
        elif res.kind == _ODK_VALUE_LIST:
            result = [res.items[i].decode("utf-8") for i in range(res.item_count)]
        else:  # _ODK_VALUE_NONE
            result = None
        distribution = {
            res.distribution.entries[i].key.decode("utf-8"):
                round(res.distribution.entries[i].value, 4)
            for i in range(res.distribution.count)
        }
        return {
            "primitive": res.primitive.decode("utf-8"),
            "result": result,
            "confidence": round(res.confidence, 4),
            "probability": round(res.probability, 4),
            "distribution": distribution,
        }

    @staticmethod
    def _check_no_image(image: Any) -> None:
        if image is not None:
            raise TypeError(
                "the omnidecide-c bridge does not support the image channel "
                "(the engine passes extracted PDF text only)"
            )

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
            raise OmniDecideInferenceError("choice evaluation requires at least one option")
        cleaned = [str(option) for option in options]
        return self._eval(
            _LIB.odk_evaluate_choice,
            self._utf8(instruction), self._str_array(cleaned), len(cleaned),
            self._utf8(context or ""), None,
        )

    def evaluate_score(
        self,
        instruction: str,
        rubric: Any,
        context: str,
        image: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Place the evidence on an ordered rubric scale; result in [0, 1].

        ``rubric`` may be a list of levels or a mapping - a mapping
        contributes its keys in insertion order, exactly like iterating the
        dict in the Python kernel.
        """
        self._check_no_image(image)
        if isinstance(rubric, dict):
            levels = list(rubric.keys())
        else:
            levels = [str(level) for level in (rubric or [])]
        levels = [level.strip() for level in levels if str(level).strip()]
        if not levels:
            levels = ["very low", "low", "medium", "high", "very high"]
        return self._eval(
            _LIB.odk_evaluate_score,
            self._utf8(instruction), self._str_array(levels), len(levels),
            self._utf8(context or ""), None,
        )

    def evaluate_noul(
        self,
        statement: str,
        context: str,
        image: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Binary affirmation: is *statement* supported by the evidence?"""
        self._check_no_image(image)
        if not statement or not str(statement).strip():
            raise OmniDecideInferenceError("noul evaluation requires a non-empty statement")
        return self._eval(
            _LIB.odk_evaluate_noul,
            self._utf8(statement), self._utf8(context or ""), None,
        )

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
            raise OmniDecideInferenceError("rank evaluation requires at least two options")
        cleaned = [str(option) for option in options]
        return self._eval(
            _LIB.odk_evaluate_rank,
            self._utf8(instruction), self._str_array(cleaned), len(cleaned),
            self._utf8(context or ""), None,
        )

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
            raise OmniDecideInferenceError("compare evaluation requires exactly two options")
        cleaned = [str(option) for option in options]
        return self._eval(
            _LIB.odk_evaluate_compare,
            self._utf8(instruction), self._str_array(cleaned), len(cleaned),
            self._utf8(context or ""), None,
        )

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
            raise OmniDecideInferenceError("extract evaluation requires a non-empty instruction")
        return self._eval(
            _LIB.odk_evaluate_extract,
            self._utf8(instruction), self._utf8(context or ""), None,
            max(1, min(10, int(top_k))),
        )


if __name__ == "__main__":  # pragma: no cover - smoke entry for operators
    kernel = DeterministicDecisionKernel(use_cuda=False)
    print(f"{KERNEL_ID}, backend={kernel.backend}")
    payload = kernel.evaluate_choice(
        "How should we fix the outage?",
        ["restart the service", "reinstall the operating system", "wait for the weekend"],
        "The service stopped responding. "
        "Restarting the service restored normal operation within seconds.",
    )
    print(f"{payload['result']} (confidence {payload['confidence']:.2f})")
    kernel.close()

    # Multilingual smoke: a Chinese decision that scores zero evidence in the
    # legacy ASCII mode must score real evidence in Unicode mode.
    question = "\u5982\u4f55\u4fee\u590d\u670d\u52a1\u4e2d\u65ad?"
    options = ["\u91cd\u542f\u670d\u52a1", "\u91cd\u88c5\u64cd\u4f5c\u7cfb\u7edf"]
    context = ("\u670d\u52a1\u505c\u6b62\u54cd\u5e94\u3002\u91cd\u542f\u670d\u52a1\u540e"
               "\u51e0\u79d2\u5185\u6062\u590d\u4e86\u6b63\u5e38\u8fd0\u884c\u3002")
    legacy_k = DeterministicDecisionKernel(use_cuda=False)
    uni_k = DeterministicDecisionKernel(use_cuda=False, text_mode="unicode", language="zh")
    legacy_dist = legacy_k.evaluate_choice(question, options, context)["distribution"]
    uni_dist = uni_k.evaluate_choice(question, options, context)["distribution"]
    print(f"zh ascii/und: {legacy_dist}")
    print(f"zh unicode/zh: {uni_dist}")
    legacy_k.close()
    uni_k.close()
