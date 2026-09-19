"use client";

import { useState } from "react";

// "Save as tool": pick which fields a colleague fills, and the same workflow gets a one-panel
// form at /w/<workspace>/t/<id>. Input steps' fields are on by default; any other step's
// parameter can be exposed too. The graph does not change; only wf.tool and each node's
// data.expose are written.
export default function ToolDialog({ wf, catalog, onSave, onClose }) {
  const byKind = Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
  const candidates = [];
  for (const n of wf.nodes) {
    const spec = byKind[n.kind];
    if (!spec) continue;
    for (const p of spec.params || []) {
      candidates.push({ node: n.id, kind: n.kind, nodeLabel: spec.label, key: p.key, label: p.label, isInput: spec.category === "inputs", on: spec.category === "inputs" || (Array.isArray(n.data?.expose) && n.data.expose.includes(p.key)) });
    }
  }
  const [title, setTitle] = useState(wf.tool?.title || wf.title || "");
  const [on, setOn] = useState(new Set(candidates.filter((c) => c.on).map((c) => `${c.node}:${c.key}`)));
  const [busy, setBusy] = useState(false);
  const toggle = (k) => setOn((s) => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });

  async function save() {
    setBusy(true);
    const exposeByNode = {};
    for (const c of candidates) if (on.has(`${c.node}:${c.key}`) && !c.isInput) (exposeByNode[c.node] ||= []).push(c.key);
    await onSave({ title: title.trim() || wf.title, inputs: candidates.filter((c) => on.has(`${c.node}:${c.key}`)).map((c) => ({ node: c.node, key: c.key })), exposeByNode });
    setBusy(false);
  }

  return (
    <div className="cmdk-backdrop" onMouseDown={onClose} role="presentation">
      <div className="cmdk tooldlg" role="dialog" aria-modal="true" aria-label="Save as tool" onMouseDown={(e) => e.stopPropagation()}>
        <h3>Save as tool</h3>
        <p className="muted">A tool is this graph with only the fields below showing. Colleagues fill them in and press Run; the nodes stay here for anyone who wants them.</p>
        <label className="field"><span>Tool name</span><input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
        <ul className="tool-fields">
          {candidates.map((c) => {
            const k = `${c.node}:${c.key}`;
            return (
              <li key={k}>
                <label className="switch">
                  <input type="checkbox" checked={on.has(k)} onChange={() => toggle(k)} />
                  <span><b>{c.label}</b> <small className="muted">{c.nodeLabel}{c.isInput ? " (input)" : ""}</small></span>
                </label>
              </li>
            );
          })}
          {!candidates.length && <li className="muted">This graph has no fields to expose. Add an input step or a step with parameters.</li>}
        </ul>
        <div className="creator-actions">
          <button type="button" className="btn btn-quiet" onClick={onClose}>Cancel</button>
          <button type="button" className="btn btn-primary" disabled={busy || !on.size} onClick={save}>{busy ? "Saving" : "Save tool"}</button>
        </div>
      </div>
    </div>
  );
}
