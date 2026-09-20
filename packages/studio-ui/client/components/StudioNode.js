"use client";

import { memo, useContext, useState } from "react";
import { Handle, Position } from "reactflow";
import { CanvasContext } from "./canvas/context.js";
import RefStack from "./refs/RefStack";
import { fmtUsd, latestResult } from "../lib/estimate";

export const REF_KINDS = new Set(["reference-images", "product-photo", "video-clip"]);

const RUNS = { input: "You provide", brand: "Brand kit", comfy: "ComfyUI", router: "Hosted model", python: "Studio code", publish: "Draft", human: "You choose" };
const READY = { ready: "Ready", "needs-setup": "Needs setup", gap: "Gap" };
const isVideo = (f) => /\.(mp4|webm|mov)$/i.test(f);
const media = (f) => `/api/media?path=${encodeURIComponent(String(f).replace(/\\/g, "/"))}`;

function Thumb({ file, alt = "" }) {
  return isVideo(file)
    ? <video src={media(file)} muted loop playsInline preload="metadata" onMouseEnter={(e) => e.currentTarget.play().catch(() => {})} onMouseLeave={(e) => e.currentTarget.pause()} />
    : <img src={media(file)} alt={alt} loading="lazy" />;
}

// One step on the canvas. Inputs on the left, outputs on the right, each port coloured by the
// kind of thing it carries so a wrong connection is visible before it is refused. The node
// shows its readiness (Ready, Needs setup, Gap), what it last made (from run manifests, or the
// results the engine wrote on the node), its per-item grid and count when it runs once per
// item, and what it would cost to run.
function StudioNode({ id, data, selected }) {
  const ctx = useContext(CanvasContext) || {};
  const [over, setOver] = useState(false);
  const { spec, types, gap } = data;
  if (!spec) {
    return (
      <div className={`snode is-gap${selected ? " is-selected" : ""}`}>
        <div className="snode-head"><b>{data.step || data.kind}</b><span className="chip chip-gap">Gap</span></div>
        <p className="snode-note">No step in the studio runs this yet.</p>
      </div>
    );
  }
  const outType = spec.outputs[0]?.type;
  const colour = (t) => types[t]?.color || "#888";
  const portColour = (p) => (p.id === "media" ? "linear-gradient(135deg, var(--image) 50%, var(--video) 50%)" : colour(p.type));
  const readiness = ctx.readiness?.[spec.kind]?.status || (spec.backend.kind === "gap" ? "gap" : "ready");
  const waiting = spec.backend.kind === "human" && !(data.picked || []).length;
  const run = ctx.runsByNode?.[id] || null;
  const last = run || latestResult(data.results);
  const items = run?.items || null;
  const files = items ? items.map((i) => i.files?.[0]).filter(Boolean) : (last?.files || []);
  const shown = files.slice(0, items ? 6 : 3);
  const est = ctx.estimates?.[id];
  const each = !!data.each;
  const meta = [data.scene && `scene ${data.scene}`, data.camera, data.variant_count > 1 && `x${data.variant_count}`, data.role].filter(Boolean);
  const status = last?.status;
  const itemCount = items ? items.length : (each ? (est?.items && est.itemsKnown ? est.items : null) : null);
  // Input steps that take a reference collection show it as a stack and accept dropped files.
  const isRef = REF_KINDS.has(spec.kind);
  // the engine writes params.folder and data.collection; the intake writes params.folder and data.ref
  const folder = data.params?.folder || data.ref?.path || "";
  const col = isRef ? (ctx.refsByFolder?.[folder] || ctx.refsByName?.[data.collection] || ctx.refsByName?.[folder.split("/").filter(Boolean).pop()] || null) : null;
  const refDrop = isRef && ctx.openIntake ? {
    onDragOver: (e) => { if (e.dataTransfer?.types?.includes("Files")) { e.preventDefault(); e.stopPropagation(); setOver(true); } },
    onDragLeave: () => setOver(false),
    onDrop: (e) => { if (e.dataTransfer?.files?.length) { e.preventDefault(); e.stopPropagation(); setOver(false); ctx.openIntake({ nodeId: id, files: e.dataTransfer.files, purpose: spec.kind === "video-clip" ? "motion" : spec.kind === "product-photo" ? "product" : "persona", collection: col?.name }); } },
  } : {};

  return (
    <div className={`snode${gap ? " is-gap" : ""}${selected ? " is-selected" : ""}${waiting ? " is-waiting" : ""}${each ? " is-each" : ""}${over ? " is-over" : ""}`} data-kind={spec.kind} {...refDrop}>
      <div className="snode-head">
        <b title={spec.blurb}>{spec.label}</b>
        <span className="snode-flags">
          {each && <span className="snode-each" title="Runs once per item">each{itemCount ? ` ${itemCount}` : ""}</span>}
          {spec.adult && <span className="snode-flag" title="18+ line only: fictional adults, a separate entity">18+</span>}
          {spec.consent && <span className="snode-flag" title="Owned or consented likenesses only">Consent</span>}
        </span>
      </div>

      {isRef ? (
        <div className="snode-ref">
          <RefStack col={col} size={50} compact
            onPick={ctx.openIntake ? () => ctx.openIntake({ nodeId: id, purpose: spec.kind === "video-clip" ? "motion" : spec.kind === "product-photo" ? "product" : "persona", collection: col?.name, mode: "pick" }) : undefined}
            onFix={ctx.openIntake && col ? () => ctx.openIntake({ nodeId: id, collection: col.name, mode: col.verified ? "fix" : "fix" }) : undefined} />
        </div>
      ) : shown.length ? (
        <div className={`snode-thumbs${items ? " is-grid" : ""}`}>
          {shown.map((f, i) => <Thumb key={`${f}-${i}`} file={f} />)}
          {files.length > shown.length && <span className="more">+{files.length - shown.length}</span>}
        </div>
      ) : (
        <div className="snode-preview" style={{ "--out": colour(outType) }}>
          <span>{types[outType]?.label || "Result"}</span>
          <small>{spec.backend.kind === "gap" ? "Not runnable yet" : RUNS[spec.backend.kind]}</small>
        </div>
      )}

      <div className="snode-meta">
        <span className={`chip chip-${readiness}`}>{READY[readiness]}</span>
        {meta.map((m) => <b key={m}>{m}</b>)}
        {waiting && <span className="snode-status waiting">waiting for you</span>}
        {!waiting && spec.backend.kind === "human" && <span className="snode-status completed">kept {data.picked.length}</span>}
        {status && spec.backend.kind !== "human" && (
          <span className={`snode-status ${status}`}>
            {status}{items ? ` ${run.itemsDone}/${items.length}` : ""}
          </span>
        )}
        {est && est.basis !== "none" && (
          <span className="snode-cost" title={`${est.gpu_seconds}s GPU, ${est.basis}${est.rate ? `, ${est.rate}` : ""}`}>
            {fmtUsd(est.usd)}{each && !est.itemsKnown ? " per item" : ""} <i>{est.basis}</i>
          </span>
        )}
      </div>

      <div className="snode-ports">
        <div className="col">
          {spec.inputs.map((p) => (
            <div key={p.id} className="port port-in">
              <Handle type="target" position={Position.Left} id={p.id} className="handle" style={{ background: portColour(p) }} />
              <span>{p.id}{p.optional ? "?" : ""}{each && (data.each_port || ctx.iteratedPort?.(data, spec)) === p.id ? " (each)" : ""}</span>
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
