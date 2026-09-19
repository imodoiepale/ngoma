"use client";

import { memo } from "react";
import { Handle, Position } from "reactflow";
import { fmtUsd } from "../../lib/estimate";

// A proposed step: what the describe bar or a "Continue with" suggestion would add. It is
// drawn in the graph so describing something visibly builds nodes, but it is not part of the
// workflow until accepted. Ports are shown so its links read the same as a real node's.
function GhostNode({ data, selected }) {
  const { spec, types, each, params = {}, estimate, onAccept, onDiscard, onToggleEach, onParam, itemCount, note, kindLabel } = data;
  const colour = (t) => types?.[t]?.color || "#888";
  const label = spec?.label || kindLabel || data.kind;
  const slidesParam = (spec?.params || []).find((p) => p.key === "slides");
  return (
    <div className={`snode ghost${selected ? " is-selected" : ""}${each ? " is-each" : ""}`} aria-label={`Proposed step ${label}`}>
      <div className="snode-head">
        <b>{label}</b>
        <span className="snode-flags"><span className="chip chip-proposed">Proposed</span></span>
      </div>
      <div className="ghost-body">
        {note && <p className="muted">{note}</p>}
        {onToggleEach && spec && (
          <label className="ghost-row">
            <input type="checkbox" checked={!!each} onChange={(e) => onToggleEach(e.target.checked)} />
            <span>for each{itemCount ? ` of the ${itemCount}` : " item"}</span>
          </label>
        )}
        {slidesParam && onParam && (
          <label className="ghost-row">
            <span>Slides</span>
            <span className="seg" role="radiogroup" aria-label="Slides per carousel">
              {[5, 10].map((n) => (
                <button key={n} type="button" role="radio" aria-checked={Number(params.slides) === n} className={Number(params.slides) === n ? "is-on" : ""} onClick={() => onParam("slides", n)}>{n}</button>
              ))}
              <input type="number" min={1} max={20} value={params.slides ?? ""} onChange={(e) => onParam("slides", Number(e.target.value))} aria-label="Slides" />
            </span>
          </label>
        )}
        {estimate && estimate.basis !== "none" && (
          <p className="ghost-cost">est {fmtUsd(estimate.usd)} <i>{estimate.basis}</i>{itemCount && each ? ` for ${itemCount} items` : ""}</p>
        )}
        {(onAccept || onDiscard) && (
          <div className="ghost-actions">
            {onAccept && <button type="button" className="btn btn-primary btn-sm" onClick={onAccept}>Add to graph</button>}
            {onDiscard && <button type="button" className="btn btn-quiet btn-sm" onClick={onDiscard}>Dismiss</button>}
          </div>
        )}
      </div>
      {spec && (
        <div className="snode-ports">
          <div className="col">
            {spec.inputs.map((p) => (
              <div key={p.id} className="port port-in">
                <Handle type="target" position={Position.Left} id={p.id} className="handle" isConnectable={false} style={{ background: p.id === "media" ? "linear-gradient(135deg, var(--image) 50%, var(--video) 50%)" : colour(p.type) }} />
                <span>{p.id}{p.optional ? "?" : ""}</span>
              </div>
            ))}
          </div>
          <div className="col col-out">
            {spec.outputs.map((p) => (
              <div key={p.id} className="port port-out">
                <span>{p.id}</span>
                <Handle type="source" position={Position.Right} id={p.id} className="handle" isConnectable={false} style={{ background: colour(p.type) }} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default memo(GhostNode);
