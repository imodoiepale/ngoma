import { StudioError, TEMPLATES, readWorkflow, writeWorkflow } from "../../../../../lib/studio";

function fail(e) {
  const status = e instanceof StudioError ? e.status : 500;
  return Response.json({ error: e.message || "Something went wrong reading the workflow." }, { status });
}

export async function GET(_request, { params }) {
  const { client, id } = await params;
  try {
    return Response.json(await readWorkflow(client, id));
  } catch (e) {
    return fail(e);
  }
}

export async function PUT(request, { params }) {
  const { client, id } = await params;
  if (client === TEMPLATES) {
    return Response.json({ error: "Templates are generated from ideas.yaml. Use it for a client, then edit that copy." }, { status: 403 });
  }
  try {
    const saved = await writeWorkflow(client, id, await request.json());
    return Response.json(saved);
  } catch (e) {
    return fail(e);
  }
}
