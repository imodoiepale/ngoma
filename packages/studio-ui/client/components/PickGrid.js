"use client";

import { useState } from "react";

// Candidates from every step feeding a pick, as a grid. Choose up to k, confirm, and the
// runner feeds only those to what comes next.
export default function PickGrid({ client, workflow, node, candidates, onPicked, onClose }) {
  const k = Number(node.data?.params?.k || candidates.length);
  const [chosen, setChosen] = useState(new Set(node.data?.picked || []));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function toggle(id) {
    setChosen((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id); else if (n.size < k) n.add(id);
      return n;
    });
  }

  async function confirm() {
    setBusy(true); setError("");
    const res = await fetch("/api/pick", { method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client, workflow, node: node.id, picked: [...chosen] }) });
    const data = await res.json().catch(() => ({}));
    setBusy(false);
    if (!res.ok) { setError(data.error || "Could not save the pick."); return; }
    onPicked([...chosen]);
  }

  return (
    <aside className="panel pickgrid" aria-label="Your pick">
      <div className="inspector-head">
        <h3>Keep up to {k} of {candidates.length}</h3>
        <button className="icon-btn" onClick={onClose} aria-label="Close">×</button>
      </div>
      {!candidates.length && <p className="muted">Nothing to choose from yet. Run the stage before this one, then come back.</p>}
      <div className="pick-grid">
        {candidates.map((c) => (
          <button key={c.id} type="button" className={`pick-cell${chosen.has(c.id) ? " is-on" : ""}`} onClick={() => toggle(c.id)} aria-pressed={chosen.has(c.id)}>
            {c.file ? (c.video
              ? <video src={`/api/media?path=${encodeURIComponent(c.file)}`} muted loop playsInline />
              : <img src={`/api/media?path=${encodeURIComponent(c.file)}`} alt={c.label} />)
              : <span className="pick-empty">{c.label}</span>}
            <small>{c.label}</small>
          </button>
        ))}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="creator-actions">
        <span className="muted">{chosen.size} chosen</span>
        <button className="btn btn-primary" onClick={confirm} disabled={busy || !chosen.size}>{busy ? "Saving" : "Keep these"}</button>
      </div>
    </aside>
  );
}
