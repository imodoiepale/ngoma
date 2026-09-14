import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { REPO, StudioError, TEMPLATES, workflowDir } from "../../../lib/studio";

const run = promisify(execFile);
const ID = /^[a-z0-9][a-z0-9_-]{0,79}$/;

// One utterance to the director. The engine (packages/engine/session.py) parses it, changes
// the brief, rebuilds the workflow and saves both. Arguments are an array, never a shell.
export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const { client, session, workflow } = body;
  const text = String(body.message || "").trim();
  try {
    if (client === TEMPLATES) throw new StudioError("Direct a client's workflow, not a template.");
    await workflowDir(client);
    if (!ID.test(session || "")) throw new StudioError("A session needs a short id.");
    if (workflow && !ID.test(workflow)) throw new StudioError("That workflow id is not valid.");
    if (text.length < 2) throw new StudioError("Say something first.");
    if (text.length > 2000) throw new StudioError("Keep it under 2,000 characters.");
    const args = ["run", "--quiet", "--with", "pyyaml", "python", "packages/engine/cli.py", "say",
      "--client", client, "--session", session, "--text", text, "--json"];
    if (workflow) args.push("--workflow", workflow);
    const { stdout } = await run("uv", args, { cwd: REPO, timeout: 120000, windowsHide: true, maxBuffer: 32 * 1024 * 1024 });
    return Response.json(JSON.parse(stdout));
  } catch (e) {
    const status = e instanceof StudioError ? e.status : 400;
    const detail = (e.stderr || e.message || "").toString().split("\n").filter(Boolean).slice(-2).join(" ");
    return Response.json({ error: detail || "The director did not answer." }, { status });
  }
}
