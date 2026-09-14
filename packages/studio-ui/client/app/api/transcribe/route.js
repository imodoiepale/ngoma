import { execFile } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { REPO } from "../../../lib/studio";

const run = promisify(execFile);

// A recorded clip becomes text through the studio's local whisper (packages/voice/transcribe.py).
// The audio never leaves this machine and is deleted after transcription.
export async function POST(request) {
  const form = await request.formData().catch(() => null);
  const file = form?.get("audio");
  if (!file || typeof file.arrayBuffer !== "function") return Response.json({ error: "Send an audio clip." }, { status: 400 });
  const tmp = path.join(os.tmpdir(), `director-${Date.now()}.webm`);
  try {
    await fs.writeFile(tmp, Buffer.from(await file.arrayBuffer()));
    const { stdout } = await run("uv", ["run", "--quiet", "--with", "pyyaml", "python", "packages/voice/transcribe.py", tmp, "--json"],
      { cwd: REPO, timeout: 180000, windowsHide: true });
    const data = JSON.parse(stdout);
    return Response.json({ transcript: data.transcript || "", language: data.language_detected || null });
  } catch (e) {
    const detail = (e.stderr || e.message || "").toString().split("\n").filter(Boolean).slice(-2).join(" ");
    return Response.json({ error: detail || "Could not transcribe." }, { status: 500 });
  } finally {
    await fs.rm(tmp, { force: true });
  }
}
