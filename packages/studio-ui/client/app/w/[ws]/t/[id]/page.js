import Link from "next/link";
import { notFound } from "next/navigation";
import { TEMPLATES, computeGaps, getClient, listReferences, loadCatalog, readWorkflow, toolInputs } from "../../../../../lib/studio";
import { loadPricing } from "../../../../../lib/pricing";
import { loadCapabilities, readinessByKind } from "../../../../../lib/capabilities";
import { estimateWorkflow } from "../../../../../lib/estimate";
import ToolForm from "../../../../../components/ToolForm";
import { Shell } from "../../../../../components/Shell";

export const dynamic = "force-dynamic";

// A workflow as a tool: only the inputs, the cost, and Run. Weavy's "convert to tool".
export default async function ToolPage({ params }) {
  const { ws, id } = await params;
  if (ws === TEMPLATES) notFound();
  let info, wf;
  try {
    [info, wf] = await Promise.all([getClient(ws), readWorkflow(ws, id)]);
  } catch {
    notFound();
  }
  const [catalog, pricing, caps, refs] = await Promise.all([loadCatalog(), loadPricing(), loadCapabilities(), listReferences(ws)]);
  const readiness = readinessByKind(caps);
  const refCounts = {};
  for (const r of refs) { refCounts[r.folder] = r.count; refCounts[r.name] = r.count; }
  const all = toolInputs(wf, catalog);
  const chosen = wf.tool?.inputs?.length ? all.filter((i) => wf.tool.inputs.some((t) => t.node === i.node && t.key === i.key)) : all;
  const byKind = Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
  const nodeReadiness = wf.nodes.map((n) => ({ id: n.id, label: byKind[n.kind]?.label || n.kind, status: readiness[n.kind]?.status || "ready" }));

  return (
    <Shell workspace={info} crumbs={[{ href: `/w/${ws}`, label: info.name }, { label: wf.tool?.title || wf.title }]}>
      <section className="page-head">
        <p className="eyebrow">Tool</p>
        <h1>{wf.tool?.title || wf.title}</h1>
        <p className="lede">{wf.nodes.length} steps behind {chosen.length} field{chosen.length === 1 ? "" : "s"}. Fill them in, save, and dry-run. Nothing runs live from here without the approval gate.</p>
      </section>
      <div className="tool-layout">
        <ToolForm workspace={ws} workflow={{ id: wf.id, title: wf.title }} inputs={chosen} estimate={estimateWorkflow(wf, catalog, pricing, refCounts)} consent={!!wf.consent_required} gaps={computeGaps(wf, catalog)} readiness={nodeReadiness} />
        <aside className="tool-side">
          <h3>Inside</h3>
          <ol className="steps-list">
            {wf.nodes.map((n) => (
              <li key={n.id}>
                <span className="lib-dot" style={{ background: catalog.types[byKind[n.kind]?.outputs?.[0]?.type]?.color || "var(--muted)" }} />
                <span>{byKind[n.kind]?.label || n.kind}{n.data?.each ? <em> each</em> : null}</span>
                <span className={`chip chip-${readiness[n.kind]?.status || "ready"}`}>{{ ready: "Ready", "needs-setup": "Setup", gap: "Gap" }[readiness[n.kind]?.status || "ready"]}</span>
              </li>
            ))}
          </ol>
          <Link className="btn btn-quiet" href={`/w/${ws}/f/${id}`}>Open on canvas</Link>
        </aside>
      </div>
    </Shell>
  );
}
