import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { REPO } from "../../../../lib/studio";

const run = promisify(execFile);

// A short-lived ElevenLabs session URL for the voice director. The API key stays in the
// vault on this machine (packages/voice/elevenlabs_agent.py reads it); the browser only
// ever sees the signed URL.
export async function GET() {
  try {
    const { stdout } = await run("uv", ["run", "--quiet", "--with", "pyyaml", "python", "packages/voice/elevenlabs_agent.py", "signed-url"],
      { cwd: REPO, timeout: 60000, windowsHide: true });
    const { signed_url: signedUrl } = JSON.parse(stdout);
    return Response.json({ signedUrl }, { headers: { "Cache-Control": "no-store" } });
  } catch (e) {
    const detail = (e.stderr || e.message || "").toString().split("\n").filter(Boolean).slice(-1).join(" ");
    return Response.json({ error: detail || "The voice agent is not set up." }, { status: 503 });
  }
}
