"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { fmtUsd } from "../lib/estimate";
import ReferenceIntake from "./refs/ReferenceIntake";
import { purposeForRole } from "./refs/RefStack";

// "Describe what you want" on Home and on a workspace page. Plan first (POST /api/describe,
// mode plan), show the plan card from the contract, then Create (mode create) opens the canvas
// with the new workflow. If the describe route is not there yet, Create falls back to the
// author's brief mode and opens the canvas with the sentence in its describe bar, where the
// graph is drafted locally.
export default function CreateBar({ workspaces, workspace, initialText = "" }) {
  const router = useRouter();
  const [ws, setWs] = useState(workspace || workspaces[0]?.id || "");
  const [text, setText] = useState(initialText);
  const [answers, setAnswers] = useState({});
  const [state, setState] = useState({ busy: false, error: "", engine: "unknown", data: null });
  const [intake, setIntake] = useState(null);

  async function call(mode, extra = answers) {
    const res = await fetch("/api/describe", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workspace: ws, text: text.trim(), mode, answers: extra }) });
    if (res.status === 404 || res.status === 501) return { offline: true };
    const data = await res.json().catch(() => ({}));
    if (res.status >= 500) return { offline: true, detail: data.error };
    return { ok: res.ok, data };
  }

  async function plan(extra) {
    if (text.trim().length < 3 || !ws) return;
    setState((s) => ({ ...s, busy: true, error: "" }));
    try {
      const r = await call("plan", extra);
      if (r.offline) { setState({ busy: false, error: r.detail ? `Engine error: ${r.detail}` : "", engine: "offline", data: null }); return; }
      setState({ busy: false, error: r.ok ? "" : (r.data.error || "The describe engine did not answer."), engine: "online", data: r.ok ? r.data : null });
    } catch (e) {
      setState({ busy: false, error: "", engine: e instanceof TypeError ? "offline" : "online", data: null });
    }
  }

  async function create() {
    if (text.trim().length < 3 || !ws) return;
    setState((s) => ({ ...s, busy: true, error: "" }));
    try {
      const r = await call("create");
      if (!r.offline) {
        if (!r.ok) { setState((s) => ({ ...s, busy: false, error: r.data.error || "Could not create the workflow." })); return; }
        if (r.data.id) { router.push(`/w/${ws}/f/${r.data.id}`); return; }
        setState((s) => ({ ...s, busy: false, error: "The engine returned a plan without a workflow id." })); return;
      }
    } catch { /* fall through to the author */ }
    const res = await fetch("/api/author", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "brief", client: ws, brief: text.trim(), title: "" }) });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { setState((s) => ({ ...s, busy: false, engine: "offline", error: data.error || "Neither the describe engine nor the author answered. Open a workspace and start from the canvas." })); return; }
    router.push(`/w/${ws}/f/${data.id}?describe=${encodeURIComponent(text.trim())}`);
  }

  const d = state.data;
  const steps = d?.plan?.steps || [];
  return (
    <section className="create" aria-label="Describe what you want to make">
      <form className="create-form" onSubmit={(e) => { e.preventDefault(); plan(); }}>
        {!workspace && (
          <select value={ws} onChange={(e) => setWs(e.target.value)} aria-label="Workspace">
            {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
        )}
        {workspace && <span className="chip"><span className="client-swatch" aria-hidden />{workspaces.find((w) => w.id === workspace)?.name || workspace}</span>}
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Describe what you want to make: a carousel of 10 slides for each of my 50 reference images" aria-label="Describe what you want to make" />
        <span style={{ display: "flex", gap: 8 }}>
          <button type="submit" className="btn" disabled={state.busy || text.trim().length < 3}>Plan</button>
          <button type="button" className="btn btn-primary" disabled={state.busy || text.trim().length < 3} onClick={create}>Create on canvas</button>
        </span>
      </form>
      {state.error && <p className="error" role="alert">{state.error}</p>}
      {state.engine === "offline" && (
        <p className="create-offline">Describe engine offline: /api/describe is not available yet. Create on canvas still works; the canvas drafts the steps locally from the catalogue.</p>
      )}
      {d && (
        <div className="create-plan" role="status">
          {d.reply && <p className="muted" style={{ margin: 0 }}>{d.reply}</p>}
          {steps.length > 0 && (
            <div className="plan-steps">
              {steps.map((s, i) => (
                <span key={i} style={{ display: "contents" }}>
                  {i > 0 && <span className="plan-arrow" aria-hidden>to</span>}
                  <span className={`plan-step${s.status === "gap" ? " is-gap" : ""}`} title={s.status}>
                    <i style={{ background: s.status === "ready" ? "var(--ready)" : s.status === "gap" ? "var(--gap)" : "var(--setup)" }} />
                    {s.kind}{s.each ? <em>each</em> : null}{s.params?.slides ? <small className="muted">{s.params.slides} slides</small> : null}
                  </span>
                </span>
              ))}
            </div>
          )}
          <div className="card-foot">
            {d.plan?.estimate && <span>Estimate {fmtUsd(d.plan.estimate.usd)} <i className="basis">{d.plan.estimate.basis}</i>{d.plan.estimate.items ? `, ${d.plan.estimate.items} items` : ""}</span>}
            {d.plan?.consent_required && <span className="chip chip-consent">Consent required</span>}
            {d.plan?.gaps?.length ? <span className="chip chip-gap">{d.plan.gaps.length} gap(s)</span> : null}
            {d.route && <span className="chip">{d.route}</span>}
          </div>
          {Array.isArray(d.plan?.inputs) && d.plan.inputs.length > 0 && (
            <div className="plan-inputs">
              {d.plan.inputs.map((inp, i) => {
                const key = inp.param || "collection";
                return (
                  <div key={`${inp.node}-${i}`} className={`plan-input${answers[key] ? " is-bound" : ""}`}>
                    <span className="plan-input-text">
                      <b>{inp.prompt || `${inp.kind || "references"} for ${inp.node}`}</b>
                      <small>{inp.role ? `${inp.role}. ` : ""}{inp.expected_count ? `About ${inp.expected_count} ${inp.kind === "video" ? "clips" : "images"}.` : ""}{answers[key] ? ` Using ${answers[key]}.` : ""}</small>
                    </span>
                    {(inp.options || []).length > 0 && !answers[key] && (
                      <span className="pick-list">{inp.options.slice(0, 4).map((o) => <button key={String(o)} type="button" className="pick" onClick={() => { const a = { ...answers, [key]: String(o), collection: String(o) }; setAnswers(a); plan(a); }}>{String(o)}</button>)}</span>
                    )}
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => setIntake({ mode: "pick", purpose: purposeForRole(inp.role, inp.kind), expected: { kind: inp.kind === "video" ? "video" : "image", count: inp.expected_count, prompt: inp.prompt }, key })}>{answers[key] ? "Change" : "Choose or add"}</button>
                  </div>
                );
              })}
            </div>
          )}
          {(d.questions || []).map((q) => (
            <div key={q.key} className="describe-q">
              <span className="muted">{q.prompt}</span>
              <span className="pick-list">
                {(q.options || []).map((o) => (
                  <button key={String(o)} type="button" className={`pick${answers[q.key] === o ? " is-on" : ""}`} onClick={() => { const a = { ...answers, [q.key]: o }; setAnswers(a); plan(a); }}>{String(o)}</button>
                ))}
              </span>
            </div>
          ))}
          {(d.continuations || []).length > 0 && (
            <p className="muted" style={{ margin: 0 }}>Offered after stage one: {d.continuations.map((c) => `${c.step}${c.each ? " for each" : ""}${c.params?.slides ? ` (${c.params.slides} slides)` : ""}`).join(", ")}.</p>
          )}
        </div>
      )}
      {intake && (
        <ReferenceIntake workspace={ws} initial={intake} onClose={() => setIntake(null)}
          onDone={(col) => { const a = { ...answers, [intake.key]: col.name, collection: col.name }; setAnswers(a); setIntake(null); plan(a); }} />
      )}
    </section>
  );
}
