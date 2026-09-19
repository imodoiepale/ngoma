"use client";

import { canEach, iteratedPort } from "../../lib/graph";
import { fmtUsd } from "../../lib/estimate";
import RefStack from "../refs/RefStack";

const READY = { ready: "Ready", "needs-setup": "Needs setup", gap: "Gap" };

// Settings for the selected step: what runs it, its readiness and why, its parameters, the
// fan-out switch (run once per item) and which parameters a saved tool exposes.
export default function Inspector({ node, catalog, readiness, estimate, readOnly, collection, onIntake, onParam, onData, onDelete, onClose }) {
  if (!node) return null;
  const spec = node.data.spec;
  const be = spec?.backend;
  const state = readiness?.[spec?.kind];
  const runs = !spec ? `No catalogue node runs '${node.data.step}' yet.`
    : { input: "You provide this.", brand: "Read from the brand.yaml of this workspace.", comfy: `ComfyUI workflow: ${be.workflow}`,
        router: "Hosted image model through OpenRouter.", python: `Runs ${be.module}`, publish: `Creates a draft through ${be.module}`,
        human: "Waits for you to choose. Nothing downstream runs until you do.", gap: be.reason }[be.kind];
  const eachOk = canEach(spec);
  const iterable = spec ? spec.inputs.filter((p) => !p.optional && (p.type === "image" || p.type === "video" || p.id === "media")) : [];
  const expose = new Set(Array.isArray(node.data.expose) ? node.data.expose : []);
  const params = node.data.params || {};

  return (
    <aside className="panel inspector" aria-label="Step settings">
      <div className="inspector-head">
        <h3>{spec?.label || node.data.step}</h3>
        <button className="icon-btn" onClick={onClose} aria-label="Close settings">x</button>
      </div>
      {spec?.blurb && <p className="muted">{spec.blurb}</p>}
      <dl className="facts">
        <dt>Runs on</dt><dd className={be?.kind === "gap" || !spec ? "gap-text" : ""}>{runs}</dd>
        {state && (<><dt>Status</dt><dd><span className={`chip chip-${state.status}`}>{READY[state.status]}</span></dd></>)}
        {state?.reasons?.length ? (<><dt>Why</dt><dd className="why">{state.reasons.map((r, i) => <span key={i}>{r}</span>)}</dd></>) : null}
        {estimate && estimate.basis !== "none" && (<><dt>Estimate</dt><dd>{fmtUsd(estimate.usd)} <i className="basis">{estimate.basis}</i>, {estimate.gpu_seconds}s GPU{estimate.each ? (estimate.itemsKnown ? ` for ${estimate.items} items` : " per item") : ""}</dd></>)}
        {node.data.part && (<><dt>From</dt><dd>{node.data.part}</dd></>)}
      </dl>
      {collection !== undefined && (
        <fieldset className="field field-each">
          <legend className="muted" style={{ fontSize: 12 }}>References</legend>
          <RefStack col={collection} size={54}
            onPick={onIntake ? () => onIntake({ mode: "pick", collection: collection?.name }) : undefined}
            onFix={onIntake && collection ? () => onIntake({ mode: "fix", collection: collection.name }) : undefined} />
          {onIntake && (
            <div className="pick-list" style={{ marginTop: 10 }}>
              <button type="button" className="btn btn-sm" onClick={() => onIntake({ mode: "pick", collection: collection?.name })}>Choose a collection</button>
              <button type="button" className="btn btn-sm btn-quiet" onClick={() => onIntake({ mode: collection ? "add" : "new", collection: collection?.name })}>{collection ? "Add files" : "New from files or folder"}</button>
            </div>
          )}
          <small className="muted">A collection is a folder under references/ with its rights on file. Choose one from the grid or drop files on the node; nobody types a path.</small>
        </fieldset>
      )}
      {spec?.adult && <p className="notice">18+ line only: fictional adults, a separate entity, never on the infrastructure of a client workspace.</p>}
      {spec?.consent && <p className="notice">Only owned or consented likenesses may go into this step. The runner checks the rights in collection.json before a live submission.</p>}

      {eachOk && (
        <fieldset className="field field-each">
          <label className="switch">
            <input type="checkbox" checked={!!node.data.each} disabled={readOnly} onChange={(e) => onData({ each: e.target.checked || undefined, each_port: e.target.checked ? node.data.each_port : undefined })} />
            <span>Run once per item</span>
          </label>
          <small className="muted">Every file that reaches the iterated port becomes its own run. Fifty references become fifty results, with one seed per item.</small>
          {node.data.each && iterable.length > 1 && (
            <label className="field">
              <span>Iterate over</span>
              <select value={node.data.each_port || iteratedPort(node, spec) || ""} disabled={readOnly} onChange={(e) => onData({ each_port: e.target.value })}>
                {iterable.map((p) => <option key={p.id} value={p.id}>{p.id}</option>)}
              </select>
            </label>
          )}
        </fieldset>
      )}

      {spec?.params?.map((p) => (
        <label key={p.key} className="field">
          <span>
            {p.label}
            {spec.category !== "inputs" && (
              <label className="expose" title="Show this field in the saved tool's form">
                <input type="checkbox" checked={expose.has(p.key)} disabled={readOnly}
                  onChange={(e) => { const s = new Set(expose); if (e.target.checked) s.add(p.key); else s.delete(p.key); onData({ expose: s.size ? [...s] : undefined }); }} />
                <span>tool input</span>
              </label>
            )}
          </span>
          {p.type === "textarea" ? (
            <textarea rows={4} value={params[p.key] ?? ""} readOnly={readOnly} onChange={(e) => onParam(p.key, e.target.value)} />
          ) : p.type === "select" ? (
            <select value={params[p.key] ?? p.default} disabled={readOnly} onChange={(e) => onParam(p.key, e.target.value)}>
              {p.options.map((o) => <option key={o}>{o}</option>)}
            </select>
          ) : (
            <input type={p.type === "number" ? "number" : "text"} value={params[p.key] ?? ""} readOnly={readOnly}
              onChange={(e) => onParam(p.key, p.type === "number" ? Number(e.target.value) : e.target.value)} />
          )}
        </label>
      ))}
      {!readOnly && <button className="btn btn-danger" onClick={onDelete}>Delete step</button>}
    </aside>
  );
}
