import { notFound } from "next/navigation";
import { TEMPLATES, getClient, listClients, loadCatalog, readWorkflow } from "../../../../../lib/studio";
import { listCollections } from "../../../../../lib/references";
import { loadPricing } from "../../../../../lib/pricing";
import { loadCapabilities, readinessByKind } from "../../../../../lib/capabilities";
import { listRuns } from "../../../../../lib/runs";
import Canvas from "../../../../../components/Canvas";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }) {
  const { ws, id } = await params;
  try {
    const wf = await readWorkflow(ws, id);
    return { title: `${wf.title} | Director` };
  } catch {
    return { title: "Director" };
  }
}

// The canvas: the workspace's workflow as nodes, with what each step made, what it costs and
// whether it can run. Everything on it comes from files under brands/ and the catalogue.
export default async function WorkflowPage({ params, searchParams }) {
  const { ws, id } = await params;
  const q = (await searchParams) || {};
  let info, wf;
  try {
    [info, wf] = await Promise.all([getClient(ws), readWorkflow(ws, id)]);
  } catch {
    notFound();
  }
  const [catalog, pricing, caps, runs, refs, workspaces] = await Promise.all([
    loadCatalog(), loadPricing(), loadCapabilities(),
    ws === TEMPLATES ? [] : listRuns({ workspace: ws, workflow: id }),
    ws === TEMPLATES ? [] : listCollections(ws),
    ws === TEMPLATES ? listClients() : [],
  ]);
  return (
    <Canvas
      client={info}
      initial={wf}
      catalog={catalog}
      pricing={pricing}
      readiness={readinessByKind(caps)}
      runs={runs}
      references={refs}
      workspaces={workspaces.map((w) => ({ id: w.id, name: w.name }))}
      query={{ use: typeof q.use === "string" ? q.use : undefined, describe: typeof q.describe === "string" ? q.describe : undefined, node: typeof q.node === "string" ? q.node : undefined, continue: typeof q.continue === "string" ? q.continue : undefined }}
    />
  );
}
