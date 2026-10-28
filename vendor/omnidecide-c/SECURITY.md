<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->

# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's
private vulnerability reporting: on this repository, open the **Security** tab and
choose **Report a vulnerability**. Include the library version
(`ODK_LIBRARY_VERSION`), a minimal input that triggers the problem and the
platform and compiler you used. Reports are handled on a best-effort basis.

## Supported versions

Only the latest 1.x release receives fixes.

## What the library does and does not touch

- It processes **text, JSON queries and brain snapshots that may come from
  untrusted sources**. Memory-safety bugs reachable from these inputs (out-of-bounds
  access, use after free, integer overflow, unbounded allocation) are in scope.
- It performs **no network access** and reads no environment variables.
- The only file access is to paths you pass explicitly: brain snapshots
  (`odk_brain_save_file` writes `<path>.tmp` then renames it; `odk_brain_load_file`
  reads) and the optional stopword and lexicon loaders. Validate and restrict
  those paths in your application.
- Snapshot loading caps entry counts and key lengths. The JSON parser limits
  nesting to 64 levels (deeper input, up to 2 million levels in our test, is
  rejected without crashing). Context and chunk limits are enforced and
  clamped to hard ceilings.

## Hardening that has been done

Warning-free builds under gcc, clang and musl with `-Wall -Wextra -Werror
-pedantic`; a 2,013-case golden corpus; a 5,443-check hostile-input runner that
also covers corrupt model files; AddressSanitizer, UndefinedBehaviorSanitizer, LeakSanitizer, valgrind
and ThreadSanitizer runs; and a randomized robustness run over the text, JSON,
snapshot and client entry points. **There has been no independent security audit.**
Treat the library accordingly when exposing it to hostile input, for example by
running it in a sandboxed process with memory and time limits.

## Model files

Scoring model files (`odk_kernel_load_model`) are **trusted configuration**.
The loader is hardened (strict size, magic, version, reserved bytes, NaN and
infinity checks, SHA-256, kernel left unchanged on failure), but the hash only
detects corruption: anyone who can write a file can write a valid hash, and a
model can change which option wins. Never load a model file from an untrusted
source, and validate a trained model on held-out data before deploying it.

## Not a security boundary

OmniDecide is a lexical decision engine. Its answers can be manipulated by
crafting the words of the context or options, so do not use it as the sole
control for authorization, safety or fraud decisions.
