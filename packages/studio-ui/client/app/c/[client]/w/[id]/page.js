import { notFound } from "next/navigation";
import { getClient, loadCatalog, readWorkflow } from "../../../../../lib/studio";
import Canvas from "../../../../../components/Canvas";

export const dynamic = "force-dynamic";

export default async function WorkflowPage({ params }) {
  const { client, id } = await params;
  let info, wf;
  try {
    [info, wf] = await Promise.all([getClient(client), readWorkflow(client, id)]);
  } catch {
    notFound();
  }
  const catalog = await loadCatalog();
  return <Canvas client={info} initial={wf} catalog={catalog} />;
}
