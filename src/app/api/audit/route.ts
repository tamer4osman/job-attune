import { NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";
import { jsonError, resolveRunDir } from "@/lib/attune-server";

/** GET: review decisions (sign-offs + escalation resolutions) for a run. */
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const dir = await resolveRunDir(searchParams.get("run_id") ?? "");
  if (!dir) return jsonError("Unknown run", 404);
  try {
    const raw = await fs.readFile(path.join(dir, "review_decisions.jsonl"), "utf-8");
    const decisions = raw.split("\n").filter(Boolean).map((l) => JSON.parse(l));
    return NextResponse.json({ decisions });
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "ENOENT") {
      console.warn("[attune:audit] decisions unreadable:", e);
    }
    // ENOENT = no decisions recorded yet
    return NextResponse.json({ decisions: [] });
  }
}

function cap(value: unknown, max: number): string | null {
  return typeof value === "string" && value.trim() ? value.trim().slice(0, max) : null;
}

/** POST: append an auditable human decision to review_decisions.jsonl. */
export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const dir = await resolveRunDir(typeof body?.run_id === "string" ? body.run_id : "");
  if (!dir) return jsonError("Unknown run", 404);
  // every free-text field is capped: the JSONL is immutable, so oversized or
  // abusive payloads must not bloat the audit trail
  const entry = {
    at: new Date().toISOString(),
    action: body?.action === "signoff" ? "signoff" : "resolve",
    candidate_ref: cap(body?.candidate_ref, 64),
    kind: cap(body?.kind, 64),
    decision: cap(body?.decision, 32),
    reviewer: cap(body?.reviewer, 80) ?? "anonymous",
    note: typeof body?.note === "string" ? body.note.slice(0, 500) : "",
  };
  try {
    await fs.appendFile(path.join(dir, "review_decisions.jsonl"), JSON.stringify(entry) + "\n", "utf-8");
  } catch (e) {
    console.error("[attune:audit] append failed:", e);
    return jsonError("Could not record the decision", 500);
  }
  return NextResponse.json({ ok: true, entry });
}
