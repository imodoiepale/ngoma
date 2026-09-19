import Link from "next/link";
import { TEMPLATES, listClients, listReferences, listWorkflows, loadCatalog } from "../lib/studio";
import { loadCapabilities } from "../lib/capabilities";
import { recentResults, previewsByKind, spendSummary } from "../lib/runs";
import { fmtUsd } from "../lib/estimate";
import { Shell } from "../components/Shell";
import CreateBar from "../components/CreateBar";
import { CapabilityCard, WorkflowCard, ResultTile, FAMILY } from "../components/cards";

export const dynamic = "force-dynamic";

// Home: describe what you want, open a workspace canvas, or start from what already exists.
// Everything shown comes from brands/ and the catalogue.
export default async function Home() {
  const [workspaces, templates, caps, results, previews, spend, catalog] = await Promise.all([
    listClients(), listWorkflows(TEMPLATES), loadCapabilities(), recentResults(12), previewsByKind(), spendSummary(), loadCatalog(),
  ]);
  const refs = Object.fromEntries(await Promise.all(workspaces.map(async (w) => [w.id, await listReferences(w.id)])));
  const anyAdult = workspaces.some((w) => w.adult);
  const featured = caps.capabilities.filter((c) => !c.adult && c.category !== "inputs" && c.category !== "decide").sort((a, b) => (a.status === b.status ? 0 : a.status === "ready" ? -1 : 1)).slice(0, 8);
  const families = Object.entries(FAMILY).filter(([k]) => k !== "adult" || anyAdult).map(([key, label]) => ({ key, label, items: templates.filter((t) => t.family === key) })).filter((f) => f.items.length);
  const workflowCount = workspaces.reduce((s, w) => s + w.workflows.length, 0);

  return (
    <Shell current="/">
      <section className="hero">
        <div>
          <p className="eyebrow">Node canvas for any brand</p>
          <h1>Describe it, wire it, run it with a cost you can see.</h1>
          <p>Every step is a node with typed ports. Describe what you want and the graph proposes itself; drop fifty references on a step and it runs once per item. Nothing runs live until a person approves the estimate.</p>
        </div>
        <div className="stats" aria-label="Studio at a glance">
          <div className="stat"><b>{workspaces.length}</b><small>workspaces</small></div>
          <div className="stat"><b>{workflowCount}</b><small>workflows</small></div>
          <div className="stat"><b>{caps.counts.ready}</b><small>steps ready of {caps.capabilities.length}</small></div>
          <div className="stat"><b>{fmtUsd(spend.estimated_usd)}</b><small>spent to date <span className="basis basis-assumed">estimated</span></small></div>
        </div>
      </section>

      <CreateBar workspaces={workspaces.map((w) => ({ id: w.id, name: w.name }))} />

      <section className="row" aria-labelledby="ws-h">
        <div className="row-head"><h2 id="ws-h">Workspaces</h2><p>One folder under brands/ per brand. Open one to work on its canvas.</p></div>
        <div className="cards cards-wide">
          {workspaces.map((w) => (
            <Link key={w.id} href={`/w/${w.id}`} className="ws-card" style={{ "--accent": w.accent }}>
              <h3><span className="client-swatch" aria-hidden />{w.name}</h3>
              <span className="muted">{w.tagline || w.kind}</span>
              <span className="swatches" aria-hidden>{w.palette.slice(0, 6).map((p) => <i key={p.key} style={{ background: p.hex }} title={p.key} />)}</span>
              <span className="card-foot">
                <span>{w.workflows.length} workflows</span>
                <span>{refs[w.id].length} reference collections</span>
                {w.adult && <span className="chip chip-consent">18+ enabled</span>}
              </span>
            </Link>
          ))}
          <Link href="/explore" className="ws-card empty" style={{ display: "grid", alignContent: "center" }}>
            <b>Add a workspace</b>
            <span>Create brands/&lt;key&gt;/brand.yaml (see brands/_kit when it lands) and it appears here.</span>
          </Link>
        </div>
      </section>

      <section className="row" aria-labelledby="recent-h">
        <div className="row-head"><h2 id="recent-h">Recent results</h2><p>From run manifests under brands/*/runs. Open one to see the inside of the run.</p><Link href="/batches">All batches</Link></div>
        {results.length ? (
          <div className="cards" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))" }}>
            {results.flatMap((r) => (r.files.length ? r.files.slice(0, 2) : r.items.flatMap((i) => i.files).slice(0, 2)).map((f) => <ResultTile key={`${r.run_id}-${f}`} run={r} file={f} />))}
          </div>
        ) : (
          <div className="empty"><b>No results yet.</b>Runs so far were dry runs, which write a plan and make nothing. Open a workspace canvas, switch the mode to Approve and run a stage to see results here.</div>
        )}
      </section>

      <section className="row" aria-labelledby="caps-h">
        <div className="row-head"><h2 id="caps-h">Capabilities</h2><p>{caps.counts.ready} ready, {caps.counts.needsSetup} need setup, {caps.counts.gap} gaps.</p><Link href="/explore">Explore all</Link></div>
        <div className="cards">
          {featured.map((c) => <CapabilityCard key={c.kind} cap={c} types={caps.types} preview={previews[c.kind]} />)}
        </div>
      </section>

      <section className="row" aria-labelledby="tpl-h">
        <div className="row-head"><h2 id="tpl-h">Templates</h2><p>{templates.length} pipelines, one per business idea. Open one on the canvas, then use it in a workspace.</p></div>
        {families.map((f) => (
          <div key={f.key} className="family">
            <h3>{f.label}</h3>
            <div className="cards">
              {f.items.map((w) => <WorkflowCard key={w.id} wf={w} workspace={TEMPLATES} catalog={catalog} href={`/w/${TEMPLATES}/f/${w.id}`} />)}
            </div>
          </div>
        ))}
      </section>
    </Shell>
  );
}
