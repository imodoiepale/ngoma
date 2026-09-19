import { StudioError, workflowDir } from "../../../lib/studio";
import { listRuns } from "../../../lib/runs";

const ID = /^[a-z0-9][a-z0-9_-]{0,79}$/;

// Every run manifest the engine wrote, newest first, normalised (files repo-relative, items[]
// summarised). Scope with ?client=<workspace> and optionally &workflow=<id>.
export async function GET(request) {
  const q = new URL(request.url).searchParams;
  const client = q.get("client") || "", workflow = q.get("workflow") || "";
  try {
    if (client) await workflowDir(client);
    if (workflow && !ID.test(workflow)) throw new StudioError("That workflow id is not valid.");
    const runs = await listRuns({ workspace: client || undefined, workflow: workflow || undefined });
    return Response.json({ runs });
  } catch (e) {
    const status = e instanceof StudioError ? e.status : 400;
    return Response.json({ error: e.message }, { status });
  }
}
