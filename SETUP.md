<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: 2026 Tamer Osman -->
# Job Attune 1.0.0 - source archive

GDPR-safe resume screening: a Next.js UI driving a deterministic Python scoring
engine, running on the omnidecide-c 1.0.0 C11 decision kernel (vendored under
`download/omnidecide-c/`, the only kernel - the floors contract
ships as `attune-engine/floors.py` with calibration data in
`attune-engine/data/floors_v1.json`). Candidate
documents are reduced to pseudonymous references before scoring; PDF exports
contain no raw PII.

## Layout

    src/                        Next.js app (UI + API routes)
    attune-engine/              Python engine, C-kernel bridge, PDF reporter,
                                vendored floors contract (floors.py + data/)
    bench/                      candidate-blind benchmark harness + frozen corpora
    download/omnidecide-c/      omnidecide-c 1.0.0 C11 kernel (the only kernel)
    attune-data/                templates (runs/ is created at runtime)
    attune-sample-data/         demo corpus: 6 candidates, 10 PDFs
    scripts/                    QA gates, sample generator, JS check pipelines
    docs/                       architecture, API, CLI, developer guide, marketing
    SETUP.md, requirements.txt, Dockerfile, LICENSE, NOTICE

## Prerequisites

- Bun 1.1+ (or Node 20+ with npm) - https://bun.sh
- Python 3.10+ (tested on 3.12)
- A C11 compiler (gcc/clang) + libm - one-time build of the omnidecide-c
  shared library (see Setup below)
- Optional: `fallow` CLI for the JS/TS check pipelines (`npm install -g fallow`)
- Optional: Docker — container images for the QA gate and the full app (see the Docker section below)

## Setup

    pip install -r requirements.txt   # reportlab + pypdf (engine itself: stdlib only)

    # build the omnidecide-c decision kernel (one-time):
    cd download/omnidecide-c
    mkdir -p build
    cc -std=c11 -ffp-contract=off -O2 -fPIC -shared -Iinclude -Isrc \
       src/*.c -lm -o build/libomnidecide.so
    cd ../..

    bun install                       # or: npm install

## Run

    bun run dev                       # or: npm run dev
    -> http://localhost:3000

First screening:

1. In the folder picker enter `attune-sample-data/candidates`
   (relative paths resolve against the project root, or use the built-in browser)
2. Scan -> confirm the CV / cover-letter role tags -> Start run
3. Explore: ranking, per-candidate dossier cards, position report; exported PDFs
   land in `attune-data/runs/<run-id>/exports/`

Engine-only (scripted / air-gapped operation):

    python3 attune-engine/engine.py \
      --folder attune-sample-data/candidates \
      --profile attune-data/templates/example-senior-data-engineer.json \
      --run-dir /tmp/my-run

## Docker

The multi-stage `Dockerfile` has two buildable targets (plus internal stages
that compile the vendored omnidecide-c kernel and set up the Python base).
Port 3000 is the app default; map it wherever the host is free
(`-p <host-port>:3000`).

### Engine image (QA gate / scripted runs)

    docker build --target engine -t job-attune-engine .

Run it with the repo bind-mounted at /app so code stays outside the image and
rebuilding is never needed to pick up changes. Default command = the full
45-check QA gate:

    docker run --rm -it -v /path/to/this/folder:/app -w /app job-attune-engine

The same image for a plain engine run:

    docker run --rm -v /path/to/this/folder:/app -w /app job-attune-engine \
      python3 attune-engine/engine.py \
      --folder attune-sample-data/candidates \
      --profile attune-data/templates/example-senior-data-engineer.json \
      --run-dir /app/attune-data/runs/cli-run

### Full-stack image (default target)

    docker build -t job-attune-full .
    docker run -d -p 127.0.0.1:3000:3000 job-attune-full
    -> http://127.0.0.1:3000

Baked in with the app: the compiled kernel (built with `-std=c11
-ffp-contract=off`, exposed via `OMNIDECIDE_C_LIB=/opt/attune/libomnidecide.so`),
python3 + reportlab/pypdf, the Next.js standalone bundle, the demo candidates
and the profile templates. Run directories (`attune-data/runs/`) are
machine-local state and are never baked in — persist or inspect them with:

    -v /path/to/this/folder/attune-data/runs:/app/attune-data/runs

Scripted access to the container API must carry the loopback-guard header
(the built-in UI sends it automatically; the middleware also rejects
cross-site browser requests):

    curl -H "X-Attune-Client: cli" http://127.0.0.1:3000/api/template

Windows/Docker Desktop bind-mount style: `-v D:/Projects/job-attune-1.0.0:/app`.

## QA gates

    python3 scripts/check_python_side.py
    # 45-check release gate: static analysis, floors contract, two-pass engine
    # determinism, enrichment fields, PII-redaction probes, bench baselines
    # (C36-C38), 7-PDF export validation. Exit 0 = all green.

    python3 scripts/attune_app/js_check_pipelines.py
    # JS/TS static checks (dead code, circular deps, unresolved imports,
    # duplication, complexity, styling drift); requires the `fallow` CLI
    # (https://fallow.tools). Release rule: 0 red findings.

The demo corpus (6 candidates, 10 PDFs, including an unreadable image-only
scan) is regenerated with `python3 scripts/attune_app/make_samples.py`.

## Regenerate the demo corpus

    python3 scripts/attune_app/make_samples.py
    # rewrites the 6 sample candidate folders under attune-sample-data/candidates/

## Environment variables (all optional)

- `ATTUNE_ROOT` - web-app project-root override (default: the cwd the app starts from)
- `ATTUNE_TEXT_MODE` - kernel text layer: `unicode` (default) or `ascii`
- `ATTUNE_LANGUAGE` - kernel language pack: `und` (default), `en zh hi es ar fr bn pt id ur auto`
- `OMNIDECIDE_C_LIB` - engine override for the compiled C kernel (default: `<repo>/download/omnidecide-c/build/libomnidecide.so`)

## Documentation

- `README.md` - project overview, measured accuracy, quickstart, repository layout
- `docs/ARCHITECTURE.md` - components, run lifecycle, data contracts, security model, diagrams
- `docs/DEVELOPMENT.md` - QA pipelines, regression lock, adding bench corpora, release checklist
- `docs/API.md` - HTTP API reference (all 7 endpoints + middleware auth rules)
- `docs/ENGINE-CLI.md` - engine + reporter CLI reference, aggregation profile keys
- `docs/MARKETING.md` - sales playbook: positioning, statistics, workflows, objection handling
- `bench/README.md` - bench harness protocol and reference results
- `CHANGELOG.md` - version history (v1.0.0 - initial public release)
- `docs/VERIFICATION-1.8.0.md` - kernel-migration verification evidence (historical record)
- `LICENSE` / `NOTICE` - Apache License 2.0, copyright Tamer Osman
- `download/omnidecide-c/README.md` - the C11 decision kernel the engine runs on

## What is NOT in this archive (restorable via build commands)

- `node_modules/`            -> `bun install`
- `.next/`                   -> `bun run build`
- (no database — the unused Prisma scaffold was removed; all data lives on the filesystem)
- `attune-data/runs/`   -> created automatically at runtime
- `download/omnidecide-c/build/libomnidecide.so` -> the one-time build command
  in Setup above (the vendored C sources and their test suite ship in the tree)
