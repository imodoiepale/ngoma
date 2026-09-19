"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

// "Use": drop this step onto a workspace's canvas, either into an existing workflow or a new
// one made from a one-line brief through the author.
export default function UseInWorkspace({ kind, workspaces }) {
  const router = useRouter();
  const [ws, setWs] = useState(workspaces[0]?.id || "");
  const [wf, setWf] = useState("new");
  const [state, setState] = useState({ busy: false, error: "" });
  const space = workspaces.find((w) => w.id === ws);

  async function go() {
    if (!ws) return;
    if (wf !== "new") { router.push(`/w/${ws}/f/${wf}?use=${kind}`); return; }
    setState({ busy: true, error: "" });
    const res = await fetch("/api/author", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "brief", client: ws, brief: kind.replace(/-/g, " "), title: "" }) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { setState({ busy: false, error: data.error || "Could not create a workflow. Open the workspace and add the step from the palette." }); return; }
    router.push(`/w/${ws}/f/${data.id}?use=${kind}`);
  }

  if (!workspaces.length) return <p className="muted" style={{ marginTop: 16 }}>No workspace may use this step.</p>;
  return (
    <section className="create" aria-label="Use this step">
      <div className="create-form" style={{ gridTemplateColumns: "auto auto minmax(0,1fr) auto" }}>
        <select value={ws} onChange={(e) => { setWs(e.target.value); setWf("new"); }} aria-label="Workspace">
          {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
        </select>
        <select value={wf} onChange={(e) => setWf(e.target.value)} aria-label="Workflow">
          <option value="new">New workflow</option>
          {(space?.workflows || []).map((w) => <option key={w.id} value={w.id}>{w.title}</option>)}
        </select>
        <span className="muted">Opens the canvas with this step added. Nothing runs.</span>
        <button type="button" className="btn btn-primary" disabled={state.busy} onClick={go}>Use on canvas</button>
      </div>
      {state.error && <p className="error" role="alert">{state.error}</p>}
    </section>
  );
}
