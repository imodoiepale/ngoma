import { runPython } from "../../../lib/python";
import { StudioError, TEMPLATES, workflowDir } from "../../../lib/studio";

const IDEA = /^[A-Z]\d{2}$/;
const REF = /^([A-Z]\d{2}|[a-z0-9][a-z0-9_-]{0,79})$/;
const ID = /^[a-z0-9][a-z0-9_-]{0,79}$/;

// Creates a workflow with packages/strategy/workflow_author.py, the same code the skill uses.
// Arguments go to the process as an array, never through a shell (see lib/python.js).
// Mode `extend` appends steps to a saved workflow through `cli.py describe --workflow`.
export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const { mode, client } = body;
  try {
    if (client === TEMPLATES) throw new StudioError("Create workflows for a client, not in the template library.");
    await workflowDir(client);
    if (mode === "extend") {
      const workflow = String(body.workflow || "");
      const text = String(body.text || body.steps || "").trim();
      if (!ID.test(workflow)) throw new StudioError("Pick the workflow to extend.");
      if (text.length < 2) throw new StudioError("Say what to add, like 'carousel@each slides=10'.");
      const res = await runPython("packages/engine/cli.py",
        ["describe", "--client", client, "--workflow", workflow, "--text", text.slice(0, 2000), "--json"]);
      if (res.json && res.json.error) return Response.json(res.json, { status: res.json.refused ? 422 : 400 });
      if (!res.ok || !res.json) throw new StudioError(res.error || "The engine did not answer.", 500);
      return Response.json({ id: res.json.id, added: res.json.added, plan: res.json.plan, reply: res.json.reply, log: res.json.reply });
    }
    const args = ["--client", client];
    if (mode === "idea") {
      if (!IDEA.test(body.idea || "")) throw new StudioError("Pick an idea from the list.");
      args.push("--idea", body.idea);
    } else if (mode === "brief") {
      const brief = String(body.brief || "").trim();
      if (brief.length < 8) throw new StudioError("Describe what to make in at least a few words.");
      if (brief.length > 1000) throw new StudioError("Keep the description under 1,000 characters.");
      args.push("--brief", brief);
    } else if (mode === "combine") {
      const refs = Array.isArray(body.refs) ? body.refs : [];
      if (refs.length < 2 || refs.length > 6 || !refs.every((r) => REF.test(r))) {
        throw new StudioError("Choose between two and six workflows to combine, in order.");
      }
      args.push("--combine", ...refs);
    } else {
      throw new StudioError("Choose how to create the workflow.");
    }
    const title = String(body.title || "").trim();
    if (title) args.push("--title", title.slice(0, 120));

    const res = await runPython("packages/strategy/workflow_author.py", args, { timeout: 120000 });
    if (!res.ok) throw new StudioError(res.error || "Could not create the workflow.", res.timedOut ? 504 : 400);
    const match = res.stdout.match(/workflows[\\/]([a-z0-9][a-z0-9_-]*)\.studio\.json/);
    if (!match) throw new StudioError(`The author did not report a saved workflow. Output: ${res.stdout.slice(0, 300)}`, 500);
    return Response.json({ id: match[1], log: res.stdout });
  } catch (e) {
    const status = e instanceof StudioError ? e.status : 400;
    return Response.json({ error: e.message || "Could not create the workflow." }, { status });
  }
}
