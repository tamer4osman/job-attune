<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->
# HTTP API Reference

All endpoints live under `/api` on the local server (`http://127.0.0.1:3000`).
Every request — no exceptions — must carry the `X-Attune-Client` header
(any non-empty value, e.g. `ui` or `cli`); requests with
`Sec-Fetch-Site: cross-site` are rejected outright. See `server.py` (loopback guard).

```bash
curl -s -H "X-Attune-Client: cli" "http://127.0.0.1:3000/api/run" | jq
```

Errors are always `{"error": string}` with an appropriate status code
(400 validation, 404 unknown/not-found, 413 too large, 429 rate-limited,
500 failure, 504 timeout).

### Transport hardening (server-side, applies to every request)

- **Security headers** — every response carries `X-Content-Type-Options:
  nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`;
  HTML responses additionally carry a `Content-Security-Policy`
  (`script-src 'self'`, no remote origins — the UI is fully static and
  external; styles allow `'unsafe-inline'` because the views set string
  `style=""` attributes through the DOM builder, and `img-src` allows
  `data:` for the self-contained inline-SVG chevron in `app.css`).
- **Rate limit** — a per-client sliding window caps requests at
  `ATTUNE_RATE_LIMIT` per minute (default **300** — the run monitor polls
  at ~67/min, so normal UI use is far below the cap; set `0` to disable).
  Exceeding it returns `429` with a `Retry-After` header.
- **Socket timeout** — a client that stalls mid-request (headers or body
  never finished) is dropped after 30 s instead of holding a worker
  thread (slowloris mitigation).
- **`/api` boundary** — only `/api` itself and `/api/...` paths hit the
  API layer; unknown look-alikes (`/apifoo`) resolve as static paths and
  404 without touching the guard.
- **Body header validation** — a non-integer `Content-Length` is a
  `400` (a body over the 10 MiB cap stays a `413`).

---

## GET /api — ping

- **Response**: `{ "message": "Hello, world!" }` — the cheapest way to
  prove the guard lets your client through before scripting anything else.

## POST /api/browse — folder browser

Lists direct sub-directories of a path for the folder-picker dialog.

- **Body**: `{ "path": string }` — absolute or project-root-relative;
  empty/missing resolves to the project root.
- **Response**: `{ "path": resolved, "parent": string|null, "directories": [{ "name", "path" }] }`
  (max 400 entries, dot-files hidden).
- **Errors**: `404` path is not a directory, `500` browse failed.

## POST /api/scan — scan candidate folders

Classifies PDFs per candidate sub-folder (same alias sets and tie-breaking
as the engine).

- **Body**: `{ "folder": string }` — required.
- **Response**:
  ```json
  {
    "folder": "/abs/path",
    "candidates": [{
      "folder": "james_okafor",
      "files": [{ "name": "cv.pdf", "relPath": "james_okafor/cv.pdf",
                  "role": "cv", "sizeBytes": 34567 }],
      "hasCv": true, "hasCover": true
    }],
    "notes": ["\"maria_gomez\" contains no PDF files - candidate will be skipped"]
  }
  ```
  `role` is `cv`, `cover` or `unclassified`; notes are strings or
  `{folder, note}` objects.
- **Errors**: `400` missing folder, `404` folder not readable.

## POST /api/run — start a screening run

- **Body**:
  ```json
  {
    "folder": "/abs/path/to/candidates",
    "profile": { "profile_name": "...", "requirements": [ ... ] },
    "roleOverrides": { "james_okafor/anschreiben.pdf": "cover" },
    "pseudonymous": true
  }
  ```
  `folder` and `profile` are required; `roleOverrides` maps
  `<candidate>/<file>` to a role from the validation preview;
  `pseudonymous` defaults to true.
- **Response**: `{ "runId": "run-20261001010246" }` — returned immediately;
  the engine runs in the background (poll status). Run ids are
  collision-proof (4-hex suffix on timestamp clash).
- **Errors**: `400` missing folder/profile, `404` main folder not readable.

## GET /api/run — list runs

- **Response**: `{ "runs": [{ "runId", "status": "done"|"running"|"failed"|"starting",
  "pct", "finishedAt", "summary": { "candidates", "shortlisted", "topLabel",
  "profileTitle", "company", "reviewItems", "blocking" } | null }] }`
  Summaries are parsed from `results.json` with mtime caching.

## GET /api/run/status?run_id=… — poll progress

- **Response**: `{ "runId", "stage", "pct", "message" }` — mirrors the
  engine's `progress.json`. A run with no progress for 120 s is reported as
  `stage: "error"` (failed or stalled); a pre-progress run reports
  `stage: "starting"`.
- **Errors**: `404` unknown run (bad id, missing dir, or traversal attempt).

## GET /api/run/results?run_id=… — fetch full results

- **Response**: `{ "results": <engine results.json verbatim>,
  "decisions": [review-decision objects], "exports": [{ "kind", "ref", "file", "sha256" }] }`
- **Errors**: `404` unknown run or results not ready yet.

## POST /api/report — generate PDF exports

Spawns `make_report.py` for a finished run (120 s kill timer).

- **Body**: `{ "run_id": string, "pseudonymous": boolean }` — `pseudonymous`
  defaults to true and should stay on for sharing.
- **Response**: `{ "ok": true, "files": [{ "kind", "ref", "file", "sha256" }] }`
  from the fresh manifest (the UI re-reads the same list via
  `GET /api/run/results` before listing downloads).
- **Errors**: `404` unknown run, `500` generation failed, `504` timeout.

## GET /api/report?run_id=…&file=… — download an exported PDF

Streams one file from `exports/`, but **only** if it appears in the export
manifest (no arbitrary file reads). Content-Disposition names the download
`<runId>-attune-<label>.pdf`.

## GET /api/audit?run_id=… — read review decisions

- **Response**: `{ "decisions": [...] }` from `review_decisions.jsonl`
  (empty array when nothing was decided yet).

## POST /api/audit — record a human decision

- **Body**: `{ "run_id", "action": "signoff"|"resolve", "candidate_ref",
  "kind", "decision", "note?" }` — free-text fields are length-capped
  (candidate_ref/kind 64, decision 32, notes trimmed) because the JSONL is
  append-only.
- **Response**: `{ "ok": true }` (entry appended with an ISO timestamp).
- **Errors**: `404` unknown run.

## GET /api/template?name=… / GET /api/template — job-profile templates

- **`?name=`**: `{ "name", "profile" }`; **without**: `{ "templates": [{ "name", "title" }] }`.
- **Errors**: `400` invalid name (allow-list: letters, digits, space, `-`, `_`),
  `404` not found.

## POST /api/template — save or delete a template

- **Body**: `{ "action": "save"|"delete", "name", "profile?" }`
  (`profile` JSON capped at 2 MB on save; delete is idempotent).
- **Response**: `{ "ok": true, "name": "..." }` (save) / `{ "ok": true }` (delete).
- **Errors**: `400` invalid name/unknown action, `413` profile too large.
