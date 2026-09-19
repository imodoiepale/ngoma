import Link from "next/link";
import { loadPricing } from "../../lib/pricing";
import { loadCapabilities } from "../../lib/capabilities";
import { listRuns, spendSummary } from "../../lib/runs";
import { fmtUsd } from "../../lib/estimate";
import { Shell } from "../../components/Shell";
import PodStatus from "../../components/PodStatus";

export const dynamic = "force-dynamic";

// Jobs and budget: the cap a person set, what has been spent (estimated and measured), the
// GPU rate, what still needs setup, the recent runs, and the pods right now. No credits, no
// upsell: USD and a basis on every figure.
export default async function Jobs() {
  const [pricing, caps, spend, runs] = await Promise.all([loadPricing(), loadCapabilities(), spendSummary(), listRuns()]);
  const setup = caps.capabilities.filter((c) => c.status === "needs-setup");
  const recent = runs.slice(0, 20);
  return (
    <Shell current="/jobs" crumbs={[{ label: "Jobs" }]}>
      <section className="page-head">
        <p className="eyebrow">Jobs and budget</p>
        <h1>What it costs, what ran, what is running.</h1>
        <p className="lede">The budget cap lives in brands/_presets/engine.yaml and only a person changes it. Estimates come from seconds-per-unit figures marked measured or assumed. Queued is not success; a run counts when its manifest says completed.</p>
      </section>

      <div className="stats" style={{ marginBottom: 20 }}>
        <div className="stat"><b>{fmtUsd(pricing.budget_usd)}</b><small>budget cap {pricing.budget_usd === 0 ? "(nothing live runs)" : ""}</small></div>
        <div className="stat"><b>{fmtUsd(spend.estimated_usd)}</b><small>spent to date <span className="basis basis-assumed">estimated</span></small></div>
        <div className="stat"><b>{Math.round(spend.measured_gpu_seconds)}s</b><small>GPU measured <span className="basis basis-measured">measured</span></small></div>
        <div className="stat"><b>{spend.live_runs}</b><small>live runs, {spend.dry_runs} dry, {spend.partial} partial</small></div>
        <div className="stat"><b>${pricing.rate.usd_per_hour}/h</b><small>{pricing.rate.name} <span className={`basis basis-${pricing.rate.basis}`}>{pricing.rate.basis}</span></small></div>
      </div>

      <div className="jobs-grid">
        <section className="panel-card">
          <h2>Seconds per unit</h2>
          <p className="muted" style={{ marginTop: 0 }}>From {pricing.source}. A measured figure came from a pod run; an assumed one is a planning number until a run replaces it.</p>
          {Object.entries(pricing.seconds_per_unit).map(([k, v]) => (
            <div key={k} className="kv"><span>{k}</span><b>{v.seconds}s{v.per === "second_of_video" ? " per second of video" : ""}</b><span className={`basis basis-${v.basis}`}>{v.basis}</span><span className="muted">{fmtUsd((v.seconds / 3600) * pricing.rate.usd_per_hour)}</span></div>
          ))}
        </section>
        <section className="panel-card">
          <h2>Needs setup ({setup.length})</h2>
          <p className="muted" style={{ marginTop: 0 }}>Steps bound to a backend with something missing. Each line names the piece.</p>
          <ul className="plan-list">
            {setup.map((c) => <li key={c.kind} className="plan-waiting"><Link href={`/explore/${c.kind}`} style={{ fontWeight: 600, textDecoration: "none" }}>{c.label}</Link>{c.reasons.map((r, i) => <small key={i}>{r}</small>)}</li>)}
            {!setup.length && <li className="plan-ready"><small>Every bound step is ready.</small></li>}
          </ul>
        </section>
        <section className="panel-card">
          <h2>By workspace</h2>
          {Object.entries(spend.by_workspace).map(([ws, s]) => (
            <div key={ws} className="kv"><span><Link href={`/w/${ws}`}>{ws}</Link></span><b>{fmtUsd(s.estimated_usd)}</b><span className="muted">{s.live_runs} live, {s.dry_runs} dry</span></div>
          ))}
          {!Object.keys(spend.by_workspace).length && <p className="muted">No runs recorded yet.</p>}
          <h2 style={{ marginTop: 16 }}>Posture</h2>
          <div className="kv"><span>Default mode</span><b>dry-run</b></div>
          <div className="kv"><span>Live runs</span><b>a person approves the estimate first</b></div>
          <div className="kv"><span>Faces</span><b>owned or consented references only; the runner refuses others</b></div>
          <div className="kv"><span>Publishing</span><b>drafts only; a person posts</b></div>
        </section>
      </div>

      <section className="row" aria-labelledby="recent-h">
        <div className="row-head"><h2 id="recent-h">Recent runs</h2><p>{runs.length} manifests under brands/*/runs.</p></div>
        {recent.length ? (
          <div className="panel-card" style={{ padding: "4px 18px" }}>
            {recent.map((r) => (
              <div key={`${r.workspace}-${r.run_id}`} className="kv" style={{ alignItems: "center" }}>
                <span>{r.finished ? new Date(r.finished).toLocaleString() : ""}</span>
                <Link href={`${r.canvas}?node=${encodeURIComponent(r.node)}`} style={{ fontWeight: 600, textDecoration: "none" }}>{r.kind}{r.items ? ` each ${r.itemCount}` : ""}</Link>
                <span className="muted">{r.workspace} / {r.workflow}</span>
                <span className={`snode-status ${r.status}`}>{r.status}</span>
                {r.cost_estimate && <span className="muted">est {fmtUsd(r.cost_estimate.usd)} <i className="basis">{r.cost_estimate.basis}</i></span>}
                {r.gpu_seconds_actual != null && <span className="muted">measured {r.gpu_seconds_actual}s</span>}
              </div>
            ))}
          </div>
        ) : <div className="empty"><b>No runs yet.</b>Dry-run a stage on any canvas and its manifest appears here.</div>}
      </section>

      <section className="row" aria-labelledby="pods-h">
        <div className="row-head"><h2 id="pods-h">Pods right now</h2><p>From the RunPod account when RUNPOD_API_KEY is set on the server. Storage bills continuously and is not in the hourly figure.</p></div>
        <PodStatus />
      </section>
    </Shell>
  );
}
