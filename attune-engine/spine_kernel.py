#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
"""omnidecide-c 2.0.0 integration-spine bridge (F1/F4/F6/F7).

This module exposes the **spine** of the vendored omnidecide-c 2.0.0 kernel
(``include/odk_spine.h``) to Job-Attune. The spine is what kernel 2.0.0 adds
over 1.x: content classification against registered schemes (F1), decision
pinning with self-contained replay records (F6), an observation log with
calibration reports (F4) and the extension API that registers Job-Attune's
scheme data (F7). The six decision primitives are NOT routed through this
module - scoring stays on the layered kernel resolver (``ckernel.py``), so
spine availability never changes a score.

Feature gate: ``$ATTUNE_SPINE`` = ``auto`` (default) | ``off``. The spine is
native-tier only (the WASM dist exports the evaluate surface, not the spine),
so ``resolve_spine`` returns ``None`` with a machine-readable reason whenever
the active backend is ``wasm``, the policy is ``off``, or the library cannot
be loaded - the engine runs unchanged in every one of those cases
(docs/SPINE-FEATURES.md).

Everything in here is deterministic: identical inputs produce identical
classification labels, pin records and calibration reports; timestamps are
caller-supplied because the spine never reads the wall clock.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "ENV_SPINE",
    "SCHEMES_PATH",
    "TAG_MIN_CHARS",
    "TAG_MIN_CONFIDENCE",
    "CV_SCHEME_ID",
    "COVER_SCHEME_ID",
    "SpineUnavailable",
    "SpineStatusError",
    "SpineContext",
    "load_spine_library",
    "evaluate_request",
    "schema_fingerprint",
    "KERNEL_VERSION",
    "resolve_spine",
]


#: Feature gate: "auto" (default) engages the spine whenever the native
#: kernel tier is active; "off" disables every spine feature explicitly.
ENV_SPINE = "ATTUNE_SPINE"

#: Registered scheme data (F7): the document-role schemes live as DATA, per
#: the kernel's zero-application-domain rule (vendor docs/EXTENSION.md).
SCHEMES_PATH = Path(__file__).resolve().parent / "data" / "spine_schemes.json"

#: Documents shorter than this are never content-classified (a near-empty
#: text layer says nothing about the document type).
TAG_MIN_CHARS = 200

#: Review floor for a filename-vs-content disagreement (I2, plumber case
#: study): a real cv/cover conflict expresses ~0.53 on the binary Tier A
#: scheme pair - barely above the 0.5 "no rule" prior - so the floor must
#: sit AT the prior, not above it, for planted mistags to reach the human
#: queue. Still below-floor rows are recorded as inconclusive annotations.
TAG_MIN_CONFIDENCE = 0.5

CV_SCHEME_ID = "attune-cv-document"
COVER_SCHEME_ID = "attune-cover-letter"

#: The Tier A "no rule matched" prior: a scheme that found no supporting term
#: reports exactly this confidence, so comparisons against it separate "no
#: evidence" from "weak but real evidence".
TIER_A_PRIOR = 0.5

_TEXT_CAP = 20000          # parity with the kernel's documented context limit
_UNSET = object()


class SpineUnavailable(RuntimeError):
    """The spine feature cannot be used in this process."""


class SpineStatusError(RuntimeError):
    """A spine call returned a non-OK status (message carries err.text)."""


# --------------------------------------------------------------------------- #
# ctypes bindings (include/odk_spine.h + generated odk_spine_types.h)
# --------------------------------------------------------------------------- #

class _Kv(ctypes.Structure):
    _fields_ = [("key", ctypes.c_char_p), ("value", ctypes.c_char_p)]


class _StrList(ctypes.Structure):
    _fields_ = [("count", ctypes.c_size_t), ("items", ctypes.POINTER(ctypes.c_char_p))]


class _Map(ctypes.Structure):
    _fields_ = [("count", ctypes.c_size_t), ("items", ctypes.POINTER(_Kv))]


class _RegRef(ctypes.Structure):
    _fields_ = [("kind", ctypes.c_char_p), ("id", ctypes.c_char_p),
                ("version", ctypes.c_int64), ("content_hash", ctypes.c_char_p)]


class _RegRefList(ctypes.Structure):
    _fields_ = [("count", ctypes.c_size_t), ("items", ctypes.POINTER(_RegRef))]


class _Classification(ctypes.Structure):
    _fields_ = [("scheme_id", ctypes.c_char_p), ("scheme_version", ctypes.c_int64),
                ("label", ctypes.c_char_p), ("facets", _Map), ("tier", ctypes.c_char_p),
                ("brain_snapshot_id", ctypes.c_char_p), ("confidence", ctypes.c_double),
                ("matched_terms", _StrList), ("rule_index", ctypes.c_int64)]


class _ClassificationList(ctypes.Structure):
    _fields_ = [("count", ctypes.c_size_t), ("items", ctypes.POINTER(_Classification))]


class _ClassificationResult(ctypes.Structure):
    _fields_ = [("subject_ref", ctypes.c_char_p), ("t", ctypes.c_int64),
                ("classifications", _ClassificationList)]


class _DecisionPin(ctypes.Structure):
    _fields_ = [("pin_id", ctypes.c_char_p), ("schema_fp", ctypes.c_char_p),
                ("kernel_version", ctypes.c_char_p), ("brain_snapshot_id", ctypes.c_char_p),
                ("context_hash", ctypes.c_char_p), ("inputs_ref", ctypes.c_char_p),
                ("request_json", ctypes.c_char_p), ("decision", ctypes.c_char_p),
                ("confidence", ctypes.c_double), ("tier", ctypes.c_char_p),
                ("replay_class", ctypes.c_char_p), ("timestamp", ctypes.c_int64),
                ("registrations", _RegRefList)]


class _SpineError(ctypes.Structure):
    _fields_ = [("text", ctypes.c_char * 256)]


_VOID_P = ctypes.c_void_p
_ERR_P = ctypes.POINTER(_SpineError)


def _bind(lib: ctypes.CDLL) -> None:
    """Declare argtypes/restypes once per library handle (idempotent)."""
    if getattr(lib, "_attune_spine_bound", False):
        return
    lib.odk_spine_create.restype = _VOID_P
    lib.odk_spine_free.argtypes = [_VOID_P]
    lib.odk_spine_schema_fingerprint.argtypes = [_VOID_P]
    lib.odk_spine_schema_fingerprint.restype = ctypes.c_char_p
    lib.odk_spine_register_json.argtypes = [_VOID_P, ctypes.c_char_p, ctypes.c_char_p,
                                            ctypes.c_char_p, _ERR_P]
    lib.odk_spine_register_json.restype = ctypes.c_int
    lib.odk_spine_classify.argtypes = [_VOID_P, ctypes.c_char_p, ctypes.c_char_p,
                                       ctypes.c_char_p, ctypes.c_int64,
                                       ctypes.POINTER(_ClassificationResult), _ERR_P]
    lib.odk_spine_classify.restype = ctypes.c_int
    lib.odk_spine_classification_result_release.argtypes = [
        ctypes.POINTER(_ClassificationResult)]
    lib.odk_spine_observation_ingest.argtypes = [_VOID_P, ctypes.c_char_p, _ERR_P]
    lib.odk_spine_observation_ingest.restype = ctypes.c_int
    lib.odk_spine_calibrate.argtypes = [_VOID_P, ctypes.c_char_p, _VOID_P, _ERR_P]
    lib.odk_spine_calibrate.restype = ctypes.c_int
    lib.odk_spine_calibration_report_to_json.argtypes = [_VOID_P]
    lib.odk_spine_calibration_report_to_json.restype = _VOID_P
    lib.odk_spine_calibration_report_release.argtypes = [_VOID_P]
    lib.odk_spine_pin.argtypes = [_VOID_P, _VOID_P, ctypes.c_char_p, ctypes.c_char_p,
                                  ctypes.c_char_p, ctypes.c_int64,
                                  ctypes.POINTER(_DecisionPin), _ERR_P]
    lib.odk_spine_pin.restype = ctypes.c_int
    lib.odk_spine_decision_pin_release.argtypes = [ctypes.POINTER(_DecisionPin)]
    lib.odk_spine_decision_pin_to_json.argtypes = [ctypes.POINTER(_DecisionPin)]
    lib.odk_spine_decision_pin_to_json.restype = _VOID_P
    lib.odk_spine_pin_count.argtypes = [_VOID_P]
    lib.odk_spine_pin_count.restype = ctypes.c_size_t
    lib.odk_spine_pin_at.argtypes = [_VOID_P, ctypes.c_size_t]
    lib.odk_spine_pin_at.restype = ctypes.POINTER(_DecisionPin)
    lib.odk_kernel_free.argtypes = [_VOID_P]
    lib._attune_spine_bound = True


_LIB_CACHE: Dict[str, ctypes.CDLL] = {}


def _load_spine_library() -> ctypes.CDLL:
    """Load the native kernel library (the spine lives in the same .so).

    Search order mirrors ckernel_native: $OMNIDECIDE_C_LIB override, then the
    vendored build, then /usr/local/lib. Raises SpineUnavailable with a
    complete, operator-readable reason.
    """
    filename = ("omnidecide.dll" if sys.platform == "win32" else
                "libomnidecide.dylib" if sys.platform == "darwin" else "libomnidecide.so")
    override = os.environ.get("OMNIDECIDE_C_LIB")
    candidates = [Path(override).expanduser()] if override else []
    vendored = Path(__file__).resolve().parent.parent / "vendor" / "omnidecide-c" / "build" / filename
    candidates += [vendored, Path("/usr/local/lib") / filename]
    tried = []
    for path in candidates:
        if path.is_file():
            key = str(path)
            if key not in _LIB_CACHE:
                try:
                    _LIB_CACHE[key] = ctypes.CDLL(key)
                except OSError as exc:
                    raise SpineUnavailable(
                        f"spine library found at {path} but failed to load: {exc}") from exc
            _bind(_LIB_CACHE[key])
            return _LIB_CACHE[key]
        tried.append(str(path))
    raise SpineUnavailable(
        f"the spine requires the native kernel library ({filename}), which was not found. "
        f"Build it with scripts/build-kernel.sh. Searched: {', '.join(tried)}")


def _now_ms() -> int:
    return int(time.time() * 1000)


class SpineContext:
    """One spine handle with Job-Attune's document-role schemes registered.

    Lifecycle: ``open()`` in main() before the pipeline runs, ``close()``
    after pins are exported. A context is reusable across the engine's two
    determinism passes (classification is a pure function of the text);
    per-pass counters are reset by the pipeline so the manifest reports
    single-pass quantities.
    """

    def __init__(self, lib: ctypes.CDLL, handle: int, fingerprint: str) -> None:
        self._lib = lib
        self._handle = handle
        self.fingerprint = fingerprint
        self.classify_calls = 0
        self.tag_conflicts = 0
        self.mixed_documents = 0
        self.pins_created = 0
        self.pin_errors = 0
        self.pin_error_sample: Optional[str] = None

    # -- lifecycle ----------------------------------------------------------- #
    @classmethod
    def open(cls, register_schemes: bool = True) -> "SpineContext":
        lib = _load_spine_library()
        handle = lib.odk_spine_create()
        if not handle:
            raise SpineUnavailable("odk_spine_create returned NULL")
        try:
            fingerprint = lib.odk_spine_schema_fingerprint(handle).decode("utf-8")
            ctx = cls(lib, handle, fingerprint)
            if register_schemes:
                schemes = json.loads(SCHEMES_PATH.read_text(encoding="utf-8"))
                ctx._register_scheme_set(schemes)
            return ctx
        except Exception:
            lib.odk_spine_free(handle)
            raise

    def close(self) -> None:
        if self._handle:
            self._lib.odk_spine_free(self._handle)
            self._handle = 0

    def _register_scheme_set(self, schemes: List[dict]) -> None:
        err = _SpineError()
        status = self._lib.odk_spine_register_json(
            self._handle, b"scheme_set",
            json.dumps(schemes, ensure_ascii=False).encode("utf-8"),
            b"attune://spine-schemes", ctypes.byref(err))
        if status != 0:
            raise SpineStatusError(
                f"registering {SCHEMES_PATH.name} failed: "
                f"{err.text.decode('utf-8', 'replace') or f'spine status {status}'}")

    # -- F1: classification --------------------------------------------------- #
    def classify(self, subject_ref: str, text: str, scope: str = "role-tag") -> List[dict]:
        """Classify *text* against every active scheme (Tier A, deterministic).

        Returns one row per active scheme:
        ``{"scheme_id", "label", "confidence", "tier", "matched_terms"}``.
        """
        self.classify_calls += 1
        result = _ClassificationResult()
        err = _SpineError()
        status = self._lib.odk_spine_classify(
            self._handle, subject_ref.encode("utf-8"), text[:_TEXT_CAP].encode("utf-8"),
            scope.encode("utf-8"), _now_ms(), ctypes.byref(result), ctypes.byref(err))
        if status != 0:
            raise SpineStatusError(
                f"odk_spine_classify failed: "
                f"{err.text.decode('utf-8', 'replace') or f'spine status {status}'}")
        try:
            rows: List[dict] = []
            items = result.classifications.items
            for i in range(result.classifications.count):
                row = items[i]
                rows.append({
                    "scheme_id": row.scheme_id.decode("utf-8"),
                    "scheme_version": int(row.scheme_version),
                    "label": row.label.decode("utf-8"),
                    "confidence": round(float(row.confidence), 4),
                    "tier": row.tier.decode("utf-8"),
                    "matched_terms": [row.matched_terms.items[j].decode("utf-8")
                                      for j in range(row.matched_terms.count)],
                })
            return rows
        finally:
            self._lib.odk_spine_classification_result_release(ctypes.byref(result))

    def check_document_tag(self, cand: dict, finfo: dict, text: str, audit: list) -> None:
        """Cross-check a document's filename-derived role against its content.

        Annotates ``finfo["content_tag"]``; a confident disagreement raises a
        non-blocking ``tag_conflict`` review item (the human confirms tags in
        the UI, the pipeline never re-tags on its own). Never raises:
        classification trouble must not break a run - the annotation is
        advisory by design.
        """
        try:
            rows = self.classify(f"doc:{str(finfo.get('sha256', ''))[:16]}", text)
        except Exception as exc:  # error boundary: advisory feature, record + continue
            finfo["content_tag"] = {"error": f"{type(exc).__name__}: {exc}"}
            return
        by_scheme = {row["scheme_id"]: row for row in rows}
        cv_row = by_scheme.get(CV_SCHEME_ID)
        cover_row = by_scheme.get(COVER_SCHEME_ID)
        if not cv_row or not cover_row:
            return
        top = cv_row if cv_row["confidence"] >= cover_row["confidence"] else cover_row
        content = top["label"]
        confidence = float(top["confidence"])
        role = finfo.get("role", "")
        agrees: Optional[bool] = (content == role) if content in ("cv", "cover") else None
        finfo["content_tag"] = {
            "label": content,
            "confidence": confidence,
            "role": role,
            "agrees": agrees,
            "tier": top["tier"],
            "matched_terms": top["matched_terms"][:6],
        }
        if agrees is False and confidence >= TAG_MIN_CONFIDENCE:
            self.tag_conflicts += 1
            audit.append({
                "kind": "tag_conflict",
                "primitive": "classify",
                "candidate_ref": cand.get("candidate_ref"),
                "file": finfo.get("name"),
                "blocking": False,
                "confidence": confidence,
                "floor": TAG_MIN_CONFIDENCE,
                "detail": (
                    f"Document {finfo.get('name')} is tagged '{role}' by filename but its "
                    f"content classifies as '{content}' (tier A confidence {confidence:.2f}) - "
                    "confirm the role tag before acting on this candidate"),
            })
        # Mixed-document hint (plumber case study, bogdan_ionescu): when BOTH
        # role schemes scored strictly ABOVE the Tier A no-rule prior (0.5),
        # both found supporting terms - the file likely holds letter AND CV in
        # one document. (The losing scheme of a clean document sits exactly AT
        # the prior, so a mere margin test would flag every file.) Annotate
        # always; raise a non-blocking review item when it is the candidate's
        # only file, where the single-file default silently scored it as CV.
        if (cv_row["confidence"] > TIER_A_PRIOR
                and cover_row["confidence"] > TIER_A_PRIOR):
            finfo["content_tag"]["mixed_hint"] = True
            if len(cand.get("files") or []) == 1:
                audit.append({
                    "kind": "mixed_document",
                    "primitive": "classify",
                    "candidate_ref": cand.get("candidate_ref"),
                    "file": finfo.get("name"),
                    "blocking": False,
                    "confidence": round(min(cv_row["confidence"], cover_row["confidence"]), 4),
                    "floor": TAG_MIN_CONFIDENCE,
                    "detail": (
                        f"Single document {finfo.get('name')} classifies as BOTH cv and cover "
                        f"(tier A confidence {cv_row['confidence']:.2f}/{cover_row['confidence']:.2f}) - "
                        "likely a combined letter+CV file; confirm or split before acting"),
                })
                self.mixed_documents += 1

    # -- F6: decision pinning -------------------------------------------------- #
    def attach_to_kernel(self, kernel: Any) -> None:
        """Pin every kernel evaluation made through *kernel* (native tier).

        ``odk_spine_pin`` re-evaluates the exact request document and records
        an append-only DecisionPin (request bytes, decision, confidence,
        schema fingerprint, kernel version, registered customizations). The
        kernel is deterministic, so the pin's own evaluation returns exactly
        the engine's result; the cost is one extra kernel call per decision
        on the pinned pass only.
        """
        handle = kernel.native_handle()
        seq = {"n": 0}

        def _recorder(request: dict) -> None:
            seq["n"] += 1
            self._pin_request(handle, request, f"attune:kernel-call#{seq['n']}")

        kernel.attach_pin_recorder(_recorder)

    def _pin_request(self, kernel_handle: int, request: dict, inputs_ref: str) -> None:
        request_json = json.dumps(request, ensure_ascii=False)
        pin = _DecisionPin()
        err = _SpineError()
        status = self._lib.odk_spine_pin(
            self._handle, kernel_handle, request_json.encode("utf-8"),
            inputs_ref.encode("utf-8"), b"exact", _now_ms(),
            ctypes.byref(pin), ctypes.byref(err))
        if status != 0:
            # Audit integrity is additive by design: a pin failure is counted
            # and surfaced in the manifest, never fatal to the run.
            self.pin_errors += 1
            if self.pin_error_sample is None:
                self.pin_error_sample = err.text.decode("utf-8", "replace") or f"status {status}"
            return
        self.pins_created += 1
        self._lib.odk_spine_decision_pin_release(ctypes.byref(pin))

    def export_pins(self, path: Path) -> int:
        """Write every pin as one JSON line (schema field order, verbatim)."""
        count = int(self._lib.odk_spine_pin_count(self._handle))
        lines: List[str] = []
        for i in range(count):
            pin_ptr = self._lib.odk_spine_pin_at(self._handle, i)
            json_ptr = self._lib.odk_spine_decision_pin_to_json(pin_ptr)
            try:
                lines.append(ctypes.cast(json_ptr, ctypes.c_char_p).value.decode("utf-8"))
            finally:
                _libc_free(json_ptr)
        Path(path).write_text(
            "".join(line + "\n" for line in lines), encoding="utf-8")
        return count

    # -- F4: observations + calibration ---------------------------------------- #
    def ingest_observation(self, observation: dict) -> None:
        err = _SpineError()
        status = self._lib.odk_spine_observation_ingest(
            self._handle,
            json.dumps(observation, ensure_ascii=False).encode("utf-8"),
            ctypes.byref(err))
        if status != 0:
            raise SpineStatusError(
                f"observation ingest failed: "
                f"{err.text.decode('utf-8', 'replace') or f'spine status {status}'}")

    def calibrate(self, generated_from: str) -> dict:
        """Compute the F4 calibration report over the ingested log."""
        report = ctypes.create_string_buffer(4096)
        err = _SpineError()
        status = self._lib.odk_spine_calibrate(
            self._handle, generated_from.encode("utf-8"),
            ctypes.cast(report, _VOID_P), ctypes.byref(err))
        if status != 0:
            raise SpineStatusError(
                f"odk_spine_calibrate failed: "
                f"{err.text.decode('utf-8', 'replace') or f'spine status {status}'}")
        json_ptr = self._lib.odk_spine_calibration_report_to_json(
            ctypes.cast(report, _VOID_P))
        try:
            parsed = json.loads(ctypes.cast(json_ptr, ctypes.c_char_p).value.decode("utf-8"))
        finally:
            _libc_free(json_ptr)
        self._lib.odk_spine_calibration_report_release(ctypes.cast(report, _VOID_P))
        return parsed

    # -- manifest summary ------------------------------------------------------- #
    def reset_counters(self) -> None:
        """Called by the pipeline at the start of each determinism pass so the
        manifest reports single-pass quantities."""
        self.classify_calls = 0
        self.tag_conflicts = 0
        self.mixed_documents = 0

    def summary(self) -> dict:
        return {
            "schema_fingerprint": self.fingerprint,
            "schemes_file": str(SCHEMES_PATH.relative_to(SCHEMES_PATH.parent.parent)),
            "classify_calls": self.classify_calls,
            "tag_conflicts": self.tag_conflicts,
            "mixed_documents": self.mixed_documents,
            "pins": self.pins_created,
            "pin_errors": self.pin_errors,
            "pin_error_sample": self.pin_error_sample,
        }


_LIBC_FREE = None


def _libc_free(ptr: int) -> None:
    """Free a malloc'd string returned by the spine (plain libc free, exactly
    what the upstream C example does with report/json pointers)."""
    global _LIBC_FREE
    if ptr:
        if _LIBC_FREE is None:
            _LIBC_FREE = ctypes.CDLL(None).free
            _LIBC_FREE.argtypes = [_VOID_P]
        _LIBC_FREE(ctypes.cast(ptr, _VOID_P))


def load_spine_library() -> ctypes.CDLL:
    """Public loader (replay auditor re-derivation path uses the same .so)."""
    return _load_spine_library()


def schema_fingerprint() -> str:
    """Schema fingerprint of the running build (F5; pins record it)."""
    lib = _load_spine_library()
    handle = lib.odk_spine_create()
    if not handle:
        raise SpineUnavailable("odk_spine_create returned NULL")
    try:
        return lib.odk_spine_schema_fingerprint(handle).decode("utf-8")
    finally:
        lib.odk_spine_free(handle)


def _parse_kernel_version() -> str:
    """Read ODK_LIBRARY_VERSION from the vendored header (single source,
    same convention as ckernel_native)."""
    header = (Path(__file__).resolve().parent.parent / "vendor" / "omnidecide-c"
              / "include" / "omnidecide.h")
    try:
        import re
        match = re.search(r'#define\s+ODK_LIBRARY_VERSION\s+"([^"]+)"',
                          header.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    except OSError:
        pass
    return "unknown"


KERNEL_VERSION = _parse_kernel_version()


def evaluate_request(kernel_handle: int, request_json: str) -> Tuple[str, float, str]:
    """Re-derive one pinned decision on a native kernel handle.

    Evaluates the exact request document ``{primitive, instruction, options?,
    context, top_k?}`` (the bytes a DecisionPin records) and returns
    ``(decision, confidence, result_json)``. This is the kernel's own
    re-derivation entry point for integrations that replay pinned decisions
    (vendor docs/REPLAY.md); the replay auditor compares its output against
    the recorded pin. Raises SpineStatusError on a non-OK status.
    """
    lib = _load_spine_library()
    decision = ctypes.c_char_p()
    confidence = ctypes.c_double()
    result_json = ctypes.c_char_p()
    err = _SpineError()
    status = lib.odk_spine_evaluate_request(
        _VOID_P(kernel_handle), request_json.encode("utf-8"),
        ctypes.byref(decision), ctypes.byref(confidence), ctypes.byref(result_json),
        ctypes.byref(err))
    if status != 0:
        raise SpineStatusError(
            f"odk_spine_evaluate_request failed: "
            f"{err.text.decode('utf-8', 'replace') or f'spine status {status}'}")
    try:
        return (decision.value.decode("utf-8"), float(confidence.value),
                result_json.value.decode("utf-8"))
    finally:
        # Free the RAW malloc'd pointers (not .value, which is a Python copy).
        _libc_free(ctypes.cast(decision, _VOID_P))
        _libc_free(ctypes.cast(result_json, _VOID_P))


def resolve_spine(backend: str) -> Tuple[Optional[SpineContext], dict]:
    """Feature-gate resolution for the spine layer.

    Returns ``(spine_or_None, info)``; ``info`` is a machine-readable record
    for the run manifest. Never raises for unavailability - an unavailable
    spine degrades the app to exactly its pre-spine behavior.
    """
    policy = (os.environ.get(ENV_SPINE) or "auto").strip().lower()
    info: Dict[str, Any] = {"feature": "spine", "policy": policy, "backend": backend}
    if policy not in ("auto", "off"):
        raise ValueError(
            f"unknown {ENV_SPINE} policy {policy!r} - expected auto|off")
    if policy == "off":
        info.update(status="off", reason=f"{ENV_SPINE}=off")
        return None, info
    if backend != "native-c":
        info.update(
            status="unavailable",
            reason=(f"the spine is native-tier only; the active kernel backend is "
                    f"'{backend}' (docs/SPINE-FEATURES.md)"))
        return None, info
    try:
        ctx = SpineContext.open()
    except Exception as exc:
        info.update(status="unavailable", reason=f"{type(exc).__name__}: {exc}")
        return None, info
    info.update(status="active", **ctx.summary())
    return ctx, info


if __name__ == "__main__":  # pragma: no cover - operator smoke entry
    ctx, info = resolve_spine("native-c")
    print(json.dumps(info, indent=1))
    if ctx:
        rows = ctx.classify(
            "probe-doc", "Curriculum Vitae. Work experience, education, skills.")
        print(json.dumps(rows, indent=1))
        ctx.close()
