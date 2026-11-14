#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Shared evaluation-contract helpers for the omnidecide kernel bridges.

``ckernel_native.py`` (ctypes) and ``wasm_kernel.py`` (wasmtime) expose the
exact same ``DeterministicDecisionKernel`` contract. The validation and
normalization rules below ARE that contract, shared verbatim so the two
transports cannot drift apart (previously they were near-verbatim copies in
each bridge; pylint flagged them as duplicate-code R0801).

Transport-specific plumbing stays in the bridges: ctypes structs and the
decision-pin recorder on the native tier, linear-memory marshalling and the
JSON envelope on the WASM tier. Contract helpers that raise take the
CALLER'S exception class so ``from ckernel import OmniDecideInferenceError``
keeps yielding exactly the class the active tier raises.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, List, Optional

__all__ = [
    "KERNEL_NAME",
    "TEXT_MODES",
    "SUPPORTED_LANGUAGE_CODES",
    "ENV_TEXT_MODE",
    "ENV_LANGUAGE",
    "check_no_image",
    "normalize_options",
    "rubric_levels",
    "require_non_empty",
    "clamp_top_k",
    "resolve_language_code",
    "read_header_version",
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

_ARITY_WORDS = {1: "one", 2: "two", 3: "three"}


def check_no_image(image: Any, error_type: type, bridge: str) -> None:
    """The engine passes extracted PDF text only; reject image evidence."""
    if image is not None:
        raise error_type(
            f"the {bridge} does not support the image channel "
            "(the engine passes extracted PDF text only)"
        )


def normalize_options(
    options: Any,
    error_type: type,
    primitive: str,
    minimum: int = 1,
    exact: Optional[int] = None,
) -> List[str]:
    """String-coerce the option list and enforce the primitive's arity.

    choice: minimum 1 (empty/None rejected); rank: minimum 2;
    compare: exactly 2. Error messages match the historical per-bridge
    wording exactly.
    """
    if not options or len(options) < minimum:
        raise error_type(
            f"{primitive} evaluation requires at least "
            f"{_ARITY_WORDS.get(minimum, minimum)} option"
            f"{'' if minimum == 1 else 's'}")
    if exact is not None and len(options) != exact:
        raise error_type(
            f"{primitive} evaluation requires exactly "
            f"{_ARITY_WORDS.get(exact, exact)} options")
    return [str(option) for option in options]


def rubric_levels(rubric: Any) -> List[str]:
    """Normalize a score rubric: a mapping contributes its keys in insertion
    order (exactly like iterating the dict in the Python kernel), any other
    iterable is string-coerced; blank levels drop; an empty rubric falls
    back to the historical five-level default."""
    if isinstance(rubric, dict):
        levels = list(rubric.keys())
    else:
        levels = [str(level) for level in (rubric or [])]
    levels = [level.strip() for level in levels if str(level).strip()]
    return levels or ["very low", "low", "medium", "high", "very high"]


def require_non_empty(text: str, error_type: type, primitive: str, noun: str) -> None:
    """noul needs a statement, extract needs an instruction."""
    if not text or not str(text).strip():
        raise error_type(f"{primitive} evaluation requires a non-empty {noun}")


def clamp_top_k(top_k: int) -> int:
    """extract's top_k clamps to the kernel's documented 1..10 band."""
    return max(1, min(10, int(top_k)))


def resolve_language_code(value: Any) -> str:
    """Validate a language code against SUPPORTED_LANGUAGE_CODES.

    ``None`` falls back to $ATTUNE_LANGUAGE, then to "und" (the generic
    baseline). Unknown codes are rejected here (odk_lang_from_code would
    silently map them to UND, which would hide a config typo). The native
    bridge additionally probes the kernel's own converter after this check.
    """
    code = (str(value).strip().lower() if value is not None
            else (os.environ.get(ENV_LANGUAGE) or "und").strip().lower())
    if code not in SUPPORTED_LANGUAGE_CODES:
        raise ValueError(
            f"unknown language {code!r} - expected one of "
            f"{', '.join(SUPPORTED_LANGUAGE_CODES)} (set {ENV_LANGUAGE} or pass language=...)"
        )
    return code


def read_header_version(header: Path) -> Optional[str]:
    """Read ODK_LIBRARY_VERSION from an omnidecide.h header (single parser
    for the vendored-header and co-located-header provenance paths)."""
    try:
        match = re.search(r'#define\s+ODK_LIBRARY_VERSION\s+"([^"]+)"',
                          header.read_text(encoding="utf-8"))
        return match.group(1) if match else None
    except OSError:
        return None
