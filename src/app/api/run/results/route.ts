import { NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";
import { jsonError, resolveRunIdFromRequest } from "@/lib/attune-server";

export async function GET(request: Request) {
  const resolved = await resolveRunIdFromRequest(request);
  if (!resolved) return jsonError("Unknown run", 404);
  const { dir } = resolved;
  try {
    const results = JSON.parse(await fs.readFile(path.join(dir, "results.json"), "utf-8"));
    let decisions: unknown[] = [];
    try {
      const raw = await fs.readFile(path.join(dir, "review_decisions.jsonl"), "utf-8");
      decisions = raw.split("\n").filter(Boolean).map((line) => JSON.parse(line));
    } catch {}
    let exports: { kind: string; ref: string | null; file: string; sha256: string }[] = [];
    try {
      const mf = JSON.parse(await fs.readFile(path.join(dir, "exports", "manifest.json"), "utf-8"));
      exports = mf.files ?? [];
    } catch {}
    return NextResponse.json({ results, decisions, exports });
  } catch (e) {
    console.warn("[attune:results] not ready:", e);
    return jsonError("Results not ready", 404);
  }
}
