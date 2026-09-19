import Link from "next/link";
import { notFound } from "next/navigation";
import { TEMPLATES, listClients, listWorkflows } from "../../../lib/studio";
import { loadCapabilities } from "../../../lib/capabilities";
import { listRuns } from "../../../lib/runs";
import { fmtUsd } from "../../../lib/estimate";
import { Shell } from "../../../components/Shell";
import { ResultTile, READY_LABEL } from "../../../components/cards";
import UseInWorkspace from "../../../components/UseInWorkspace";

export const dynamic = "force-dynamic";

// One capability, in three steps: what you give, what you get, what it costs. Then where it
// runs, what it is waiting for, its alternatives, the templates that use it and its results.
export default async function CapabilityPage({ params }) {
  const { kind } = await params;
  const [caps, workspaces, templates, runs] = await Promise.all([loadCapabilities(), listClients(), listWorkflows(TEMPLATES), listRuns()]);
  const cap = caps.capabilities.find((c) => c.kind === kind);
  if (!cap) notFound();
  const anyAdult = workspaces.some((w) => w.adult);
  if (cap.adult && !anyAdult) notFound();
  const types = caps.types;
  const uses = templates.filter((t) => t.kinds.includes(kind));
  const made = runs.filter((r) => r.kind === kind && (r.files.length || (r.items || []).some((i) => i.files.length))).slice(0, 12);
  const label = (p) => (p.id === "media" ? "image or video" : types[p.type]?.label || p.type);

  return (
    <Shell current="/explore" crumbs={[{ href: "/explore", label: "Explore" }, { label: cap.label }]}>
      <section className="page-head">
        <p className="eyebrow">{caps.categories.find((c) => c.id === cap.category)?.label || cap.category}</p>
        <h1>{cap.label}</h1>
        <p className="lede">{cap.blurb}.</p>
        <div className="page-actions">
          <span className={`chip chip-${cap.status}`}>{READY_LABEL[cap.status]}</span>
          {cap.consent && <span className="chip chip-consent">Consent required</span>}
          {cap.adult && <span className="chip chip-consent">18+ line only</span>}
          {cap.canEach && <span className="chip">Can run once per item</span>}
        </div>
      </section>

      <div className="jobs-grid">
        <section className="panel-card">
          <h2>1. What you give</h2>
          {cap.inputs.length ? cap.inputs.map((p) => (
            <div key={p.id} className="kv"><span>{p.id}{p.optional ? " (optional)" : ""}</span><b><i className="lib-dot" style={{ background: types[p.type]?.color, display: "inline-block", marginRight: 6 }} />{label(p)}</b></div>
          )) : <p className="muted">Nothing. This step is a source.</p>}
          {cap.params.length > 0 && (
            <>
              <h2 style={{ marginTop: 14 }}>Settings</h2>
              {cap.params.map((p) => <div key={p.key} className="kv"><span>{p.label}</span><b>{p.type}{"default" in p ? `, default ${p.default}` : ""}</b></div>)}
            </>
          )}
        </section>
        <section className="panel-card">
          <h2>2. What you get</h2>
          {cap.outputs.map((p) => (
            <div key={p.id} className="kv"><span>{p.id}</span><b><i className="lib-dot" style={{ background: types[p.type]?.color, display: "inline-block", marginRight: 6 }} />{types[p.type]?.label || p.type}</b></div>
          ))}
          <h2 style={{ marginTop: 14 }}>Runs on</h2>
          <div className="kv"><span>Backend</span><b>{cap.runsOn}</b></div>
          {cap.backend.workflow && <div className="kv"><span>Workflow</span><b style={{ wordBreak: "break-all" }}>workflows/{cap.backend.workflow}</b></div>}
          {cap.backend.module && <div className="kv"><span>Module</span><b>{cap.backend.module}</b></div>}
          {cap.backend.profile && <div className="kv"><span>Profile</span><b>{cap.backend.profile}</b></div>}
        </section>
        <section className="panel-card">
          <h2>3. What it costs</h2>
          {cap.estimate ? (
            <>
              <div className="plan-total"><b>{fmtUsd(cap.estimate.usd)}</b><span className={`basis basis-${cap.estimate.basis}`}>{cap.estimate.basis}</span><small>per {cap.estimate.per === "second_of_video" ? "second of video" : "unit"}, {cap.estimate.seconds}s of GPU at {caps.pricing.rate.name} ${caps.pricing.rate.usd_per_hour}/h ({caps.pricing.rate.basis})</small></div>
              {cap.canEach && <p className="muted">Once per item: 50 items is {fmtUsd(cap.estimate.usd * 50)}{kind === "carousel" ? " per slide" : ""}. The item count is known before the gate because the folder is on disk.</p>}
            </>
          ) : <p className="muted">No GPU time in the cost model. Studio code, an input or a decision.</p>}
          <div className="kv"><span>Budget cap</span><b>{fmtUsd(caps.pricing.budget_usd)}</b></div>
          {cap.reasons.length > 0 && (
            <>
              <h2 style={{ marginTop: 14 }}>{cap.status === "ready" ? "Notes" : "Waiting for"}</h2>
              <ul className="plan-list">{cap.reasons.map((r, i) => <li key={i} className={cap.status === "ready" ? "plan-ready" : "plan-blocked"}><small>{r}</small></li>)}</ul>
            </>
          )}
        </section>
      </div>

      <UseInWorkspace kind={kind} workspaces={workspaces.filter((w) => !cap.adult || w.adult).map((w) => ({ id: w.id, name: w.name, workflows: w.workflows.map((x) => ({ id: x.id, title: x.title })) }))} />

      {cap.alternatives?.length > 0 && (
        <section className="row" aria-labelledby="alt-h">
          <div className="row-head"><h2 id="alt-h">Alternatives</h2><p>Other routes to the same result. Pick by readiness and cost, not by name.</p></div>
          <div className="cards">
            {cap.alternatives.map((a) => (
              <Link key={a.kind} href={`/explore/${a.kind}`} className="card"><span className="card-body"><span className="card-title">{a.label}</span><span className="card-foot"><span className={`chip chip-${a.status}`}>{READY_LABEL[a.status]}</span>{a.estimate && <span className="cost">{fmtUsd(a.estimate.usd)} <i className="basis">{a.estimate.basis}</i></span>}</span></span></Link>
            ))}
          </div>
        </section>
      )}

      {made.length > 0 && (
        <section className="row" aria-labelledby="made-h">
          <div className="row-head"><h2 id="made-h">Made with this step</h2><p>Open one to see the run and recreate it.</p></div>
          <div className="cards" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))" }}>
            {made.flatMap((r) => (r.files.length ? r.files : r.items.flatMap((i) => i.files)).slice(0, 2).map((f) => <ResultTile key={`${r.run_id}-${f}`} run={r} file={f} label={r.workflow} />))}
          </div>
        </section>
      )}

      <section className="row" aria-labelledby="tpl-h">
        <div className="row-head"><h2 id="tpl-h">Templates that use it</h2><p>{uses.length} of {templates.length}</p></div>
        {uses.length ? (
          <ul className="steps-list">
            {uses.map((t) => <li key={t.id}><Link href={`/w/${TEMPLATES}/f/${t.id}`}>{t.title}</Link>{t.gaps > 0 && <span className="chip chip-gap">{t.gaps} gap(s)</span>}</li>)}
          </ul>
        ) : <p className="muted">No template uses this step yet. Add it from the palette on any canvas.</p>}
      </section>
    </Shell>
  );
}
