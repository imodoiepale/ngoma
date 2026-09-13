"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const MODES = [
  { id: "idea", label: "From an idea", hint: "Start from one of the 50 costed ideas." },
  { id: "brief", label: "Describe it", hint: "Say what to make in plain words. The studio picks the steps." },
  { id: "combine", label: "Combine workflows", hint: "Chain workflows so one result feeds the next." },
];

export default function ClientWorkspace({ client, ideas, workflows }) {
  const router = useRouter();
  const [mode, setMode] = useState("brief");
  const [idea, setIdea] = useState(ideas[0]?.id || "");
  const [brief, setBrief] = useState("");
  const [title, setTitle] = useState("");
  const [picked, setPicked] = useState([]);
  const [state, setState] = useState({ busy: false, error: "" });

  function toggle(id) {
    setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
  }

  async function create(e) {
    e.preventDefault();
    setState({ busy: true, error: "" });
    const body = { mode, client, title, idea, brief, refs: picked };
    const res = await fetch("/api/author", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      setState({ busy: false, error: data.error || "Could not create the workflow." });
      return;
    }
    router.push(`/c/${client}/w/${data.id}`);
  }

  return (
    <form className="creator" onSubmit={create}>
      <div className="creator-modes" role="tablist">
        {MODES.map((m) => (
          <button key={m.id} type="button" role="tab" aria-selected={mode === m.id}
            className={mode === m.id ? "mode is-on" : "mode"} onClick={() => setMode(m.id)}>
            <b>{m.label}</b>
            <small>{m.hint}</small>
          </button>
        ))}
      </div>

      <div className="creator-body">
        {mode === "idea" && (
          <label className="field">
            <span>Idea</span>
            <select value={idea} onChange={(e) => setIdea(e.target.value)}>
              {ideas.map((i) => (
                <option key={i.id} value={i.id}>{i.id} · {i.title}</option>
              ))}
            </select>
          </label>
        )}
        {mode === "brief" && (
          <label className="field">
            <span>What should this make?</span>
            <textarea rows={3} value={brief} onChange={(e) => setBrief(e.target.value)}
              placeholder="A Sheng WhatsApp Status ad showing a mama mboga getting paid by voice, with captions" />
          </label>
        )}
        {mode === "combine" && (
          <fieldset className="field">
            <span>Pick workflows in the order they should run</span>
            <div className="pick-list">
              {workflows.map((w) => {
                const at = picked.indexOf(w.id);
                return (
                  <button key={w.id} type="button" className={at >= 0 ? "pick is-on" : "pick"} onClick={() => toggle(w.id)}>
                    {at >= 0 && <em>{at + 1}</em>}
                    {w.title}
                  </button>
                );
              })}
            </div>
          </fieldset>
        )}
        <label className="field field-title">
          <span>Title (optional)</span>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Named after the idea if empty" />
        </label>
        <div className="creator-actions">
          {state.error && <p className="error" role="alert">{state.error}</p>}
          <button className="btn btn-primary" disabled={state.busy || (mode === "combine" && picked.length < 2)}>
            {state.busy ? "Creating workflow…" : "Create workflow"}
          </button>
        </div>
      </div>
    </form>
  );
}
