"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const READY = { ready: "Ready", "needs-setup": "Setup", gap: "Gap" };

export function visibleNodes(catalog, { allowAdult, readiness }) {
  return catalog.nodes
    .filter((n) => allowAdult || !n.adult)
    .map((n) => ({ ...n, readiness: readiness?.[n.kind]?.status || (n.backend.kind === "gap" ? "gap" : "ready") }));
}

function matches(n, q) {
  if (!q) return true;
  const hay = `${n.label} ${n.blurb} ${n.kind} ${(n.steps || []).join(" ")}`.toLowerCase();
  return q.toLowerCase().split(/\s+/).every((w) => hay.includes(w));
}

// The node palette: every catalogue step grouped by family, searchable, draggable onto the
// canvas or added with a click. Steps a workspace may not use (18+) are not listed.
export function Palette({ catalog, allowAdult, readiness, onPick, collapsed, onToggle }) {
  const [q, setQ] = useState("");
  const nodes = useMemo(() => visibleNodes(catalog, { allowAdult, readiness }), [catalog, allowAdult, readiness]);
  const shown = nodes.filter((n) => matches(n, q));
  return (
    <aside className={`panel palette${collapsed ? " is-collapsed" : ""}`} aria-label="Node palette">
      <div className="palette-head">
        <input className="search" placeholder="Search steps" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search steps" />
        <button type="button" className="icon-btn" onClick={onToggle} aria-label={collapsed ? "Show palette" : "Hide palette"} aria-expanded={!collapsed}>{collapsed ? ">" : "<"}</button>
      </div>
      <p className="palette-hint">Drag onto the canvas, or press <kbd>Ctrl</kbd> <kbd>K</kbd></p>
      <div className="palette-scroll">
        {catalog.categories.map((c) => {
          const items = shown.filter((n) => n.category === c.id);
          if (!items.length) return null;
          return (
            <div key={c.id} className="lib-group">
              <h4>{c.label}</h4>
              {items.map((n) => (
                <button key={n.kind} type="button" className={`lib-item is-${n.readiness}`} draggable
                  onDragStart={(e) => { e.dataTransfer.setData("application/studio-node", n.kind); e.dataTransfer.effectAllowed = "move"; }}
                  onClick={() => onPick(n.kind)} title={n.blurb}>
                  <span className="lib-dot" style={{ background: catalog.types[n.outputs[0]?.type]?.color || "var(--muted)" }} />
                  <span className="lib-text">
                    <b>{n.label}</b>
                    <small>{n.readiness === "gap" ? "Not runnable yet" : n.blurb}</small>
                  </span>
                  <span className={`chip chip-${n.readiness}`}>{READY[n.readiness]}</span>
                </button>
              ))}
            </div>
          );
        })}
        {!shown.length && <p className="muted palette-empty">Nothing matches. Try a step name like carousel, wardrobe or lipsync.</p>}
      </div>
    </aside>
  );
}

// Command-K: type a step, press Enter, it lands at the centre of the view. Mounted only while
// open, so it starts empty each time.
export function CommandK({ onClose, catalog, allowAdult, readiness, onPick }) {
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const input = useRef(null);
  const nodes = useMemo(() => visibleNodes(catalog, { allowAdult, readiness }), [catalog, allowAdult, readiness]);
  const shown = nodes.filter((n) => matches(n, q)).slice(0, 12);

  useEffect(() => { const t = setTimeout(() => input.current?.focus(), 10); return () => clearTimeout(t); }, []);

  const choose = (n) => { onPick(n.kind); onClose(); };
  return (
    <div className="cmdk-backdrop" onMouseDown={onClose} role="presentation">
      <div className="cmdk" role="dialog" aria-modal="true" aria-label="Add a step" onMouseDown={(e) => e.stopPropagation()}>
        <input ref={input} className="cmdk-input" value={q} onChange={(e) => { setQ(e.target.value); setI(0); }} placeholder="Add a step: carousel, head swap, lipsync, export"
          aria-label="Search steps to add"
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setI((x) => Math.min(shown.length - 1, x + 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setI((x) => Math.max(0, x - 1)); }
            else if (e.key === "Enter" && shown[i]) { e.preventDefault(); choose(shown[i]); }
            else if (e.key === "Escape") onClose();
          }} />
        <ul className="cmdk-list" role="listbox">
          {shown.map((n, idx) => (
            <li key={n.kind} role="option" aria-selected={idx === i} className={idx === i ? "is-on" : ""} onMouseEnter={() => setI(idx)} onClick={() => choose(n)}>
              <span className="lib-dot" style={{ background: catalog.types[n.outputs[0]?.type]?.color || "var(--muted)" }} />
              <span className="lib-text"><b>{n.label}</b><small>{n.blurb}</small></span>
              <span className="cmdk-io">{n.inputs.filter((p) => !p.optional).map((p) => p.type).join(" + ") || "none"} to {n.outputs[0]?.type || "none"}</span>
              <span className={`chip chip-${n.readiness}`}>{READY[n.readiness]}</span>
            </li>
          ))}
          {!shown.length && <li className="muted">No step matches.</li>}
        </ul>
        <p className="cmdk-foot">Enter adds. Esc closes. Arrows move.</p>
      </div>
    </div>
  );
}
