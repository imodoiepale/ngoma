"use client";

import { fmtUsd } from "../../lib/estimate";

// The plan card, top right: what this graph would cost (with its basis), what stops it running,
// what is waiting on a person, and the budget cap a human set in engine.yaml. Nothing on this
// card runs anything.
export default function PlanCard({ estimate, problems, gaps, plan, consent, pending, budget, onClose, onSelect }) {
  const over = budget != null && estimate.usd > budget;
  return (
    <aside className="panel plancard" aria-label="Plan">
      <div className="inspector-head">
        <h3>Plan</h3>
        <button className="icon-btn" onClick={onClose} aria-label="Close plan">x</button>
      </div>
      <div className="plan-total">
        <b>{fmtUsd(estimate.usd)}</b>
        <span className={`basis basis-${estimate.basis}`}>{estimate.basis === "none" ? "no GPU time" : estimate.basis}</span>
        <small>{estimate.gpu_seconds ? `${Math.round(estimate.gpu_seconds)}s GPU` : ""}{estimate.unknownItems ? ` · ${estimate.unknownItems} per-item step(s) with unknown count` : ""}</small>
      </div>
      <dl className="facts">
        <dt>Budget cap</dt>
        <dd className={over ? "gap-text" : ""}>{fmtUsd(budget ?? 0)}{budget === 0 ? " (nothing live runs until a person raises it)" : over ? " (this plan exceeds it)" : ""}</dd>
        {plan && (<><dt>Steps</dt><dd>{plan.ready} ready, {plan.blocked} blocked{plan.waiting ? `, ${plan.waiting} waiting on you` : ""}</dd></>)}
        {pending?.length ? (<><dt>Picks</dt><dd>{pending.length} waiting</dd></>) : null}
      </dl>
      {consent && <p className="notice">Uses faces or characters. Owned or consented references only; the runner blocks anything else.</p>}
      {problems.length > 0 && (
        <div className="plan-block">
          <h4>Will not save</h4>
          <ul className="plan-list">
            {problems.map((p, i) => <li key={i} className="plan-blocked"><small>{p}</small></li>)}
          </ul>
        </div>
      )}
      {gaps.length > 0 && (
        <div className="plan-block">
          <h4>Not runnable yet</h4>
          <ul className="plan-list">
            {gaps.map((g, i) => (
              <li key={i} className="plan-blocked">
                <button type="button" className="linkish" onClick={() => onSelect?.(g.node)}>{g.step}</button>
                <small>{g.reason}</small>
              </li>
            ))}
          </ul>
        </div>
      )}
      {plan && (
        <ol className="plan-list">
          {plan.steps.map((s) => (
            <li key={s.id} className={`plan-${s.status}`}>
              <button type="button" className="linkish" onClick={() => onSelect?.(s.id)}>{s.label}{s.each ? " (each)" : ""}</button>
              <small>{s.detail}</small>
            </li>
          ))}
        </ol>
      )}
      <p className="muted plan-note">Check only. Nothing runs, spends or publishes from this card.</p>
    </aside>
  );
}
