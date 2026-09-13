"use client";

import { memo } from "react";
import { Handle, Position } from "reactflow";

// One step on the canvas. Inputs on the left, outputs on the right, each port coloured by
// the kind of thing it carries so a wrong connection is visible before it is refused.
function StudioNode({ data, selected }) {
  const { spec, types, gap } = data;
  if (!spec) {
    return (
      <div className={`snode is-gap${selected ? " is-selected" : ""}`}>
        <div className="snode-head"><b>{data.step}</b></div>
        <p className="snode-note">No step in the studio runs this yet.</p>
      </div>
    );
  }
  const outType = spec.outputs[0]?.type;
  const colour = (t) => types[t]?.color || "#888";
  const portColour = (p) => (p.id === "media" ? "linear-gradient(135deg, var(--image) 50%, var(--video) 50%)" : colour(p.type));
  const ready = spec.backend.kind !== "gap";
  return (
    <div className={`snode${gap ? " is-gap" : ""}${selected ? " is-selected" : ""}`}>
      <div className="snode-head">
        <b>{spec.label}</b>
        {spec.consent && <span className="snode-flag" title="Consent needed">Consent</span>}
      </div>
      <div className="snode-preview" style={{ "--out": colour(outType) }}>
        <span>{types[outType]?.label || "Result"}</span>
        <small>{ready ? { input: "You provide", brand: "Brand kit", comfy: "ComfyUI", router: "Hosted model", python: "Studio code", publish: "Draft" }[spec.backend.kind] : "Not runnable yet"}</small>
      </div>
      <div className="snode-ports">
        <div className="col">
          {spec.inputs.map((p) => (
            <div key={p.id} className="port port-in">
              <Handle type="target" position={Position.Left} id={p.id} className="handle" style={{ background: portColour(p) }} />
              <span>{p.id}{p.optional ? "?" : ""}</span>
            </div>
          ))}
        </div>
        <div className="col col-out">
          {spec.outputs.map((p) => (
            <div key={p.id} className="port port-out">
              <span>{p.id}</span>
              <Handle type="source" position={Position.Right} id={p.id} className="handle" style={{ background: colour(p.type) }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default memo(StudioNode);
