import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { REPO, RUN_MODES, StudioError, TEMPLATES, workflowDir } from "../../../lib/studio";

const run = promisify(execFile);
const ID = /^[a-z0-9][a-z0-9_-]{0,79}$/;
const STAGE = /^[a-z0-9][a-z0-9_.-]{0,79}$/;

// Runs one stage through packages/engine/runner.py under the workflow's mode. The runner,
// not this route, decides whether anything is submitted; dry-run never touches a GPU.
export async function POST(request) {
  const body = await request.json().catch(() => ({}));
  const { client, workflow, stage, mode, approveAs } = body;
  try {
    if (client === TEMPLATES) throw new StudioError("Templates never run.");
    await workflowDir(client);
    if (!ID.test(workflow || "")) throw new StudioError("That workflow id is not valid.");
    if (!STAGE.test(stage || "")) throw new StudioError("Pick a stage to run.");
    if (mode && !RUN_MODES.includes(mode)) throw new StudioError("Unknown run mode.");
    const args = ["run", "--quiet", "--with", "pyyaml", "python", "packages/engine/cli.py", "run",
      "--client", client, "--workflow", workflow, "--stage", stage];
    if (mode) args.push("--mode", mode);
    if (approveAs) args.push("--approve-as", String(approveAs).slice(0, 40));
    const { stdout } = await run("uv", args, { cwd: REPO, timeout: 3_600_000, windowsHide: true, maxBuffer: 32 * 1024 * 1024 }).catch((e) => {
      if (e.stdout) return { stdout: e.stdout };
      throw e;
    });
    return Response.json(JSON.parse(stdout));
  } catch (e) {
    const status = e instanceof StudioError ? e.status : 400;
    const detail = (e.stderr || e.message || "").toString().split("\n").filter(Boolean).slice(-2).join(" ");
    return Response.json({ error: detail || "The stage did not run." }, { status });
  }
}
