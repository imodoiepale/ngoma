import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { REPO, StudioError, TEMPLATES, workflowDir } from "../../../lib/studio";

const run = promisify(execFile);
const IDEA = /^[A-Z]\d{2}$/;
const REF = /^([A-Z]\d{2}|[a-z0-9][a-z0-9_-]{0,79})$/;

// Creates a workflow with packages/strategy/workflow_author.py, the same code the skill uses.
// Arguments go to the process as an array, never through a shell.
export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const { mode, client } = body;
  try {
    if (client === TEMPLATES) throw new StudioError("Create workflows for a client, not in the template library.");
    await workflowDir(client);
    const args = ["run", "--quiet", "--with", "pyyaml", "python", "packages/strategy/workflow_author.py", "--client", client];
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

    const { stdout } = await run("uv", args, { cwd: REPO, timeout: 120000, windowsHide: true });
    const match = stdout.match(/workflows[\\/]([a-z0-9][a-z0-9_-]*)\.studio\.json/);
    if (!match) throw new StudioError(`The author did not report a saved workflow. Output: ${stdout.slice(0, 300)}`, 500);
    return Response.json({ id: match[1], log: stdout });
  } catch (e) {
    const status = e instanceof StudioError ? e.status : 400;
    const detail = (e.stderr || e.message || "").toString().split("\n").filter(Boolean).slice(-2).join(" ");
    return Response.json({ error: detail || "Could not create the workflow." }, { status });
  }
}
