<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->

# Changelog

This project follows [semantic versioning](README.md#versioning) from 1.0.0.

## 1.0.0 - first public release

OmniDecide C is released as a standalone, dependency-free C11 library.

**What is included**

- A deterministic decision kernel with six primitives (`choice`, `score`,
  `noul`, `rank`, `compare`, `extract`), each returning a result, a confidence
  and a probability distribution.
- Two text modes: ASCII compatibility (the default) and Unicode (NFC, default
  case folding, script-aware segmentation, Unicode 15.1.0 data).
- Ten language packs (English, Chinese, Hindi, Spanish, Arabic, French, Bengali,
  Portuguese, Indonesian, Urdu), a generic mode and a deterministic
  auto-detector. All non-English packs are unreviewed by native speakers.
- Input profiles (plain, markdown, chat, log, JSON, JSONL, CSV, TSV, code, HTML
  text, extracted PDF text, auto-detect), configurable limits, over-limit
  strategies, and **truncation reporting** (`context_truncated`,
  `context_units_dropped` in `odk_result_meta`, filled by the `_opts` and
  `_call` evaluators; the plain evaluators still cut long contexts without a
  signal).
- A client pipeline: raw text plus JSON queries in, five-key JSON out.
- An image-fingerprint evidence channel (raw RGB pixels).
- The **explain API** (`docs/EXPLAIN.md`): every intermediate behind a decision.
- Optional **scoring model files** (`docs/MODEL.md`) and an experimental extra
  feature set (`docs/FEATURES.md`). With no model loaded the built-in default
  is used, whose values are the kernel's original constants.
- Opt-in outcome learning: an experience brain, learned word links and JSON
  snapshots (format v3; v1 and v2 snapshots still load, whatever library
  version wrote them).
- Makefile and CMake builds, seven examples, and the test suite: a 373-check
  smoke test, a 2,013-case golden regression corpus (`docs/GOLDEN.md`), a
  5,443-check hostile-input runner, a ThreadSanitizer probe, a documentation
  link check and a version-consistency check.

**Verification performed**

- Warning-free under `-Wall -Wextra -Werror -pedantic` with gcc, clang and
  musl-gcc; CMake builds and `ctest` pass with gcc and clang.
- The golden corpus is byte-identical on gcc and clang at -O0, -O1, -O2 and -O3,
  and on musl.
- Clean under AddressSanitizer, UndefinedBehaviorSanitizer, LeakSanitizer,
  valgrind and ThreadSanitizer (separate objects per thread, and one kernel
  shared by 8 threads, with and without a loaded model).
- Extreme-value model files (1e308, negative, denormal, zero) load and evaluate
  without crashes, NaN or infinity.

**Known limitations**

- The engine is lexical, not semantic: it can pick the wrong option when a
  distractor shares a word with the question, when the context mentions both
  options, or when the answer is a paraphrase. Validate it on your own data.
- Contexts longer than the configured limits are cut. Use the `_opts`
  evaluators to see it, raise the limits, use head+tail, or use Unicode mode.
- The language packs and the experimental features have not been validated on
  real labeled data. No trained model ships with the library.
- No independent third-party audit. macOS is covered by the CI workflow but has
  not been run. Windows and MSVC are not supported.
- Model files are trusted configuration: a valid hash detects corruption, not
  tampering.

**Compatibility and numbering**

- Earlier internal builds were numbered 3.x and 4.x and were never released.
  1.0.0 is the first public version; source comments no longer refer to the
  old numbers.
- The client pipeline scores a **fixed evidence stamp** (`"1.0.0"` for the whole
  1.x series), not the library version, so client decisions do not change
  between 1.x releases. The golden corpus masks `library_version`, so a patch
  release does not require regenerating it (verified by building 1.0.1 against
  the 1.0.0 corpus).
- The public structs may grow in minor releases (new fields are appended at the
  end). There is no ABI guarantee: link statically or rebuild when you upgrade.
