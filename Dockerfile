# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Tamer Osman
#
# Job Attune container images (multi-stage, three buildable targets).
#
#   kernel-build (internal) - compiles the vendored OmniDecide C kernel into
#                             libomnidecide.so with the flags the Makefile
#                             always applies (-std=c11 -ffp-contract=off),
#                             which is what keeps results bit-identical
#                             across machines.
#   engine-base  (internal) - python:3.12-slim + the two non-stdlib Python
#                             dependencies (PDF export + QA validation),
#                             with the compiled .so baked in and wired via
#                             OMNIDECIDE_C_LIB.
#
# Targets:
#   engine     - QA/dev image for the Python engine. The repository is
#                bind-mounted at /app at run time, so code changes take
#                effect without rebuilding:
#                  docker build --target engine -t job-attune-engine .
#                  docker run --rm -v D:/Projects/job-attune-1.0.0:/app \
#                    -w /app job-attune-engine          # full QA gate
#
#   fullstack  - production-style image of the whole app (default target):
#                Next.js standalone server + Node 22 runtime + the Python
#                engine, compiled kernel, demo candidates and profile
#                templates. Runs on port 3000 and spawns the engine through
#                the app's own /api/run and /api/report routes:
#                  docker build -t job-attune-full .
#                  docker run --rm -d -p 127.0.0.1:3000:3000 job-attune-full
#                Use -v to persist or inspect run artifacts:
#                  -v D:/Projects/job-attune-1.0.0/attune-data/runs:/app/attune-data/runs

# ---------- Stage 1: compile the C decision kernel ----------
FROM debian:bookworm-slim AS kernel-build
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libc6-dev \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY vendor/omnidecide-c/ .
RUN mkdir -p /out \
 && cc -std=c11 -ffp-contract=off -O2 -Wall -Wextra -pedantic -fPIC -shared \
      -Iinclude -Isrc src/*.c \
      -lm -o /out/libomnidecide.so

# ---------- Stage 2: Python engine base (shared) ----------
FROM python:3.12-slim AS engine-base
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=kernel-build /out/libomnidecide.so /opt/attune/libomnidecide.so
ENV OMNIDECIDE_C_LIB=/opt/attune/libomnidecide.so
ENV PYTHONUNBUFFERED=1

# ---------- Target: engine (QA/runtime image) ----------
# Default command: the full Python-side QA gate (expects the repo at /app).
FROM engine-base AS engine
WORKDIR /app
CMD ["python3", "scripts/check_python_side.py"]

# ---------- Stage 3: build the Next.js UI with Bun ----------
FROM oven/bun:1 AS ui-build
WORKDIR /src
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile
COPY next.config.ts tsconfig.json postcss.config.mjs components.json next-env.d.ts eslint.config.mjs ./
COPY src ./src
COPY public ./public
# package.json "build" = `next build` + static/public copied into .next/standalone
RUN bun run build

# ---------- Target: fullstack (Next.js app + engine + kernel) ----------
FROM engine-base AS fullstack
# Node 22 LTS runtime for the Next.js standalone server (bookworm's apt
# Node is too old for the Next.js engine requirement).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*
ENV NODE_ENV=production
ENV PORT=3000
WORKDIR /app
# Next.js standalone bundle: server.js (+ its vendored node_modules/.next)
COPY --from=ui-build /src/.next/standalone ./
COPY --from=ui-build /src/.next/static ./.next/static
COPY --from=ui-build /src/public ./public
# Python engine and its vendored data floors/calibration files
COPY attune-engine ./attune-engine
# Kernel version header: ckernel.py reads ODK_LIBRARY_VERSION from
# vendor/omnidecide-c/include/omnidecide.h relative to the repo root to
# build the KERNEL_ID recorded in run manifests. Take it from the exact
# kernel-build source tree so the reported version always matches the baked
# library.
COPY --from=kernel-build /src/include ./vendor/omnidecide-c/include
# Demo candidates and profile templates (setup template is attune-data)
COPY attune-sample-data ./attune-sample-data
COPY attune-data/templates ./attune-data/templates
EXPOSE 3000
CMD ["node", "server.js"]
