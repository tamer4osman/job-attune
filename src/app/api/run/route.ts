import { NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";
import { randomBytes } from "crypto";
import { spawn } from "child_process";
import {
  ENGINE,
  RUNS_DIR,
  ensureDirs,
  jsonError,
  resolveFolder,
  resolveRunDir,
} from "@/lib/attune-server";

interface StartBody {
  folder?: string;
  profile?: Record<string, unknown>;
  roleOverrides?: Record<string, string>;
  pseudonymous?: boolean;
}

export async function POST(request: Request) {
  try {
    await ensureDirs();
    const body = (await request.json().catch(() => ({}))) as StartBody;
    // root-relative folder resolution (same contract as /api/scan): keeps the
    // standalone server - which chdir's to its own directory - working with
    // the relative default the UI ships with
    const folder = typeof body.folder === "string" ? resolveFolder(body.folder.trim()) : "";
    if (!folder) return jsonError("Missing folder");
    if (!body.profile || typeof body.profile !== "object") return jsonError("Missing job profile");
    const st = await fs.stat(folder).catch(() => null);
    if (!st || !st.isDirectory()) return jsonError("Main folder not readable", 404);

    // collision-proof run id: mkdir without `recursive` fails with EEXIST when
    // the second-resolution timestamp id is taken (double POST, scripted use)
    const ts = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
    let runId: string | null = null;
    let runDir = "";
    for (let attempt = 0; attempt < 5 && !runId; attempt++) {
      const candidate = attempt === 0 ? `run-${ts}` : `run-${ts}-${randomBytes(2).toString("hex")}`;
      try {
        await fs.mkdir(path.join(RUNS_DIR, candidate));
        runId = candidate;
        runDir = path.join(RUNS_DIR, candidate);
      } catch (e) {
        if ((e as NodeJS.ErrnoException).code !== "EEXIST") throw e;
      }
    }
    if (!runId) return jsonError("Could not allocate a run directory", 500);

    const profileOverrides = (body.profile as { role_overrides?: Record<string, string> }).role_overrides ?? {};
    const profile = {
      ...body.profile,
      pseudonymous: body.pseudonymous !== false,
      // honor the recruiter's file re-tagging: the UI sends overrides nested in
      // the profile; a top-level roleOverrides (API convenience) wins if present.
      // The previous `body.roleOverrides ?? {}` clobbered the nested value with
      // {} on every request, silently discarding manual re-tags.
      role_overrides:
        body.roleOverrides && Object.keys(body.roleOverrides).length > 0
          ? body.roleOverrides
          : profileOverrides,
    };
    const profileJson = JSON.stringify(profile, null, 2);
    if (profileJson.length > 2_000_000) return jsonError("Job profile too large", 413);
    const profilePath = path.join(runDir, "profile.json");
    await fs.writeFile(profilePath, profileJson, "utf-8");
    await fs.writeFile(
      path.join(runDir, "input.json"),
      JSON.stringify({ folder, startedAt: new Date().toISOString() }, null, 2),
      "utf-8",
    );

    // Spawn the deterministic local engine; progress is polled via progress.json.
    const child = spawn(
      "python3",
      [ENGINE, "--folder", folder, "--profile", profilePath, "--run-dir", runDir, "--salt", runId],
      { detached: true, stdio: "ignore", env: { ...process.env, PYTHONUNBUFFERED: "1" } },
    );
    // without this listener a spawn failure (missing python3, bad engine path)
    // becomes an uncaught exception that can take down the server
    child.on("error", (err) => {
      console.error("[attune:run] engine spawn failed:", err);
      const failed = {
        progress: {
          stage: "error",
          pct: 100,
          message: `Run failed: engine could not be started (${err.message})`,
          updated_at: new Date().toISOString(),
        },
      };
      fs.writeFile(path.join(runDir, "progress.json"), JSON.stringify(failed, null, 2), "utf-8").catch(() => {});
    });
    child.unref();

    // runId only: absolute server paths are an internal detail
    return NextResponse.json({ runId });
  } catch {
    // generic message: raw fs errors would leak absolute server paths
    return jsonError("Start failed: could not create the run", 500);
  }
}

export async function GET() {
  try {
    await ensureDirs();
    const ids = (await fs.readdir(RUNS_DIR, { withFileTypes: true }))
      .filter((e) => e.isDirectory())
      .map((e) => e.name)
      .sort()
      .reverse();
    type RunSummary = {
      candidates: number; shortlisted: number; topLabel: string | null;
      profileTitle: string; company: string; reviewItems: number; blocking: number;
    } | null;
    const runs: { runId: string; status: string; pct: number; finishedAt: string | null; summary: RunSummary }[] = [];
    // summaries are cached by results.json mtime: the list endpoint previously
    // parsed up to 25 full results.json files (multi-MB at scale) per request
    const summaryCache = new Map<string, { mtimeMs: number; finishedAt: string | null; summary: RunSummary }>();
    for (const id of ids.slice(0, 25)) {
      const dir = await resolveRunDir(id);
      if (!dir) continue;
      let status = "unknown";
      let pct = 0;
      let finishedAt: string | null = null;
      try {
        const prog = JSON.parse(await fs.readFile(path.join(dir, "progress.json"), "utf-8"));
        status = prog.progress?.stage ?? "unknown";
        pct = prog.progress?.pct ?? 0;
      } catch {
        // no progress yet: the engine writes one early in its boot; leave the
        // defaults so the UI shows a booting run rather than pretending "scan"
      }
      try {
        const resultsPath = path.join(dir, "results.json");
        const stat = await fs.stat(resultsPath);
        const cached = summaryCache.get(id);
        let summary: RunSummary;
        if (cached && cached.mtimeMs === stat.mtimeMs) {
          summary = cached.summary;
        } else {
          const results: Record<string, any> = JSON.parse(await fs.readFile(resultsPath, "utf-8"));
          const stats = results.statistics ?? {};
          summary = {
            candidates: stats.candidates_total ?? 0,
            shortlisted: stats.shortlisted ?? 0,
            topLabel: (results.ranking_labels ?? [])[0] ?? null,
            profileTitle: results.profile?.title ?? "",
            company: results.profile?.company ?? "",
            reviewItems: (results.review_queue ?? []).length,
            blocking: (results.review_queue ?? []).filter((q: { blocking?: boolean }) => q.blocking).length,
          };
          summaryCache.set(id, { mtimeMs: stat.mtimeMs, finishedAt: results.created_at ?? null, summary });
        }
        status = "done";
        pct = 100;
        finishedAt = summaryCache.get(id)?.finishedAt ?? finishedAt;
      } catch (e) {
        // unreadable results.json: log instead of silently showing a stale status
        console.warn("[attune:run] results summary unavailable for", id, e);
      }
      const summaryOut = await Promise.resolve(summaryCache.get(id)?.summary ?? null);
      runs.push({ runId: id, status, pct, finishedAt, summary: summaryOut });
    }
    return NextResponse.json({ runs });
  } catch (e) {
    console.error("[attune:run] list failed:", e);
    return jsonError("List failed", 500);
  }
}
