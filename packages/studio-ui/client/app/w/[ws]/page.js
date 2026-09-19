import Link from "next/link";
import { notFound } from "next/navigation";
import { TEMPLATES, getClient, listWorkflows, loadCatalog } from "../../../lib/studio";
import { listCollections } from "../../../lib/references";
import ReferencesPanel from "../../../components/refs/ReferencesPanel";
import { loadCapabilities } from "../../../lib/capabilities";
import { listBatches, listRuns, mediaUrl } from "../../../lib/runs";
import { Shell } from "../../../components/Shell";
import ClientWorkspace from "../../../components/ClientWorkspace";
import CreateBar from "../../../components/CreateBar";
import { WorkflowCard, ResultTile, READY_LABEL } from "../../../components/cards";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }) {
  const { ws } = await params;
  try { return { title: `${(await getClient(ws)).name} | Director` }; } catch { return { title: "Director" }; }
}

// A workspace: its canvases first, then what they made, its characters and references with
// their rights, and its kit as read from brand.yaml. The canvas is where work happens; this
// page is the door.
export default async function WorkspacePage({ params, searchParams }) {
  const { ws } = await params;
  const q = (await searchParams) || {};
  if (ws === TEMPLATES) notFound();
  let info;
  try { info = await getClient(ws); } catch { notFound(); }
  const [workflows, templates, catalog, caps, refs, runs, batches] = await Promise.all([
    listWorkflows(ws), listWorkflows(TEMPLATES), loadCatalog(), loadCapabilities(), listCollections(ws), listRuns({ workspace: ws }), listBatches({ workspace: ws }),
  ]);
  const results = runs.filter((r) => r.files.length || (r.items || []).some((i) => i.files.length)).slice(0, 12);
  const use = typeof q.use === "string" && catalog.nodes.some((n) => n.kind === q.use) ? q.use : "";
  const useSpec = use ? catalog.nodes.find((n) => n.kind === use) : null;
  const eachRuns = workflows.reduce((s, w) => s + w.each, 0);

  return (
    <Shell current={`/w/${ws}`} workspace={info} crumbs={[{ label: info.name }]}>
      <section className="page-head">
        <p className="eyebrow">{info.kind === "product" ? "Product workspace" : "Brand workspace"}</p>
        <h1><span className="client-swatch" aria-hidden />{info.name}</h1>
        <p className="lede">{info.tagline || `${workflows.length} workflows on the canvas.`}</p>
        <div className="page-actions">
          {workflows[0] && <Link className="btn btn-primary" href={`/w/${ws}/f/${workflows[0].id}`}>Open canvas: {workflows[0].title}</Link>}
          <Link className="btn" href={`/explore?ws=${ws}`}>Explore steps{info.adult ? " (18+ shown)" : ""}</Link>
          <Link className="btn" href={`/batches?ws=${ws}`}>Batches {batches.length ? `(${batches.length})` : ""}</Link>
        </div>
      </section>

      {useSpec && (
        <section className="create" aria-label={`Add ${useSpec.label}`}>
          <p style={{ margin: 0 }}><b>Add {useSpec.label}</b> <span className="muted">to a canvas. It lands at the centre of the view; connect it and save.</span></p>
          <div className="pick-list">
            {workflows.map((w) => <Link key={w.id} href={`/w/${ws}/f/${w.id}?use=${use}`} className="pick">{w.title}</Link>)}
            {!workflows.length && <span className="muted">No workflows yet. Create one below, then add the step from the palette.</span>}
          </div>
        </section>
      )}

      <CreateBar workspaces={[{ id: info.id, name: info.name }]} workspace={info.id} />

      <section className="row" aria-labelledby="wf-h">
        <div className="row-head"><h2 id="wf-h">Canvases</h2><p>{workflows.length} workflows{eachRuns ? `, ${eachRuns} fan-out step(s)` : ""}. Saved tools open as a form.</p></div>
        {workflows.length ? (
          <div className="cards cards-wide">
            {workflows.map((w) => <WorkflowCard key={w.id} wf={w} workspace={ws} catalog={catalog} />)}
          </div>
        ) : (
          <div className="empty"><b>No workflows yet.</b>Describe one above, or start from an idea, a brief, or by combining templates.</div>
        )}
      </section>

      <section className="row" aria-labelledby="new-h">
        <div className="row-head"><h2 id="new-h">New workflow</h2><p>From an idea, a brief, by combining what exists, or by talking to the director.</p></div>
        <ClientWorkspace client={ws} ideas={templates.map((t) => ({ id: t.source?.idea, title: t.title, family: t.family })).filter((t) => t.id)} workflows={workflows.map((w) => ({ id: w.id, title: w.title }))} />
      </section>

      <section className="row" aria-labelledby="res-h">
        <div className="row-head"><h2 id="res-h">Results</h2><p>{runs.length} run(s) recorded, {runs.filter((r) => r.status === "dry-run").length} dry.</p></div>
        {results.length ? (
          <div className="cards" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))" }}>
            {results.flatMap((r) => (r.files.length ? r.files : r.items.flatMap((i) => i.files)).slice(0, 3).map((f) => <ResultTile key={`${r.run_id}-${f}`} run={r} file={f} label={r.workflow} />))}
          </div>
        ) : (
          <div className="empty"><b>Nothing made yet.</b>{runs.length ? "Every run so far was a dry run. Switch the canvas to Approve and run a stage." : "Open a canvas and dry-run a stage to see the plan; approve one to make something."}</div>
        )}
      </section>

      <section className="row" aria-labelledby="ref-h">
        <div className="row-head"><h2 id="ref-h">Characters and references</h2><p>Every collection is a folder with its rights on file. Drop files or a folder, name it by purpose, say who owns it; the studio writes the rest.</p></div>
        <ReferencesPanel workspace={ws} collections={refs} openOnLoad={q.add === "references" ? "new" : q.add === "pick" ? "pick" : null} />
      </section>

      <section className="row" aria-labelledby="kit-h">
        <div className="row-head"><h2 id="kit-h">Kit</h2><p>Read from brands/{ws}/brand.yaml. Edit the file to change it.</p></div>
        <div className="kit">
          <div className="stat">
            <small>Palette</small>
            <span className="swatches" style={{ marginTop: 8 }}>{info.palette.map((p) => <i key={p.key} style={{ background: p.hex }} title={`${p.key} ${p.hex}`} />)}</span>
            <small>{info.palette.map((p) => p.key).join(", ") || "none measured"}</small>
          </div>
          <div className="stat"><small>Logo</small><b style={{ fontSize: 13, wordBreak: "break-all" }}>{info.logo || "not set"}</b>{info.logoRule && <small>{info.logoRule}</small>}</div>
          {info.logo && /\.(png|jpe?g|webp)$/i.test(info.logo) && (
            <div className="stat" style={{ display: "grid", placeItems: "center" }}>
              <img src={mediaUrl(`brands/${ws}/${info.logo}`)} alt={`${info.name} logo`} style={{ maxHeight: 96, objectFit: "contain" }} />
            </div>
          )}
          {info.languages.length > 0 && <div className="stat"><small>Languages</small><b style={{ fontSize: 14 }}>{info.languages.join(", ")}</b></div>}
          {info.disclosure && <div className="stat"><small>Disclosure on every asset</small><b style={{ fontSize: 13 }}>{info.disclosure}</b></div>}
          <div className="stat"><small>18+ line</small><b style={{ fontSize: 14 }}>{info.adult ? "Enabled in brand.yaml" : "Off"}</b><small>{info.adult ? "Adult steps show in this workspace's palette." : "Set adult: true in brand.yaml to show adult steps here. Never on a client's infrastructure."}</small></div>
          <div className="stat"><small>Steps ready</small><b>{caps.counts.ready} <span style={{ fontSize: 13, fontWeight: 400, color: "var(--muted)" }}>of {caps.capabilities.length}</span></b><small>{READY_LABEL["needs-setup"]}: {caps.counts.needsSetup}. Gaps: {caps.counts.gap}.</small></div>
        </div>
      </section>
    </Shell>
  );
}
