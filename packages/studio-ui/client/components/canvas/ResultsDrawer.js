"use client";

import { fmtUsd } from "../../lib/estimate";

const isVideo = (f) => /\.(mp4|webm|mov)$/i.test(f);
const media = (f) => `/api/media?path=${encodeURIComponent(String(f).replace(/\\/g, "/"))}`;

// What a step made, as a grid, with the inside of the run (bindings, seeds, cost) and the
// "Continue with" suggestions that attach a proposed step to its output.
export default function ResultsDrawer({ node, run, continuations, onContinue, onRerun, onClose }) {
  if (!node || !run) return null;
  const items = run.items || null;
  const files = items ? items.flatMap((i) => (i.files || []).map((f) => ({ file: f, group: i.index, status: i.status }))) : (run.files || []).map((f) => ({ file: f }));
  return (
    <aside className="panel results" aria-label="Results">
      <div className="inspector-head">
        <h3>{node.data.spec?.label || node.data.kind} results</h3>
        <button className="icon-btn" onClick={onClose} aria-label="Close results">x</button>
      </div>
      <p className="muted">
        <span className={`snode-status ${run.status}`}>{run.status}</span>
        {items ? ` ${run.itemsDone} of ${items.length} items completed${run.itemsFailed ? `, ${run.itemsFailed} failed` : ""}.` : ` ${files.length} file(s).`}
        {run.cost_estimate ? ` Est ${fmtUsd(run.cost_estimate.usd)} (${run.cost_estimate.basis}).` : ""}
        {run.gpu_seconds_actual != null ? ` Measured ${run.gpu_seconds_actual}s GPU.` : ""}
      </p>
      {files.length ? (
        <div className="pick-grid">
          {files.slice(0, 60).map((f, i) => (
            <figure key={`${f.file}-${i}`} className="result-cell">
              {isVideo(f.file) ? <video src={media(f.file)} muted loop playsInline controls preload="metadata" /> : <img src={media(f.file)} alt="" loading="lazy" />}
              {f.group != null && <figcaption>item {f.group}{f.status && f.status !== "completed" ? ` ${f.status}` : ""}</figcaption>}
            </figure>
          ))}
        </div>
      ) : (
        <p className="muted">{run.status === "dry-run" ? "A dry run: the plan was written, nothing was made." : "No files recorded for this run."}</p>
      )}
      {items && items.some((i) => i.status !== "completed") && (
        <p className="notice">Partial: downstream steps receive the completed items only. Failed items: {items.filter((i) => i.status !== "completed").map((i) => i.index).join(", ")}.</p>
      )}
      <details className="inside">
        <summary>Inside this run</summary>
        <dl className="facts">
          <dt>Run</dt><dd>{run.run_id}</dd>
          {run.comfy_workflow && (<><dt>Workflow</dt><dd>{run.comfy_workflow}</dd></>)}
          {run.seeds?.length ? (<><dt>Seeds</dt><dd>{run.seeds.slice(0, 8).join(", ")}{run.seeds.length > 8 ? ` +${run.seeds.length - 8}` : ""}</dd></>) : null}
          {Object.entries(run.bindings || {}).map(([k, v]) => (<span key={k} className="facts-row"><dt>{k}</dt><dd>{Array.isArray(v) ? `${v.length} files` : String(v)}</dd></span>))}
          {run.prompt && (<><dt>Prompt</dt><dd>{run.prompt}</dd></>)}
          {run.note && (<><dt>Note</dt><dd>{run.note}</dd></>)}
        </dl>
      </details>
      <div className="continue">
        <h4>Continue with</h4>
        <div className="pick-list">
          {continuations.slice(0, 6).map((c) => (
            <button key={c.kind} type="button" className="pick" onClick={() => onContinue(c)} title={c.each ? "Runs once per result" : ""}>
              {c.label}{c.each ? " for each" : ""}
            </button>
          ))}
          {!continuations.length && <span className="muted">Nothing in the catalogue accepts this output.</span>}
        </div>
        {onRerun && <button type="button" className="btn btn-quiet btn-sm" onClick={onRerun}>Recreate: run this stage again</button>}
      </div>
    </aside>
  );
}
