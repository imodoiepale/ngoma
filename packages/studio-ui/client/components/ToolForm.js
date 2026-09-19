"use client";

import { useState } from "react";
import Link from "next/link";
import { fmtUsd } from "../lib/estimate";

// A saved tool: the workflow as a one-panel form. Fill the exposed fields, save them into the
// graph, and dry-run the next stage. The nodes are one click away for anyone who wants them.
export default function ToolForm({ workspace, workflow, inputs, estimate, consent, gaps, readiness }) {
  const [values, setValues] = useState(Object.fromEntries(inputs.map((i) => [`${i.node}:${i.key}`, i.value])));
  const [state, setState] = useState({ busy: false, msg: "", error: "" });

  async function apply(run) {
    setState({ busy: true, msg: "", error: "" });
    const res = await fetch(`/api/workflows/${workspace}/${workflow.id}`);
    const wf = await res.json().catch(() => null);
    if (!res.ok || !wf) { setState({ busy: false, msg: "", error: "Could not read the workflow." }); return; }
    for (const i of inputs) {
      const n = wf.nodes.find((x) => x.id === i.node);
      if (!n) continue;
      n.data = { ...(n.data || {}), params: { ...(n.data?.params || {}), [i.key]: i.type === "number" ? Number(values[`${i.node}:${i.key}`]) : values[`${i.node}:${i.key}`] } };
    }
    const put = await fetch(`/api/workflows/${workspace}/${workflow.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(wf) });
    const saved = await put.json().catch(() => ({}));
    if (!put.ok) { setState({ busy: false, msg: "", error: saved.error || "Could not save." }); return; }
    if (!run) { setState({ busy: false, msg: "Saved into the graph.", error: "" }); return; }
    const r = await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client: workspace, workflow: workflow.id, stage: "next", mode: "dry-run" }) });
    const data = await r.json().catch(() => ({}));
    setState({ busy: false, msg: r.ok ? (data.note || `Dry run wrote ${data.results?.length || 0} manifest(s). Nothing was spent.`) : "", error: r.ok ? "" : (data.error || "The dry run did not start.") });
  }

  return (
    <form className="tool" onSubmit={(e) => { e.preventDefault(); apply(false); }}>
      {inputs.map((i) => {
        const k = `${i.node}:${i.key}`;
        return (
          <label key={k} className="field">
            <span>{i.label} <small className="muted">{i.nodeLabel}</small></span>
            {i.type === "textarea" ? <textarea rows={4} value={values[k] ?? ""} onChange={(e) => setValues({ ...values, [k]: e.target.value })} />
              : i.type === "select" ? (
                <select value={values[k] ?? ""} onChange={(e) => setValues({ ...values, [k]: e.target.value })}>
                  {(i.options || []).map((o) => <option key={o}>{o}</option>)}
                </select>
              ) : <input type={i.type === "number" ? "number" : "text"} value={values[k] ?? ""} onChange={(e) => setValues({ ...values, [k]: e.target.value })} />}
          </label>
        );
      })}
      {!inputs.length && <p className="muted">This tool exposes no fields yet. Open the canvas and mark fields as tool inputs.</p>}
      <div className="tool-cost">
        <b>{fmtUsd(estimate.usd)}</b> <span className={`basis basis-${estimate.basis}`}>{estimate.basis}</span>
        <small className="muted">{estimate.gpu_seconds ? `${Math.round(estimate.gpu_seconds)}s GPU for a full run` : "No GPU time in this model"}{estimate.unknownItems ? `; ${estimate.unknownItems} per-item step(s) with an unknown count` : ""}</small>
      </div>
      {consent && <p className="notice">This tool uses faces or characters. Owned or consented references only.</p>}
      {gaps.length > 0 && (
        <ul className="plan-list">
          {gaps.map((g, i) => <li key={i} className="plan-blocked"><b>{g.step}</b><small>{g.reason}</small></li>)}
        </ul>
      )}
      {readiness.filter((r) => r.status !== "ready").length > 0 && (
        <p className="muted">Needs setup: {readiness.filter((r) => r.status !== "ready").map((r) => r.label).join(", ")}.</p>
      )}
      {state.error && <p className="error" role="alert">{state.error}</p>}
      {state.msg && <p className="muted" role="status">{state.msg}</p>}
      <div className="creator-actions">
        <Link className="btn btn-quiet" href={`/w/${workspace}/f/${workflow.id}`}>Open on canvas</Link>
        <button type="submit" className="btn" disabled={state.busy}>Save fields</button>
        <button type="button" className="btn btn-primary" disabled={state.busy} onClick={() => apply(true)}>Save and dry-run <small>$0 spent</small></button>
      </div>
    </form>
  );
}
