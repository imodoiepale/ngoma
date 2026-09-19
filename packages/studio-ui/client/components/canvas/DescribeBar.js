"use client";

import { useEffect, useRef, useState } from "react";
import { draftFromText } from "./localDraft";
import { fmtUsd } from "../../lib/estimate";

// The describe bar on the canvas. One sentence goes to POST /api/describe (contract in the
// design spec, route owned by W2): { workspace, text, mode, answers, workflow }. The answer's
// workflow, plan, continuations, questions, route and reply come back; the canvas draws the
// new steps as proposed nodes until you accept them. When the route is not there (404) the
// bar says so and drafts locally from the catalogue so the graph still grows.
export default function DescribeBar({ workspace, workflowId, catalog, allowAdult, onProposal, initialText = "", disabled, onIntake, refsByName = {} }) {
  const [text, setText] = useState(initialText);
  const [busy, setBusy] = useState(false);
  const [engine, setEngine] = useState("unknown"); // unknown | online | offline
  const [reply, setReply] = useState("");
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState("");
  const input = useRef(null);

  useEffect(() => { if (initialText) setTimeout(() => input.current?.focus(), 50); }, [initialText]);

  async function describe(mode = "plan", extraAnswers = answers) {
    const t = text.trim();
    if (!t || busy) return;
    setBusy(true); setError(""); setReply("");
    try {
      const res = await fetch("/api/describe", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace, text: t, mode, answers: extraAnswers, workflow: workflowId || undefined }),
      });
      if (res.status === 404 || res.status === 501) throw Object.assign(new Error("offline"), { offline: true });
      const data = await res.json().catch(() => ({}));
      if (res.status >= 500) throw Object.assign(new Error(data.error || "engine error"), { offline: true, detail: data.error });
      if (!res.ok) { setEngine("online"); setError(data.error || "The describe engine did not answer."); return; }
      setEngine("online");
      setReply(data.reply || "");
      setQuestions(Array.isArray(data.questions) ? data.questions : []);
      setPlan(data.plan || null);
      onProposal?.({ source: "engine", text: t, ...data });
    } catch (e) {
      if (e?.offline || e instanceof TypeError) {
        setEngine("offline");
        const d = draftFromText(t, catalog, { allowAdult });
        setReply(e.detail ? `Engine error: ${e.detail} ${d.reply}` : d.reply);
        setPlan(null);
        setQuestions([]);
        if (d.steps.length) onProposal?.({ source: "local", text: t, steps: d.steps, reply: d.reply, count: d.count, collection: d.collection });
      } else {
        setError(String(e.message || e));
      }
    } finally {
      setBusy(false);
    }
  }

  // A reference input answers under its param name and under `collection`, the key the
  // author reads for "which folder did you mean".
  function answer(key, value, isRef = false) {
    const next = { ...answers, [key]: value, ...(isRef ? { collection: value } : {}) };
    setAnswers(next);
    describe("plan", next);
  }

  return (
    <div className="describe" aria-label="Describe what you want">
      {(reply || error || questions.length > 0 || plan) && (
        <div className="describe-reply" role="status">
          {error && <p className="error">{error}</p>}
          {reply && <p>{reply}</p>}
          {plan?.estimate && (
            <p className="muted">Estimate {fmtUsd(plan.estimate.usd)} <i>{plan.estimate.basis}</i>{plan.estimate.items ? `, ${plan.estimate.items} items` : ""}{plan.consent_required ? ". Consent required." : ""}</p>
          )}
          {Array.isArray(plan?.inputs) && plan.inputs.length > 0 && (
            <div className="plan-inputs">
              {plan.inputs.map((inp, i) => {
                const key = inp.param || "collection";
                const bound = answers[key] ? refsByName[answers[key]] : null;
                return (
                  <div key={`${inp.node}-${inp.param}-${i}`} className={`plan-input${bound ? " is-bound" : ""}`}>
                    <span className="plan-input-text">
                      <b>{inp.prompt || `${inp.kind || "references"} for ${inp.node}`}</b>
                      <small>{inp.role ? `${inp.role}. ` : ""}{inp.expected_count ? `About ${inp.expected_count} ${inp.kind === "video" ? "clips" : "images"}.` : ""}{bound ? ` Using ${bound.name} (${bound.count}).` : ""}</small>
                    </span>
                    {(inp.options || []).length > 0 && !bound && (
                      <span className="pick-list">
                        {inp.options.slice(0, 4).map((o) => <button key={String(o)} type="button" className="pick" onClick={() => answer(key, String(o), true)}>{String(o)}</button>)}
                      </span>
                    )}
                    {onIntake && <button type="button" className="btn btn-primary btn-sm" onClick={() => onIntake(inp, (col) => answer(key, col.name, true))}>{bound ? "Change" : "Choose or add"}</button>}
                  </div>
                );
              })}
            </div>
          )}
          {questions.map((q) => (
            <div key={q.key} className="describe-q">
              <span>{q.prompt}</span>
              <span className="pick-list">
                {(q.options || []).map((o) => (
                  <button key={String(o)} type="button" className={`pick${answers[q.key] === o ? " is-on" : ""}`} onClick={() => answer(q.key, o)}>{String(o)}</button>
                ))}
                {!q.options?.length && <input className="describe-answer" placeholder="Type an answer and press Enter" onKeyDown={(e) => { if (e.key === "Enter") answer(q.key, e.currentTarget.value); }} aria-label={q.prompt} />}
              </span>
            </div>
          ))}
        </div>
      )}
      <form className="describe-form" onSubmit={(e) => { e.preventDefault(); describe("plan"); }}>
        <span className={`engine-dot engine-${engine}`} title={engine === "offline" ? "Describe engine offline: drafting locally" : engine === "online" ? "Describe engine online" : "Describe engine not contacted yet"} aria-hidden />
        <input ref={input} value={text} onChange={(e) => setText(e.target.value)} disabled={disabled || busy}
          placeholder="Describe what you want: change the character in my 50 reference images to our persona, then make a carousel of 10 slides for each"
          aria-label="Describe what you want to make" />
        <button type="submit" className="btn btn-primary" disabled={disabled || busy || text.trim().length < 3}>{busy ? "Thinking" : "Propose"}</button>
      </form>
      {engine === "offline" && <p className="describe-offline">Describe engine offline: /api/describe is not available yet. Steps are drafted locally from the catalogue; nothing is saved until you add them and press Save.</p>}
    </div>
  );
}
