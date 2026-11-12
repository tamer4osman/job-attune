#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deep-diff two job-attune results.json runs (native kernel vs WASM kernel).

Mirrors the VERIFICATION-1.8.0 §3 allowlist: version pins, wall-clock
fields, absolute paths and manifest self-hashes are expected to differ;
every other leaf - all scores, confidences, distributions, rankings,
review queues - must be identical.

The ``$.spine`` subtree is provenance, not scoring: the integration spine
(kernel 2.0.0 F1/F4/F6/F7) is native-tier only and degrades on the WASM
tier with a machine-readable reason (docs/SPINE-FEATURES.md), so its
fields may differ or be absent across tiers BY DESIGN. For the same
reason the raw pass1_sha256 values cannot be equal across tiers once F1
is active: the native run legitimately carries content_tag annotations
and tag_conflict/mixed_document review items the WASM tier never
produces. The cross-tier gate therefore compares a SPINE-NORMALIZED
scoring view (spine block, content_tag annotations and spine-only review
items removed) - everything that constitutes a score, a ranking or a
human review item must still be byte-identical (issue I11, plumber
case-study fix round).
"""
import json
import sys
from pathlib import Path

# review items only the native tier can raise (they need the spine)
SPINE_ONLY_REVIEW_KINDS = {"tag_conflict", "mixed_document"}


def _strip(node):
    if isinstance(node, dict):
        return {k: _strip(v) for k, v in node.items()
                if k not in STRIP_KEYS and "_sha256" not in k}
    if isinstance(node, list):
        return [_strip(x) for x in node]
    return node


def scoring_view(doc: dict) -> str:
    """Spine-normalized canonical scoring payload (deterministic)."""
    clone = _strip(json.loads(json.dumps(doc)))
    clone.pop("spine", None)
    for cand in clone.get("candidates", []):
        for finfo in cand.get("files", []):
            finfo.pop("content_tag", None)
    rq = clone.get("review_queue")
    if isinstance(rq, list):
        clone["review_queue"] = [i for i in rq if i.get("kind") not in SPINE_ONLY_REVIEW_KINDS]
    return json.dumps(clone, sort_keys=True, ensure_ascii=False)

ALLOWLIST_EXACT = {
    "omnidecide_version",       # kernel pin: 1.0.0 vs 2.0.0 (the swap itself)
    "run_id",                   # run dir name (the A/B harness's own labels)
    "created_at",               # wall clock
    "elapsed_seconds",          # wall clock
    "updated_at",               # wall clock (progress file)
    "pct", "message", "stage",  # progress payload
    "main_folder", "floors_path", "run_dir", "folder_path",  # absolute paths
}
ALLOWLIST_SUBSTR = (
    "sha256_of_",      # manifest self-hashes over files that embed the pin
    "_sha256",         # file-hash maps (exports embed the kernel id)
    "time", "date",    # any timing-ish field
)
# determinism.pass1_sha256 is NOT allowlisted: it hashes the canonical
# scoring output BEFORE the kernel pin is attached, so identical scoring
# must produce identical hashes across kernels.

# identity/clock/path fields stripped from the scoring view (they differ for
# reasons that have nothing to do with the kernel tier)
STRIP_KEYS = ALLOWLIST_EXACT | {"determinism", "audit"}


def walk(a, b, path, diffs, allow_hash):
    # spine provenance differs (or vanishes) across tiers by design
    if path == "$.spine" or path.startswith("$.spine."):
        if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
            diffs.append((path, "ALLOWED (spine provenance: native-tier only, docs/SPINE-FEATURES.md)"))
        return
    if type(a) is not type(b):
        diffs.append((path, f"type {type(a).__name__} vs {type(b).__name__}"))
        return
    if isinstance(a, dict):
        for key in sorted(set(a) | set(b)):
            p = f"{path}.{key}"
            if key in ALLOWLIST_EXACT:
                if a.get(key) != b.get(key):
                    diffs.append((p, "ALLOWED (pin/clock/path)"))
                continue
            leaf_hash = allow_hash or any(s in key for s in ALLOWLIST_SUBSTR)
            if key in a and key in b:
                walk(a[key], b[key], p, diffs, leaf_hash)
            else:
                diffs.append((p, "ALLOWED (key present on one side only)"
                              if leaf_hash else "MISSING KEY"))
        return
    if isinstance(a, list):
        if len(a) != len(b):
            diffs.append((path, f"len {len(a)} vs {len(b)}"))
            return
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", diffs, allow_hash)
        return
    if a != b:
        if allow_hash:
            diffs.append((path, "ALLOWED (hash over pinned bytes)"))
        else:
            diffs.append((path, f"{a!r} != {b!r}"))


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", nargs="?", default="/tmp/ab_runs/native/results.json")
    parser.add_argument("candidate", nargs="?", default="/tmp/ab_runs/wasm/results.json")
    args = parser.parse_args()
    native = json.loads(Path(args.baseline).read_text())
    wasm = json.loads(Path(args.candidate).read_text())
    print(f"baseline : {args.baseline}")
    print(f"candidate: {args.candidate}")

    print(f"native determinism : {native['determinism']}")
    print(f"wasm   determinism : {wasm['determinism']}")
    same_hash = (scoring_view(native) == scoring_view(wasm))
    print("cross-kernel scoring view (spine-normalized) identical:", same_hash)
    print()

    diffs = []
    walk(native, wasm, "$", diffs, allow_hash=False)

    blocking = [d for d in diffs if not d[1].startswith(("ALLOWED", "MISSING KEY"))]
    allowed = [d for d in diffs if d[1].startswith(("ALLOWED", "MISSING KEY"))]

    print("leaves compared            : see diff count below")
    print(f"unexpected (blocking) diffs: {len(blocking)}")
    print(f"allowlisted diffs          : {len(allowed)}")
    for path, why in allowed:
        print(f"  ALLOWED {path}: {why}")
    for path, why in blocking[:30]:
        print(f"  BLOCK   {path}: {why}")

    # ranking + review queue spot proof
    def ranking(doc):
        return [(c["folder_name"], c["overall"], c["rank"]) for c in doc["candidates"]]

    same_rank = ranking(native) == ranking(wasm)
    print(f"\nranking + scores identical: {same_rank}")
    if not same_rank:
        for a, b in zip(ranking(native), ranking(wasm)):
            if a != b:
                print(f"  native {a} vs wasm {b}")

    print()
    if blocking or not same_rank or not same_hash:
        print("VERDICT: FAIL")
        return 1
    print("VERDICT: PASS - scoring output identical across kernels "
          "(only version pin + wall-clock differ)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
