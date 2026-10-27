import { NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";
import { TEMPLATES_DIR, ensureDirs, jsonError } from "@/lib/attune-server";

function safeName(name: string): string | null {
  return /^[A-Za-z0-9][A-Za-z0-9 _-]{0,60}$/.test(name) ? name : null;
}

/** GET: list templates, or load one via ?name= */
export async function GET(request: Request) {
  await ensureDirs();
  const { searchParams } = new URL(request.url);
  const name = searchParams.get("name");
  if (name) {
    const safe = safeName(name);
    if (!safe) return jsonError("Invalid template name", 400);
    try {
      const profile = JSON.parse(await fs.readFile(path.join(TEMPLATES_DIR, `${safe}.json`), "utf-8"));
      return NextResponse.json({ name: safe, profile });
    } catch {
      return jsonError("Template not found", 404);
    }
  }
  const entries = await fs.readdir(TEMPLATES_DIR).catch(() => []);
  const templates: { name: string; title: string }[] = [];
  for (const f of entries.filter((e) => e.endsWith(".json")).sort()) {
    try {
      const profile = JSON.parse(await fs.readFile(path.join(TEMPLATES_DIR, f), "utf-8"));
      templates.push({
        name: f.replace(/\.json$/, ""),
        title: profile?.profile_name ?? profile?.job?.title ?? f,
      });
    } catch {}
  }
  return NextResponse.json({ templates });
}

/** POST: { action: "save" | "delete", name, profile } */
export async function POST(request: Request) {
  await ensureDirs();
  const body = await request.json().catch(() => ({}));
  const action = body?.action;
  const name = typeof body?.name === "string" ? body.name : "";
  const safe = safeName(name);
  if (!safe) return jsonError("Invalid template name (letters, numbers, spaces, - and _ only)");
  const file = path.join(TEMPLATES_DIR, `${safe}.json`);
  if (action === "save") {
    if (!body?.profile || typeof body.profile !== "object") return jsonError("Missing profile");
    const profileJson = JSON.stringify(body.profile, null, 2);
    if (profileJson.length > 2_000_000) return jsonError("Profile too large", 413);
    await fs.writeFile(file, profileJson, "utf-8");
    return NextResponse.json({ ok: true, name: safe });
  }
  if (action === "delete") {
    try {
      await fs.unlink(file);
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code === "ENOENT") {
        return NextResponse.json({ ok: true }); // already gone
      }
      console.warn("[attune:template] delete failed:", e);
      return jsonError("Delete failed", 500);
    }
    return NextResponse.json({ ok: true });
  }
  return jsonError("Unknown action");
}
