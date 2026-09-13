import Link from "next/link";
import { notFound } from "next/navigation";
import { TEMPLATES, getClient, listWorkflows, loadCatalog } from "../../../lib/studio";
import { WorkflowTile } from "../../../components/WorkflowTile";
import ClientWorkspace from "../../../components/ClientWorkspace";

export const dynamic = "force-dynamic";

export default async function ClientPage({ params }) {
  const { client } = await params;
  let info;
  try {
    info = await getClient(client);
  } catch {
    notFound();
  }
  const [workflows, templates, catalog] = await Promise.all([
    listWorkflows(client), listWorkflows(TEMPLATES), loadCatalog(),
  ]);

  return (
    <main className="lobby" style={{ "--client": info.accent }}>
      <header className="lobby-head">
        <Link href="/" className="wordmark">EPALLE Studio</Link>
        <nav>
          <Link href="/">All clients</Link>
        </nav>
      </header>

      <section className="lobby-intro">
        <h1><span className="client-swatch" aria-hidden /> {info.name}</h1>
        <p>{workflows.length} workflows. Start a new one below, or open one to edit it.</p>
      </section>

      {!info.templates && (
        <ClientWorkspace
          client={client}
          ideas={templates.map((t) => ({ id: t.source?.idea, title: t.title, family: t.family })).filter((t) => t.id)}
          workflows={workflows.map((w) => ({ id: w.id, title: w.title }))}
        />
      )}

      <section className="client-row">
        <div className="tile-grid">
          {workflows.map((w) => (
            <WorkflowTile key={w.id} href={`/c/${client}/w/${w.id}`} wf={w} catalog={catalog} />
          ))}
        </div>
      </section>
    </main>
  );
}
