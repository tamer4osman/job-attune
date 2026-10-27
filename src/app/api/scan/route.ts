import { NextResponse } from "next/server";
import { jsonError, scanFolder } from "@/lib/attune-server";

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const folder = typeof body?.folder === "string" ? body.folder : "";
    if (!folder.trim()) return jsonError("Missing folder path");
    const result = await scanFolder(folder);
    if ("error" in result) return jsonError(result.error, 404);
    return NextResponse.json(result);
  } catch {
    return jsonError("Scan failed", 500);
  }
}
