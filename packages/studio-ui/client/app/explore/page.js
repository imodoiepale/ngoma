import Link from "next/link";
import { TEMPLATES, getClient, listClients, listWorkflows, loadCatalog } from "../../lib/studio";
import { loadCapabilities } from "../../lib/capabilities";
import { previewsByKind } from "../../lib/runs";
import { Shell } from "../../components/Shell";
import { CapabilityCard, WorkflowCard, FAMILY } from "../../components/cards";
import ExploreFilter from "../../components/ExploreFilter";

export const dynamic = "force-dynamic";

// Every capability and template, with honest badges. Steps flagged 18+ are hidden unless the
// page is scoped to a workspace that enables them (?ws=<key>).
export default async function Explore({ searchParams }) {
  const q = (await searchParams) || {};
  const wsKey = typeof q.ws === "string" ? q.ws : "";
  const filter = typeof q.status === "string" ? q.status : "";
  const search = typeof q.q === "string" ? q.q.toLowerCase() : "";
  let scope = null;
  if (wsKey) { try { scope = await getClient(wsKey); } catch { scope = null; } }
  const allowAdult = !!scope?.adult;
  const [caps, previews, templates, workspaces, catalog] = await Promise.all([loadCapabilities(), previewsByKind(), listWorkflows(TEMPLATES), listClients(), loadCatalog()]);
  const shown = caps.capabilities.filter((c) => (allowAdult || !c.adult) && (!filter || c.status === filter)
    && (!search || `${c.label} ${c.blurb} ${c.kind} ${c.steps.join(" ")}`.toLowerCase().includes(search)));
  const hrefForUse = (kind) => (scope ? `/w/${scope.id}?use=${kind}` : `/explore/${kind}`);
  const families = Object.entries(FAMILY).filter(([k]) => k !== "adult" || allowAdult)
    .map(([key, label]) => ({ key, label, items: templates.filter((t) => t.family === key && (!search || t.title.toLowerCase().includes(search))) })).filter((f) => f.items.length);

  return (
    <Shell current="/explore" workspace={scope} crumbs={[{ label: "Explore" }]}>
      <section className="page-head">
        <p className="eyebrow">Explore</p>
        <h1>Every step the studio can run, and what it is waiting for.</h1>
        <p className="lede">Ready means port-mapped with its models present. Needs setup names the missing piece. Gap means no backend yet. Estimates come from engine.yaml and say whether they are measured or assumed.</p>
      </section>
      <ExploreFilter counts={caps.counts} status={filter} q={search} ws={wsKey} workspaces={workspaces.map((w) => ({ id: w.id, name: w.name, adult: w.adult }))} />
      {caps.categories.map((cat) => {
        const items = shown.filter((c) => c.category === cat.id);
        if (!items.length) return null;
        return (
          <section key={cat.id} className="row" aria-labelledby={`cat-${cat.id}`}>
            <div className="row-head"><h2 id={`cat-${cat.id}`}>{cat.label}</h2><p>{items.length} step{items.length === 1 ? "" : "s"}</p></div>
            <div className="cards">
              {items.map((c) => <CapabilityCard key={c.kind} cap={c} types={caps.types} preview={previews[c.kind]} hrefForUse={hrefForUse(c.kind)} />)}
            </div>
          </section>
        );
      })}
      {!shown.length && <div className="empty"><b>No step matches.</b>Clear the filter or search for another word.</div>}
      {!allowAdult && caps.capabilities.some((c) => c.adult) && (
        <p className="muted" style={{ marginTop: 24 }}>{caps.capabilities.filter((c) => c.adult).length} step(s) flagged 18+ are hidden. A workspace shows them only when its brand.yaml sets <code>adult: true</code>.</p>
      )}
      <section className="row" aria-labelledby="tpl-h">
        <div className="row-head"><h2 id="tpl-h">Templates as tools</h2><p>{templates.length} pipelines. Open one on the canvas, then use it in a workspace where it becomes editable.</p></div>
        {families.map((f) => (
          <div key={f.key} className="family">
            <h3>{f.label}</h3>
            <div className="cards">
              {f.items.map((w) => <WorkflowCard key={w.id} wf={w} workspace={TEMPLATES} catalog={catalog} href={`/w/${TEMPLATES}/f/${w.id}`} />)}
            </div>
          </div>
        ))}
        {!families.length && <p className="muted">No template matches.</p>}
      </section>
      <p className="muted" style={{ marginTop: 20 }}><Link href="/">Back home</Link></p>
    </Shell>
  );
}
