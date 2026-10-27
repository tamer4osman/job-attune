# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""Confidence floors as data - vendored floors contract (Job Attune).

The floors contract was originally shipped inside the frozen OmniDecide 3.3.1
Python library (``omnidecide.floors``). Since the Python library is no longer
shipped (the omnidecide-c C11 kernel is the only kernel), this
module vendors that contract verbatim so the engine keeps the exact same
escalation semantics, calibration values and degrade-never-crash guarantees:

``load_floors(path=None)``
    Load the floor table. Defaults to the vendored calibration file
    ``data/floors_v1.json``; a missing or malformed file silently falls back
    to the historical global constant 0.40 for every primitive (a floor is a
    decision-critical configuration: degrade, never crash, and log loudly).

``should_escalate(primitive, confidence, floors=None)``
    The floor decision itself: ``True`` when *confidence* is strictly below
    the primitive's floor. Pure, deterministic, allocation-free. In hot
    paths, load the table once and pass it explicitly - the no-table form
    re-reads the shipped data file on every call (intentional live-reload
    semantics, so swapped floor data is picked up without a restart).

Design guarantees (unchanged from the original contract):
- the floor is a threshold consumed *downstream* of the kernel, so floor
  values cannot alter kernel behaviour;
- unknown config keys are ignored, values are clamped to ``[0, 1]``, an
  unknown primitive raises :class:`OmniDecideError` (caller bug, fail
  loudly), and a floor table missing a primitive's entry raises as well -
  a silently missing floor would defeat the mechanism.

Calibration data: Phase-1 (see the provenance block in ``data/floors_v1.json``)
measured per-primitive confidence floors for the six decision primitives over
a deterministic 1,920-episode corpus.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union

logger = logging.getLogger("attune.floors")

__all__ = [
    "DEFAULT_FLOOR",
    "FLOOR_DATA_VERSION",
    "OmniDecideError",
    "PRIMITIVES",
    "DEFAULT_FLOORS",
    "default_floors_path",
    "floors_version",
    "load_floors",
    "should_escalate",
    "escalation_record",
]


class OmniDecideError(Exception):
    """Base error for the floors contract (same name/semantics as the
    original omnidecide library exception, kept so callers that catch the
    family by type keep working)."""


#: Version of the shipped floor data schema (bump when the JSON layout changes).
FLOOR_DATA_VERSION = "1.0"

#: Historical global constant used before calibration (v3.0.0 - v3.2.x).
DEFAULT_FLOOR = 0.40

#: The six kernel primitives, fixed order for deterministic iteration.
PRIMITIVES = ("choice", "compare", "extract", "noul", "rank", "score")

#: Fallback table - exactly the pre-calibration behaviour.
DEFAULT_FLOORS: Dict[str, float] = {primitive: DEFAULT_FLOOR for primitive in PRIMITIVES}


def default_floors_path() -> Path:
    """Return the vendored floor data file shipped with this release."""
    return Path(__file__).resolve().parent / "data" / "floors_v1.json"


def floors_version(path: Optional[Union[str, Path]] = None) -> str:
    """Report the schema version of a floor data file ('unknown' if absent)."""
    target = Path(path) if path is not None else default_floors_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        return str(raw.get("version", "unknown"))
    except Exception:  # noqa: BLE001 - decision-critical config: degrade, never crash
        return "unknown"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def load_floors(path: Optional[Union[str, Path]] = None) -> Dict[str, float]:
    """Load a per-primitive floor table, degrading to :data:`DEFAULT_FLOORS`.

    Accepts either the shipped layout ``{"version": ..., "floors": {...}}`` or
    a bare ``{primitive: value}`` mapping. Unknown keys are ignored; values
    are clamped into ``[0, 1]``. A missing or malformed file logs a warning
    and returns the historical 0.40 table - the exact pre-calibration
    behaviour.
    """
    target = Path(path) if path is not None else default_floors_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.warning("floor data %s not found; falling back to %.2f defaults",
                       target, DEFAULT_FLOOR)
        return dict(DEFAULT_FLOORS)
    except Exception as exc:  # noqa: BLE001 - malformed data must not crash callers
        logger.warning("floor data %s malformed (%s); falling back to %.2f defaults",
                       target, exc, DEFAULT_FLOOR)
        return dict(DEFAULT_FLOORS)
    if not isinstance(raw, Mapping):
        logger.warning("floor data %s is not an object; using %.2f defaults",
                       target, DEFAULT_FLOOR)
        return dict(DEFAULT_FLOORS)
    entries = raw.get("floors") if isinstance(raw.get("floors"), Mapping) else raw
    floors = dict(DEFAULT_FLOORS)
    for key, value in entries.items():
        if key not in PRIMITIVES:
            continue
        try:
            floors[key] = _clamp01(float(value))
        except (TypeError, ValueError):
            logger.warning("floor value for %r is not numeric (%r); keeping %.2f",
                           key, value, DEFAULT_FLOOR)
    return floors


def should_escalate(
    primitive: str,
    confidence: float,
    floors: Optional[Mapping[str, float]] = None,
) -> bool:
    """Return ``True`` when *confidence* is strictly below the primitive floor.

    ``confidence == floor`` does **not** escalate (the floor is the lowest
    trusted value). Unknown primitives raise :class:`OmniDecideError`; a
    non-finite confidence raises as well, because silently trusting ``nan``
    would defeat the mechanism. An explicit *floors* table missing the
    requested primitive also raises - never a bare :class:`KeyError`.
    """
    if primitive not in PRIMITIVES:
        raise OmniDecideError(
            f"unknown primitive {primitive!r}; expected one of {', '.join(PRIMITIVES)}"
        )
    conf = float(confidence)
    if math.isnan(conf) or math.isinf(conf):
        raise OmniDecideError(f"non-finite confidence {confidence!r} for {primitive!r}")
    table = floors if floors is not None else load_floors()
    if primitive not in table:
        raise OmniDecideError(
            f"floor table has no entry for {primitive!r}; "
            f"expected all of {', '.join(PRIMITIVES)}"
        )
    return conf < float(table[primitive])


def escalation_record(
    primitive: str,
    payload: Union[float, Any],
    floors: Optional[Mapping[str, float]] = None,
) -> Dict[str, Any]:
    """Build a harness-friendly escalation record for one decision.

    *payload* may be a bare confidence value or a kernel result payload
    (anything exposing ``.confidence`` / ``["confidence"]``). The record is
    plain JSON-serialisable data intended for the caller's telemetry.
    Unknown primitives and partial *floors* tables raise
    :class:`OmniDecideError` - same contract as :func:`should_escalate`.
    """
    if primitive not in PRIMITIVES:
        raise OmniDecideError(
            f"unknown primitive {primitive!r}; expected one of {', '.join(PRIMITIVES)}"
        )
    if isinstance(payload, Mapping):
        conf = payload.get("confidence")
    elif isinstance(payload, (int, float)):
        conf = payload
    else:
        conf = getattr(payload, "confidence", None)
    if conf is None:
        raise OmniDecideError(f"no confidence value available for {primitive!r}")
    table = floors if floors is not None else load_floors()
    if primitive not in table:
        raise OmniDecideError(
            f"floor table has no entry for {primitive!r}; "
            f"expected all of {', '.join(PRIMITIVES)}"
        )
    floor_value = float(table[primitive])
    conf = float(conf)
    return {
        "primitive": primitive,
        "confidence": conf,
        "floor": floor_value,
        "escalate": bool(conf < floor_value),
        "floor_data_version": FLOOR_DATA_VERSION,
    }
