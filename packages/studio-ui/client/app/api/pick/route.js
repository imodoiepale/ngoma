import { loadCatalog, readWorkflow, StudioError, TEMPLATES, writeWorkflow } from "../../../lib/studio";

// A person records which candidates survive a pick step. Nothing runs here.
export async function PUT(request) {
  const body = await request.json().catch(() => ({}));
  const { client, workflow, node, picked } = body;
  try {
    if (client === TEMPLATES) throw new StudioError("Templates are read-only.", 403);
    const wf = await readWorkflow(client, workflow);
    const catalog = await loadCatalog();
    const target = wf.nodes.find((n) => n.id === node);
    const spec = target && catalog.nodes.find((n) => n.kind === target.kind);
    if (!spec || spec.category !== "decide") throw new StudioError("That step is not a pick.");
    if (!Array.isArray(picked) || !picked.every((p) => typeof p === "string" && p.length < 200)) throw new StudioError("Send the picked candidate ids.");
    const k = Number(target.data?.params?.k || picked.length);
    if (picked.length > k) throw new StudioError(`This step keeps at most ${k}.`);
    target.data = { ...(target.data || {}), picked };
    const saved = await writeWorkflow(client, workflow, wf);
    return Response.json({ ok: true, node, picked, gaps: saved.gaps });
  } catch (e) {
    const status = e instanceof StudioError ? e.status : 400;
    return Response.json({ error: e.message }, { status });
  }
}
