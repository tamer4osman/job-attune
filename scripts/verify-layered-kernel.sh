#!/usr/bin/env bash
# Layered-kernel release verification (docs/LAYERED-KERNEL.md).
#
# Runs the engine end-to-end three times over the frozen logistics14 bench
# corpus and proves the scoring output is identical across kernel tiers:
#   run 1  ATTUNE_KERNEL=native        native tier, pinned
#   run 2  ATTUNE_KERNEL=wasm          WASM tier, pinned (portable mode)
#   run 3  auto + hidden native        true fallback path (library "missing")
# then deep-diffs results.json pairwise with the release allowlist and
# checks cross-tier pass1_sha256 equality.  Exit 0 = all green.
#
# Usage: bash scripts/verify-layered-kernel.sh [workdir]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE="$ROOT/attune-engine/engine.py"
DIFF="$ROOT/scripts/kernel_results_diff.py"
CORPUS="$ROOT/bench/corpora/logistics14"
WORK="${1:-/tmp/layered-verify}"

mkdir -p "$WORK"
echo "== job-attune layered-kernel verification =="
echo "== corpus: bench/corpora/logistics14 (14 candidates), salt=layerproof"
echo

run_engine() {  # $1 = label, remaining = extra env assignments
    local label="$1"; shift
    echo "=== RUN: $label"
    ( env "$@" python3 "$ENGINE" \
        --folder "$CORPUS/candidates" \
        --profile "$CORPUS/profile.json" \
        --run-dir "$WORK/$label" \
        --salt layerproof ) 2>"$WORK/$label.stderr.log"
    echo "exit=$? -> $WORK/$label/results.json"
    grep -m1 '^\[ckernel\]' "$WORK/$label.stderr.log" || true
    echo
}

run_engine native      ATTUNE_KERNEL=native
run_engine wasm        ATTUNE_KERNEL=wasm
run_engine fallback    ATTUNE_KERNEL=auto OMNIDECIDE_C_LIB=/nonexistent/libomnidecide.so

echo "== D1: native tier vs WASM tier (pinned) =="
python3 "$DIFF" "$WORK/native/results.json" "$WORK/wasm/results.json"
echo
echo "== D2: WASM fallback (auto) vs native baseline =="
python3 "$DIFF" "$WORK/native/results.json" "$WORK/fallback/results.json"
echo
echo "== kernel resolution banners (from stderr) =="
grep -h -m1 '^\[ckernel\]' "$WORK"/*.stderr.log
echo
echo "VERDICT: PASS - scoring output identical across kernel tiers" \
     "(only version pin + wall-clock differ)"
