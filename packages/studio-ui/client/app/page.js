import Link from "next/link";
import { TEMPLATES, listClients, listWorkflows, loadCatalog } from "../lib/studio";
import { WorkflowTile } from "../components/WorkflowTile";

export const dynamic = "force-dynamic";

const FAMILY = {
  volume: "Volume content", ugc: "UGC ads", persona: "AI influencer and AI model", music: "Music",
  service: "Productised services", education: "Education and community", saas: "Software", adult: "Fictional 18+ (gated)",
};

export default async function Home() {
  const [clients, templates, catalog] = await Promise.all([listClients(), listWorkflows(TEMPLATES), loadCatalog()]);
  const families = Object.entries(FAMILY)
    .map(([key, label]) => ({ key, label, items: templates.filter((t) => t.family === key) }))
    .filter((f) => f.items.length);

  return (
    <main className="lobby">
      <header className="lobby-head">
        <span className="wordmark">EPALLE Studio</span>
        <nav>
          <Link href="/library">Library</Link>
          <Link href="/jobs">Jobs</Link>
        </nav>
      </header>

      <section className="lobby-intro">
        <h1>Clients</h1>
        <p>Each client has its own workflows. Open one to edit it on the canvas, or start a new one from an idea, a description, or by combining workflows you already have.</p>
      </section>

      {clients.map((c) => (
        <section key={c.id} className="client-row" style={{ "--client": c.accent }}>
          <div className="client-meta">
            <span className="client-swatch" aria-hidden />
            <h2>{c.name}</h2>
            <span className="client-count">{c.workflows.length} workflows</span>
            <Link className="btn btn-quiet" href={`/c/${c.id}`}>Open workspace</Link>
          </div>
          <div className="tile-strip">
            {c.workflows.map((w) => (
              <WorkflowTile key={w.id} href={`/c/${c.id}/w/${w.id}`} wf={w} catalog={catalog} />
            ))}
            <Link className="tile tile-new" href={`/c/${c.id}`}>
              <span>New workflow</span>
              <small>From an idea, a description, or by combining</small>
            </Link>
          </div>
        </section>
      ))}

      <section className="templates">
        <div className="templates-head">
          <h2>Idea templates</h2>
          <p>{templates.length} ready-made pipelines, one for each business idea. Open one to see how it runs, then use it for a client.</p>
        </div>
        {families.map((f) => (
          <div key={f.key} className="family">
            <h3>{f.label}</h3>
            <div className="tile-grid">
              {f.items.map((w) => (
                <WorkflowTile key={w.id} href={`/c/${TEMPLATES}/w/${w.id}`} wf={w} catalog={catalog} compact />
              ))}
            </div>
          </div>
        ))}
      </section>
    </main>
  );
}
