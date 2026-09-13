import { loadCatalog, runPlan } from "../../../lib/studio";

// Dry check of a workflow as it is on the canvas right now. Never executes anything.
export async function POST(request) {
  const wf = await request.json();
  if (!wf || !Array.isArray(wf.nodes) || !Array.isArray(wf.edges)) {
    return Response.json({ error: "Send the workflow's nodes and links." }, { status: 400 });
  }
  return Response.json(runPlan(wf, await loadCatalog()));
}
