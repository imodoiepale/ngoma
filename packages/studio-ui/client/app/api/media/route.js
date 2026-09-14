import fs from "node:fs/promises";
import path from "node:path";
import { REPO } from "../../../lib/studio";

const TYPES = { ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
  ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".wav": "audio/wav", ".mp3": "audio/mpeg" };

// Serves files the engine produced or references a client attached, and nothing else:
// only paths under brands/<client>/runs or brands/<client>/references are readable.
export async function GET(request) {
  const rel = new URL(request.url).searchParams.get("path") || "";
  const norm = rel.replace(/\\/g, "/");
  if (!/^brands\/[a-z0-9][a-z0-9_-]*\/(runs|references)\//.test(norm) || norm.includes("..")) {
    return new Response("Not found", { status: 404 });
  }
  const abs = path.resolve(REPO, norm);
  if (!abs.startsWith(path.resolve(REPO, "brands") + path.sep)) return new Response("Not found", { status: 404 });
  try {
    const data = await fs.readFile(abs);
    const type = TYPES[path.extname(abs).toLowerCase()] || "application/octet-stream";
    return new Response(data, { headers: { "Content-Type": type, "Cache-Control": "private, max-age=60" } });
  } catch {
    return new Response("Not found", { status: 404 });
  }
}
