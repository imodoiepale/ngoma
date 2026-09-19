"use client";

import { rightsChip, fmtBytes } from "./ReferenceIntake";

const VIDEO = /\.(mp4|mov)$/i;

export function purposeForRole(role, kind) {
  const r = String(role || "").toLowerCase();
  if (/face|persona|character|identity|batch/.test(r)) return "persona";
  if (/cloth|wardrobe|outfit|garment/.test(r)) return "wardrobe";
  if (/room|location|background|place/.test(r)) return "location";
  if (/motion|video|clip|driving/.test(r) || kind === "video") return "motion";
  if (/product/.test(r)) return "product";
  return "other";
}

// A collection at a glance: three thumbnails fanned as a stack, the count, and its rights as
// a chip. Rights unclear or unverified render as a warning the user can click to fix.
export default function RefStack({ col, size = 56, onFix, onPick, compact = false }) {
  if (!col) {
    return (
      <button type="button" className="ref-stack-empty" onClick={onPick}>
        <span className="ref-stack ph" style={{ "--s": `${size}px` }}><span /><span /><span /></span>
        <span className="ref-stack-text"><b>No references yet</b><small>Click to choose or drop files here</small></span>
      </button>
    );
  }
  const chip = rightsChip(col);
  const thumbs = col.thumbs || (col.files || []).slice(0, 3).map((f) => `/api/media?path=${encodeURIComponent(f)}`);
  return (
    <div className={`ref-stack-row${compact ? " is-compact" : ""}`}>
      <button type="button" className="ref-stack" style={{ "--s": `${size}px` }} onClick={onPick} title={onPick ? "Change collection" : col.name} aria-label={`${col.name}, ${col.count} files`}>
        {thumbs.slice(0, 3).map((t, i) => (VIDEO.test(t) ? <video key={i} src={t} muted preload="metadata" /> : <img key={i} src={t} alt="" loading="lazy" />))}
        {!thumbs.length && <span className="ref-empty">empty</span>}
        <span className="count-badge">{col.count}</span>
      </button>
      <span className="ref-stack-text">
        <b>{col.name}</b>
        <small>{col.images ? `${col.images} images` : ""}{col.images && col.videos ? ", " : ""}{col.videos ? `${col.videos} clips` : ""}{col.bytes ? `, ${fmtBytes(col.bytes)}` : ""}</small>
        {chip.warn ? (
          <button type="button" className={`chip ${chip.cls} chip-btn`} onClick={onFix} title={col.warning || "Fix the rights"}>{chip.text}: fix</button>
        ) : (
          <span className={`chip ${chip.cls}`}>{chip.text}</span>
        )}
      </span>
    </div>
  );
}
