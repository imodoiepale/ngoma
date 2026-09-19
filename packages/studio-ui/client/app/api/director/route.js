import { runPython } from "../../../lib/python";
import { StudioError, TEMPLATES, workflowDir } from "../../../lib/studio";

const ID = /^[a-z0-9][a-z0-9_-]{0,79}$/;

// One utterance to the director. The engine (packages/engine/session.py) parses it, changes
// the brief, rebuilds the workflow and saves both. Arguments are an array, never a shell,
// and the interpreter is `python` (or STUDIO_PYTHON), see lib/python.js.
export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const { client, session, workflow } = body;
  const text = String(body.message || body.text || "").trim();
  try {
    if (client === TEMPLATES) throw new StudioError("Direct a client's workflow, not a template.");
    await workflowDir(client);
    if (!ID.test(session || "")) throw new StudioError("A session needs a short id.");
    if (workflow && !ID.test(workflow)) throw new StudioError("That workflow id is not valid.");
    if (text.length < 2) throw new StudioError("Say something first.");
    if (text.length > 2000) throw new StudioError("Keep it under 2,000 characters.");
    const args = ["say", "--client", client, "--session", session, "--text", text, "--json"];
    if (workflow) args.push("--workflow", workflow);
    const res = await runPython("packages/engine/cli.py", args, { timeout: 120000 });
    if (!res.ok) throw new StudioError(res.error || "The director did not answer.", res.timedOut ? 504 : 400);
    if (!res.json) throw new StudioError(`The director did not answer with JSON. Output: ${res.stdout.slice(0, 300)}`, 500);
    return Response.json(res.json);
  } catch (e) {
    const status = e instanceof StudioError ? e.status : 400;
    return Response.json({ error: e.message || "The director did not answer." }, { status });
  }
}
