import { runPython } from "../../../lib/python";
import { RUN_MODES, StudioError, TEMPLATES, workflowDir } from "../../../lib/studio";

const ID = /^[a-z0-9][a-z0-9_-]{0,79}$/;
const STAGE = /^[a-z0-9][a-z0-9_.-]{0,79}$/;

// Runs one stage through packages/engine/cli.py. The runner, not this route,
// decides whether anything is submitted; dry-run never touches a GPU.
export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const { client, workflow, stage, mode, approveAs } = body;
  try {
    if (client === TEMPLATES) throw new StudioError("Templates never run.");
    await workflowDir(client);
    if (!ID.test(workflow || "")) throw new StudioError("That workflow id is not valid.");
    if (!STAGE.test(stage || "")) throw new StudioError("Pick a stage to run.");
    if (mode && !RUN_MODES.includes(mode)) throw new StudioError("Unknown run mode.");
    const args = ["run", "--client", client, "--workflow", workflow, "--stage", stage];
    if (mode) args.push("--mode", mode);
    if (approveAs) args.push("--approve-as", String(approveAs).slice(0, 40));
    const res = await runPython("packages/engine/cli.py", args, { timeout: 3_600_000 });
    if (res.json) return Response.json(res.json, { status: res.ok ? 200 : 400 });
    if (!res.ok) throw new StudioError(res.error || "The stage did not run.", res.timedOut ? 504 : 400);
    throw new StudioError(`The runner did not answer with JSON. Output: ${(res.stdout || "").slice(0, 300)}`, 500);
  } catch (e) {
    const status = e instanceof StudioError ? e.status : 400;
    return Response.json({ error: e.message || "The stage did not run." }, { status });
  }
}
