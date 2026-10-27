import { NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";
import { spawn } from "child_process";
import { REPORTER, jsonError, resolveRunDir } from "@/lib/attune-server";

/** POST: generate PDF exports for a finished run. */
export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const runId = typeof body?.run_id === "string" ? body.run_id : "";
    const dir = await resolveRunDir(runId);
    if (!dir) return jsonError("Unknown run", 404);
    const resultsPath = path.join(dir, "results.json");
    await fs.access(resultsPath);
    const pseudonymous = body?.pseudonymous === false ? "0" : "1";
    const exit = await new Promise<number>((resolve) => {
      const child = spawn("python3", [REPORTER, "--run-dir", dir, "--pseudonymous", pseudonymous], {
        stdio: "ignore",
      });
      // bound the wait: a hung reportlab render must not hang the request forever
      const timer = setTimeout(() => {
        try {
          child.kill("SIGKILL");
        } catch {}
        resolve(124);
      }, 120_000);
      child.on("close", (code) => {
        clearTimeout(timer);
        resolve(code ?? 1);
      });
      child.on("error", (err) => {
        clearTimeout(timer);
        console.error("[attune:report] spawn failed:", err);
        resolve(1);
      });
    });
    if (exit === 124) return jsonError("Report generation timed out", 504);
    if (exit !== 0) return jsonError("Report generation failed", 500);
    const mf = JSON.parse(await fs.readFile(path.join(dir, "exports", "manifest.json"), "utf-8"));
    return NextResponse.json({ ok: true, files: mf.files ?? [] });
  } catch {
    return jsonError("Report export failed", 500);
  }
}

/** GET: stream an exported PDF (file must be listed in the export manifest). */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const runId = searchParams.get("run_id") ?? "";
  const file = searchParams.get("file") ?? "";
  const dir = await resolveRunDir(runId);
  if (!dir) return jsonError("Unknown run", 404);
  if (!/^[A-Za-z0-9._-]+\.pdf$/.test(file)) return jsonError("Bad file name", 400);
  let allowed = false;
  try {
    const mf = JSON.parse(await fs.readFile(path.join(dir, "exports", "manifest.json"), "utf-8"));
    allowed = (mf.files ?? []).some((f: { file?: string }) => f.file === file);
  } catch {}
  if (!allowed) return jsonError("File not in export manifest", 404);
  const buf = await fs.readFile(path.join(dir, "exports", file));
  const label = file === "batch-report.pdf" ? "attune-batch-report" : `attune-${file.replace(/\.pdf$/, "")}`;
  return new NextResponse(new Uint8Array(buf), {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="${runId}-${label}.pdf"`,
    },
  });
}
