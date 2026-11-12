# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Shared text mode resolution helper for kernel implementations.

Both the native (ckernel_native.py) and WASM (wasm_kernel.py) kernel
implementations need identical text mode validation logic. This module
provides the shared implementation to avoid pylint R0801 duplicate-code.
"""

from typing import Any

__all__ = ["resolve_text_mode"]


def resolve_text_mode(
    value: Any,
    env_var: str = "ATTUNE_TEXT_MODE",
    text_modes: dict = None,  # type: ignore[assignment]
) -> str:
    """Validate a text-mode selection ("ascii" | "unicode").

    ``None`` falls back to environment variable, then to "unicode"
    (the default: scoring-identical on pure-ASCII input and required for
    non-Latin scripts to carry kernel evidence). The environment variable
    name and valid modes are parameterized to allow the caller to supply
    their own constants.

    Args:
        value: The text mode value (str, None, or convertable to str)
        env_var: Environment variable name (default: "ATTUNE_TEXT_MODE")
        text_modes: Dict of valid text mode names to kernel enum values

    Returns:
        The normalized lowercase text mode string

    Raises:
        ValueError: If the mode is not in the allowed set
    """
    import os

    if text_modes is None:
        text_modes = {"ascii": 0, "unicode": 1}
    mode = (str(value).strip().lower() if value is not None
            else (os.environ.get(env_var) or "unicode").strip().lower())
    if mode not in text_modes:
        raise ValueError(
            f"unknown text mode {mode!r} - expected one of {sorted(text_modes)} "
            f"(set {env_var} or pass text_mode=...)"
        )
    return mode