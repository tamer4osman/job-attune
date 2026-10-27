import { NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";
import { jsonError, PROJECT_ROOT } from "@/lib/attune-server";

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const raw = typeof body?.path === "string" && body.path.trim() ? body.path.trim() : PROJECT_ROOT;
    const target = path.resolve(raw);
    const st = await fs.stat(target).catch(() => null);
    if (!st || !st.isDirectory()) return jsonError("Not a directory", 404);
    const entries = await fs.readdir(target, { withFileTypes: true });
    const dirs = entries
      .filter((e) => e.isDirectory() && !e.name.startsWith("."))
      .map((e) => e.name)
      .sort((a, b) => a.localeCompare(b))
      .slice(0, 400);
    const parent = path.dirname(target);
    return NextResponse.json({
      path: target,
      parent: parent === target ? null : parent,
      directories: dirs.map((name) => ({ name, path: path.join(target, name) })),
    });
  } catch (e) {
    console.warn("[attune:browse] failed:", e);
    return jsonError("Browse failed", 500);
  }
}
