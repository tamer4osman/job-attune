<!-- SPDX-License-Identifier: Apache-2.0 -->
# omnidecide-wasm dist (vendored fallback tier)

This directory vendors the **official WebAssembly dist** of the omnidecide
kernel, used by Job Attune's portable fallback tier
(`attune-engine/wasm_kernel.py`, selected by the `ckernel.py` resolver —
see `docs/LAYERED-KERNEL.md`).

| Artifact | Value |
|---|---|
| File | `dist/omnidecide.wasm` |
| Size | 212,763 bytes |
| SHA-256 | `3c1c8b0acdeb4d3eb8f9c47b115b15ed5017bf5f9951c1d13a351647a1ebbbdb` |
| Kernel version | omnidecide-c **2.0.0** (snapshot pin `561fdb8` of the upstream omnidecide-c repo) |
| Produced by | omnidecide-wasm 1.0.0 release pipeline, Emscripten 7.0.0 |
| Exports | `memory`, `malloc`, `free`, 11 `odkw_*` interop functions |
| Imports | exactly one: `env.emscripten_resize_heap` (satisfied natively by wasmtime's memory growth) |

Upstream guarantee: kernel 2.0.0 keeps the full 1.x C API and replays 1.x
decisions byte-identically (`vendor/omnidecide-c/docs/UPGRADE-2.0.md`,
`docs/COMPATIBILITY.md` in the omnidecide-wasm project). The release
verification in `verification/` confirms tier equivalence empirically.

Licensing: Apache-2.0 — see `LICENSE`, `NOTICE` and
`THIRD_PARTY_NOTICES.md` in this directory (upstream omnidecide-wasm
project files, unmodified).
