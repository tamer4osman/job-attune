import { NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";
import { jsonError, resolveRunIdFromRequest } from "@/lib/attune-server";

/** How long a run may stay without any progress.json before we call it failed. */
const STALE_AFTER_MS = 120_000;

export async function GET(request: Request) {
  const resolved = await resolveRunIdFromRequest(request);
  if (!resolved) return jsonError("Unknown run", 404);
  const { runId, dir } = resolved;
  try {
    const prog = JSON.parse(await fs.readFile(path.join(dir, "progress.json"), "utf-8"));
    return NextResponse.json({ runId, ...prog.progress });
  } catch {
    // no progress yet: distinguish a booting engine from a dead one via the
    // age of input.json (written right before spawn)
    const st = await fs.stat(path.join(dir, "input.json")).catch(() => null);
    if (st && Date.now() - st.mtimeMs > STALE_AFTER_MS) {
      return NextResponse.json({
        runId,
        stage: "error",
        pct: 100,
        message: "Engine did not report progress - the run failed or stalled before starting.",
      });
    }
    return NextResponse.json({ runId, stage: "starting", pct: 1, message: "Engine starting..." });
  }
}
