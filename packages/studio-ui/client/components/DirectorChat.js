"use client";

import { useEffect, useRef, useState } from "react";
import VoiceDirector from "./VoiceDirector";

// The director's chat. Every line you send changes the brief; the workflow is rebuilt from
// it and the canvas redraws. The same endpoint serves the voice agent.
export default function DirectorChat({ client, workflow, session, initial = [], onWorkflow, onClose }) {
  const [lines, setLines] = useState(initial.length ? initial : [{ who: "director", text: "Tell me scenes, angles, wardrobe, a look, or a kind of piece. Say \"run the next stage\" when you are ready." }]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);

  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [lines]);

  async function send(message) {
    const msg = (message ?? text).trim();
    if (!msg || busy) return;
    setText("");
    setLines((l) => l.concat({ who: "you", text: msg }));
    setBusy(true);
    try {
      const res = await fetch("/api/director", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client, session, workflow, message: msg }) });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) { setLines((l) => l.concat({ who: "director", text: data.error || "I did not catch that.", error: true })); return data.error; }
      const picks = data.pending_picks?.length ? ` ${data.pending_picks.length} pick(s) waiting for you.` : "";
      setLines((l) => l.concat({ who: "director", text: `${data.reply}${picks}` }));
      onWorkflow?.(data.workflow, data.session);
      return data.reply;
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="panel director" aria-label="Director">
      <div className="inspector-head">
        <h3>Director</h3>
        <div className="director-tools">
          <VoiceDirector onUtterance={(t) => send(t)} />
          <button className="icon-btn" onClick={onClose} aria-label="Close director">×</button>
        </div>
      </div>
      <ol className="director-lines" aria-live="polite">
        {lines.map((l, i) => (
          <li key={i} className={`line line-${l.who}${l.error ? " line-error" : ""}`}>{l.text}</li>
        ))}
        <li ref={end} aria-hidden />
      </ol>
      <form className="director-input" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="add a scene at a rooftop at golden hour, 5 angles" aria-label="Say something to the director" disabled={busy} />
        <button className="btn btn-primary" disabled={busy || !text.trim()}>{busy ? "…" : "Say"}</button>
      </form>
    </aside>
  );
}
