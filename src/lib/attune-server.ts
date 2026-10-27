import { NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";
import type { Dirent } from "fs";
import type { ScanCandidate, ScanFile, ScanResult } from "./attune";

/**
 * Project root: ATTUNE_ROOT override, else the working directory the app
 * is started from (the repo root for both `next dev` and the standalone start
 * script). All server-side paths derive from this so the tree is relocatable.
 */
export const PROJECT_ROOT = process.env.ATTUNE_ROOT ?? process.cwd();
export const DATA_ROOT = path.join(PROJECT_ROOT, "attune-data");
export const RUNS_DIR = path.join(DATA_ROOT, "runs");
export const TEMPLATES_DIR = path.join(DATA_ROOT, "templates");
export const ENGINE = path.join(PROJECT_ROOT, "attune-engine", "engine.py");
export const REPORTER = path.join(PROJECT_ROOT, "attune-engine", "make_report.py");

const CV_ALIASES = ["resume", "cv", "lebenslauf", "curriculumvitae", "curriculum", "vitae"];
const COVER_ALIASES = ["cover", "coverletter", "letter", "motivation", "motivationsschreiben", "anschreiben"];

export function foldName(text: string): string {
  return text
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
}

/** Classification parity with the Python engine (same alias sets, same order). */
export function classifyRole(stem: string): "cv" | "cover" | "unclassified" {
  const s = foldName(stem);
  if (CV_ALIASES.includes(s)) return "cv";
  if (COVER_ALIASES.includes(s)) return "cover";
  const covers = [...COVER_ALIASES].sort((a, b) => b.length - a.length);
  const cvs = [...CV_ALIASES].sort((a, b) => b.length - a.length);
  if (covers.some((a) => s.includes(a))) return "cover";
  if (cvs.some((a) => s.includes(a))) return "cv";
  return "unclassified";
}

export async function ensureDirs() {
  await fs.mkdir(RUNS_DIR, { recursive: true });
  await fs.mkdir(TEMPLATES_DIR, { recursive: true });
}

export function jsonError(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status });
}

/** Run ids: run-<14-digit timestamp> with an optional collision suffix. */
const RUN_ID_RE = /^run-\d{14}(-[0-9a-f]{4,})?$/;

/** Resolve a run dir safely (no traversal outside RUNS_DIR, no symlinks). */
export async function resolveRunDir(runId: string): Promise<string | null> {
  if (!RUN_ID_RE.test(runId)) return null;
  const runsRoot = path.resolve(RUNS_DIR);
  const resolved = path.resolve(path.join(runsRoot, runId));
  // sep-safe containment: also rejects sibling dirs like "runs-evil"
  if (resolved !== runsRoot && !resolved.startsWith(runsRoot + path.sep)) return null;
  try {
    const rootReal = await fs.realpath(runsRoot);
    const real = await fs.realpath(resolved);
    // symlink escape guard: the real path must stay inside the real runs root
    if (real !== rootReal && !real.startsWith(rootReal + path.sep)) return null;
    const st = await fs.stat(real);
    if (!st.isDirectory()) return null;
    return real;
  } catch {
    return null;
  }
}

/** Shared GET preamble: parse run_id from the query string and resolve its run dir. */
export async function resolveRunIdFromRequest(
  request: Request,
): Promise<{ runId: string; dir: string } | null> {
  const { searchParams } = new URL(request.url);
  const runId = searchParams.get("run_id") ?? "";
  const dir = await resolveRunDir(runId);
  return dir ? { runId, dir } : null;
}

// Scan types come from ./attune (single source of truth, imported type-only above).

/** Resolve a recruiter-supplied folder path against the project root.
 * Absolute paths pass through unchanged; relative paths resolve against
 * PROJECT_ROOT (documented behavior) so the app behaves identically under
 * `next dev` and the standalone production server (which chdir's internally). */
export function resolveFolder(folder: string): string {
  return path.resolve(PROJECT_ROOT, folder);
}

export async function scanFolder(folder: string): Promise<ScanResult | { error: string }> {
  const root = resolveFolder(folder);
  let entries: Dirent[];
  try {
    entries = await fs.readdir(root, { withFileTypes: true });
  } catch {
    return { error: "Folder is not readable. Please check the path." };
  }
  const candidates: ScanCandidate[] = [];
  const notes: (string | { folder: string; note: string })[] = [];
  const subs = entries.filter((e) => e.isDirectory()).map((e) => e.name).sort();
  for (const sub of subs) {
    const subPath = path.join(root, sub);
    let pdfs: string[] = [];
    try {
      pdfs = (await fs.readdir(subPath)).filter((f) => f.toLowerCase().endsWith(".pdf")).sort();
    } catch (e) {
      console.warn("[attune:scan] sub-folder not readable:", sub, e);
      notes.push({ folder: sub, note: "sub-folder not readable" });
      continue;
    }
    if (pdfs.length === 0) {
      notes.push(`"${sub}" contains no PDF files - candidate will be skipped`);
      continue;
    }
    const files: ScanFile[] = [];
    const roles: string[] = [];
    for (const name of pdfs) {
      let role = classifyRole(name.replace(/\.pdf$/i, ""));
      if (role === "unclassified" && pdfs.length === 1 && roles.length === 0) role = "cv";
      if (role === "unclassified") role = roles.includes("cv") ? "cover" : "cv";
      roles.push(role);
      let sizeBytes = 0;
      try {
        sizeBytes = (await fs.stat(path.join(subPath, name))).size;
      } catch {}
      files.push({ name, relPath: `${sub}/${name}`, role: role as ScanFile["role"], sizeBytes });
    }
    if (!roles.includes("cv")) {
      notes.push(`"${sub}": no file classified as CV - candidate will be flagged for review`);
    }
    candidates.push({ folder: sub, files, hasCv: roles.includes("cv"), hasCover: roles.includes("cover") });
  }
  return { folder: root, candidates, notes };
}
