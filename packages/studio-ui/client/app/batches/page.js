import Link from "next/link";
import { getClient, listClients, loadCatalog } from "../../lib/studio";
import { continuationsFor } from "../../lib/graph";
import { listBatches, listRuns } from "../../lib/runs";
import { fmtUsd } from "../../lib/estimate";
import { Shell } from "../../components/Shell";
import { HoverMedia } from "../../components/HoverMedia";

export const dynamic = "force-dynamic";

// Batches: every fan-out run (a manifest with items[]), item by item, with what went wrong
// where it did, and what to continue with. Presentation only; the runner writes the files.
export default async function Batches({ searchParams }) {
  const q = (await searchParams) || {};
  const wsKey = typeof q.ws === "string" ? q.ws : "";
  let scope = null;
  if (wsKey) { try { scope = await getClient(wsKey); } catch { scope = null; } }
  const [batches, runs, catalog, workspaces] = await Promise.all([
    listBatches(scope ? { workspace: scope.id } : {}), listRuns(scope ? { workspace: scope.id } : {}), loadCatalog(), listClients(),
  ]);
  const byKind = Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
  const partial = batches.filter((b) => b.status === "partial").length;

  return (
    <Shell current="/batches" workspace={scope} crumbs={[{ label: "Batches" }]}>
      <section className="page-head">
        <p className="eyebrow">Batches</p>
        <h1>Steps that ran once per item.</h1>
        <p className="lede">Each card is one run of a fan-out node: its items, which completed, which did not, and what it cost. Open the node on the canvas to see the inside of any item, or continue the whole batch with the next step.</p>
        <div className="page-actions pick-list" role="radiogroup" aria-label="Workspace">
          <Link href="/batches" className={`pick${!scope ? " is-on" : ""}`} role="radio" aria-checked={!scope}>All workspaces</Link>
          {workspaces.map((w) => <Link key={w.id} href={`/batches?ws=${w.id}`} className={`pick${scope?.id === w.id ? " is-on" : ""}`} role="radio" aria-checked={scope?.id === w.id}>{w.name}</Link>)}
        </div>
      </section>

      <div className="stats" style={{ marginBottom: 24 }}>
        <div className="stat"><b>{batches.length}</b><small>batch runs</small></div>
        <div className="stat"><b>{batches.reduce((s, b) => s + b.itemCount, 0)}</b><small>items in total</small></div>
        <div className="stat"><b>{partial}</b><small>partial (some items failed)</small></div>
        <div className="stat"><b>{runs.length}</b><small>runs of any kind</small></div>
      </div>

      {batches.length ? (
        <div style={{ display: "grid", gap: 14 }}>
          {batches.map((b) => {
            const spec = byKind[b.kind];
            const outType = spec?.outputs?.[0]?.type;
            const conts = continuationsFor(outType, catalog).slice(0, 4);
            const done = b.itemsDone, failed = b.itemsFailed, other = b.itemCount - done - failed;
            return (
              <article key={`${b.workspace}-${b.run_id}`} className="batch">
                <div className="batch-head">
                  <h3>{spec?.label || b.kind} <span className="snode-each" style={{ verticalAlign: "middle" }}>each {b.itemCount}</span></h3>
                  <span className={`snode-status ${b.status}`}>{b.status}</span>
                  <span className="muted">{b.workspace} / {b.workflow} / {b.node}</span>
                  <span className="muted">{b.finished ? new Date(b.finished).toLocaleString() : b.started ? new Date(b.started).toLocaleString() : ""}</span>
                  {b.cost_estimate && <span className="muted">est {fmtUsd(b.cost_estimate.usd)} <i className="basis">{b.cost_estimate.basis}</i></span>}
                  {b.gpu_seconds_actual != null && <span className="muted">measured {b.gpu_seconds_actual}s GPU</span>}
                  <Link href={`${b.canvas}?node=${encodeURIComponent(b.node)}`} style={{ marginLeft: "auto" }}>Open on canvas</Link>
                </div>
                <div className="progress" aria-label={`${done} of ${b.itemCount} completed`}>
                  <i style={{ width: `${(done / Math.max(1, b.itemCount)) * 100}%` }} />
                  <i className="failed" style={{ width: `${(failed / Math.max(1, b.itemCount)) * 100}%` }} />
                </div>
                <p className="muted" style={{ margin: 0 }}>{done} completed{failed ? `, ${failed} failed` : ""}{other > 0 ? `, ${other} ${b.status === "dry-run" ? "planned (dry run, nothing made)" : "other"}` : ""}. Downstream steps receive the completed items only.</p>
                <div className="batch-items">
                  {b.items.slice(0, 48).map((it) => (
                    <figure key={it.index} className={it.files.length ? (it.status === "completed" ? "" : "is-failed") : "is-empty"} title={it.input || `item ${it.index}`}>
                      {it.files[0] ? <HoverMedia file={it.files[0]} alt={`item ${it.index}`} /> : <span>{it.status === "completed" ? "no file" : it.status}</span>}
                      <figcaption>{it.index}{it.group != null ? ` ${it.group}` : ""}</figcaption>
                    </figure>
                  ))}
                  {b.items.length > 48 && <figure className="is-empty"><span>+{b.items.length - 48}</span></figure>}
                </div>
                {conts.length > 0 && b.status !== "dry-run" && (
                  <div className="continue-strip">
                    <span>Continue with:</span>
                    {conts.map((c) => (
                      <Link key={c.kind} href={`${b.canvas}?node=${encodeURIComponent(b.node)}&continue=${c.kind}`} className="pick" title="Opens the canvas with the step proposed on this node's output">
                        {c.label}{c.each ? ` for each of the ${done}` : ""}{c.kind === "carousel" ? ", 10 slides" : ""}
                      </Link>
                    ))}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      ) : (
        <div className="empty">
          <b>No batch runs yet.</b>
          A batch is a step with <code>each</code> on: every file reaching its iterated port becomes its own run. On a canvas, select a step, turn on Run once per item, feed it a reference folder and run a stage. The runner records <code>items[]</code> in the manifest and this page shows them.
          {runs.length > 0 && <span style={{ display: "block", marginTop: 8 }}>{runs.length} single runs exist. See them on the <Link href="/">home page</Link> or on their canvas.</span>}
        </div>
      )}
    </Shell>
  );
}
