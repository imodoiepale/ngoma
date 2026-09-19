import fs from "node:fs/promises";
import path from "node:path";
import { StudioError } from "../../../../lib/studio";
import { MEDIA_EXT, checkName, collectionDir, refRoot } from "../../../../lib/references";

export const dynamic = "force-dynamic";

const TYPES = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".mp4": "video/mp4", ".mov": "video/quicktime" };

// GET ?ws=<workspace>&name=<collection>&file=<basename>: one media file from a collection.
// The file must be a plain basename inside that folder; anything else is refused.
export async function GET(request) {
  const q = new URL(request.url).searchParams;
  try {
    const ws = q.get("ws") || "";
    await refRoot(ws);
    const dir = collectionDir(ws, checkName(q.get("name") || ""));
    const file = q.get("file") || "";
    if (!file || file !== path.basename(file) || file.includes("..") || !MEDIA_EXT.has(path.extname(file).toLowerCase())) throw new StudioError("That file is not a media file in the collection.");
    const full = path.join(dir, file);
    const data = await fs.readFile(full).catch(() => { throw new StudioError("No such file.", 404); });
    return new Response(data, { headers: { "Content-Type": TYPES[path.extname(file).toLowerCase()] || "application/octet-stream", "Cache-Control": "private, max-age=300" } });
  } catch (e) {
    const status = e instanceof StudioError ? e.status : 400;
    return Response.json({ error: e.message }, { status });
  }
}
