import Link from "next/link";
import { fmtUsd } from "../lib/estimate";
import { HoverMedia } from "./HoverMedia";

export const READY_LABEL = { ready: "Ready", "needs-setup": "Needs setup", gap: "Gap" };
export const FAMILY = {
  volume: "Volume content", ugc: "UGC ads", persona: "AI influencer and AI model", music: "Music",
  service: "Productised services", education: "Education and community", saas: "Software", adult: "Fictional 18+ (gated)",
};

// A capability as a media card. The media is a real output from a run when one exists;
// otherwise the card shows what the step takes and gives. Never a stock image.
export function CapabilityCard({ cap, types, preview, hrefForUse }) {
  const outType = cap.outputs[0]?.type;
  const ins = cap.inputs.filter((p) => !p.optional).map((p) => (p.id === "media" ? "image or video" : types[p.type]?.label || p.type));
  const files = preview?.files || [];
  return (
    <article className="card" style={{ "--out": types[outType]?.color }}>
      <Link href={`/explore/${cap.kind}`} className="card-media-link" aria-label={`${cap.label}: details`}>
        <div className={`card-media${files.length <= 1 ? " single" : ""}`}>
          {files.length ? files.slice(0, 4).map((f) => <HoverMedia key={f} file={f} />) : (
            <div className="io">
              <span>{ins.length ? ins.join(" + ") : "Nothing"} to {types[outType]?.label || "result"}</span>
              <small>{cap.runsOn}</small>
            </div>
          )}
          <div className="card-badges">
            <span className={`chip chip-${cap.status}`}>{READY_LABEL[cap.status]}</span>
            {cap.consent && <span className="chip chip-consent">Consent</span>}
            {cap.adult && <span className="chip chip-consent">18+</span>}
            {cap.canEach && <span className="chip">each</span>}
          </div>
        </div>
      </Link>
      <div className="card-body">
        <Link href={`/explore/${cap.kind}`} className="card-title">{cap.label}</Link>
        <span className="card-sub">{cap.blurb}</span>
        <span className="card-foot">
          {cap.alternatives?.length ? <span>{cap.alternatives.length} alternative{cap.alternatives.length === 1 ? "" : "s"}</span> : null}
          {cap.estimate ? <span className="cost">{fmtUsd(cap.estimate.usd)} per unit <i className="basis">{cap.estimate.basis}</i></span> : <span className="cost">no GPU time</span>}
        </span>
      </div>
      {hrefForUse && (
        <div className="card-actions">
          <Link className="btn btn-primary btn-sm" href={hrefForUse}>{preview ? "Recreate" : "Use"}</Link>
        </div>
      )}
    </article>
  );
}

// A workflow at a glance: its chain of steps as coloured beads, one per node.
export function WorkflowCard({ wf, workspace, catalog, href }) {
  const byKind = Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
  const colour = (kind) => {
    const spec = byKind[kind];
    if (!spec || spec.backend.kind === "gap") return "var(--gap)";
    return catalog.types[spec.outputs[0]?.type]?.color || "var(--muted)";
  };
  const to = href || `/w/${workspace}/f/${wf.id}`;
  return (
    <article className="card">
      <Link href={to} className="card-body" style={{ gridRow: "1 / -1" }}>
        <span className="card-title">{wf.title}</span>
        <span className="beads" aria-hidden>
          {wf.kinds.slice(0, 14).map((k, i) => <i key={i} style={{ background: colour(k) }} />)}
        </span>
        <span className="card-foot">
          <span>{wf.nodes} steps</span>
          {wf.each > 0 && <span className="chip">{wf.each} each</span>}
          {wf.combined && <span className="chip">Combined</span>}
          {wf.tool && <span className="chip chip-proposed">Tool</span>}
          {wf.gaps > 0 && <span className="chip chip-gap">{wf.gaps} not runnable yet</span>}
          {wf.consent && <span className="chip chip-consent">Consent</span>}
        </span>
      </Link>
      {wf.tool && workspace !== "_templates" && (
        <div className="card-actions">
          <Link className="btn btn-sm" href={`/w/${workspace}/t/${wf.id}`}>Open tool</Link>
        </div>
      )}
    </article>
  );
}

// One result from a run, with a Recreate link that opens the workflow at the node that made it.
export function ResultTile({ run, file, label }) {
  return (
    <Link href={`${run.canvas}?node=${encodeURIComponent(run.node)}`} className="result-tile" title="Open on canvas">
      <figure style={{ margin: 0, height: "100%" }}>
        <HoverMedia file={file} />
        <figcaption><span>{label || run.kind}</span><span>{run.workspace}</span></figcaption>
      </figure>
    </Link>
  );
}
