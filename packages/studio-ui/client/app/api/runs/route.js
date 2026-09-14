import fs from "node:fs/promises";
import path from "node:path";
import { REPO, StudioError, workflowDir } from "../../../lib/studio";

const ID = /^[a-z0-9][a-z0-9_-]{0,79}$/;

// Every run manifest the engine wrote for one workflow, newest first.
export async function GET(request) {
  const q = new URL(request.url).searchParams;
  const client = q.get("client") || "", workflow = q.get("workflow") || "";
  try {
    await workflowDir(client);
    if (!ID.test(workflow)) throw new StudioError("That workflow id is not valid.");
    const root = path.join(REPO, "brands", client, "runs", workflow);
    const out = [];
    let nodes = [];
    try { nodes = await fs.readdir(root); } catch { return Response.json({ runs: [] }); }
    for (const node of nodes) {
      let runs = [];
      try { runs = await fs.readdir(path.join(root, node)); } catch { continue; }
      for (const r of runs) {
        try {
          out.push(JSON.parse(await fs.readFile(path.join(root, node, r, "manifest.json"), "utf8")));
        } catch { /* a run without a manifest is not a run */ }
      }
    }
    out.sort((a, b) => String(b.finished || "").localeCompare(String(a.finished || "")));
    return Response.json({ runs: out });
  } catch (e) {
    const status = e instanceof StudioError ? e.status : 400;
    return Response.json({ error: e.message }, { status });
  }
}
