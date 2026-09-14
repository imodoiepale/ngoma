"use client";

import { memo } from "react";
import { Handle, Position } from "reactflow";

const RUNS = { input: "You provide", brand: "Brand kit", comfy: "ComfyUI", router: "Hosted model", python: "Studio code", publish: "Draft", human: "You choose" };

function latest(results) {
  return (results || []).slice().sort((a, b) => String(b.finished || "").localeCompare(String(a.finished || "")))[0] || null;
}

// One step on the canvas. Inputs on the left, outputs on the right, each port coloured by
// the kind of thing it carries so a wrong connection is visible before it is refused.
// Engine nodes also show what they made (thumbnails), their scene and angle, and whether
// a person still has to choose.
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
  const waiting = spec.backend.kind === "human" && !(data.picked || []).length;
  const last = latest(data.results);
  const files = (last?.files || []).slice(0, 3);
  const isVideo = (f) => /\.(mp4|webm|mov)$/i.test(f);
  const meta = [data.scene && `scene ${data.scene}`, data.camera, data.variant_count > 1 && `×${data.variant_count}`, data.role].filter(Boolean);
  return (
    <div className={`snode${gap ? " is-gap" : ""}${selected ? " is-selected" : ""}${waiting ? " is-waiting" : ""}`}>
      <div className="snode-head">
        <b>{spec.label}</b>
        <span>
          {spec.adult && <span className="snode-flag" title="18+ line only: fictional adults, separate entity">18+</span>}
          {spec.consent && <span className="snode-flag" title="Consent needed">Consent</span>}
        </span>
      </div>
      {files.length ? (
        <div className="snode-thumbs">
          {files.map((f) => (isVideo(f)
            ? <video key={f} src={`/api/media?path=${encodeURIComponent(f)}`} muted loop playsInline />
            : <img key={f} src={`/api/media?path=${encodeURIComponent(f)}`} alt="" />))}
          {(last.files.length > 3) && <span className="more">+{last.files.length - 3}</span>}
        </div>
      ) : (
        <div className="snode-preview" style={{ "--out": colour(outType) }}>
          <span>{types[outType]?.label || "Result"}</span>
          <small>{ready ? RUNS[spec.backend.kind] : "Not runnable yet"}</small>
        </div>
      )}
      {(meta.length || last || waiting) && (
        <div className="snode-meta">
          {meta.map((m) => <b key={m}>{m}</b>)}
          {waiting && <span className="snode-status waiting">waiting for you</span>}
          {!waiting && spec.backend.kind === "human" && <span className="snode-status completed">kept {data.picked.length}</span>}
          {last && spec.backend.kind !== "human" && <span className={`snode-status ${last.status}`}>{last.status}</span>}
        </div>
      )}
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
