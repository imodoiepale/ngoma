"use client";

import { useRouter } from "next/navigation";

// Readiness filter, search and workspace scope for Explore. Plain links and a form, so the URL
// carries the state and the page stays a server component.
export default function ExploreFilter({ counts, status, q, ws, workspaces }) {
  const router = useRouter();
  const go = (patch) => {
    const p = new URLSearchParams();
    const next = { status, q, ws, ...patch };
    for (const [k, v] of Object.entries(next)) if (v) p.set(k, v);
    router.push(`/explore${p.toString() ? `?${p}` : ""}`);
  };
  return (
    <form className="create-form" style={{ gridTemplateColumns: "auto minmax(0,1fr) auto", marginBottom: 6 }} onSubmit={(e) => { e.preventDefault(); go({ q: new FormData(e.currentTarget).get("q") }); }}>
      <span className="pick-list" role="radiogroup" aria-label="Readiness">
        {[["", `All ${counts.ready + counts.needsSetup + counts.gap}`], ["ready", `Ready ${counts.ready}`], ["needs-setup", `Needs setup ${counts.needsSetup}`], ["gap", `Gap ${counts.gap}`]].map(([v, l]) => (
          <button key={v} type="button" role="radio" aria-checked={status === v} className={`pick${status === v ? " is-on" : ""}`} onClick={() => go({ status: v })}>{l}</button>
        ))}
      </span>
      <input name="q" defaultValue={q} placeholder="Search steps and templates" aria-label="Search" />
      <select value={ws} onChange={(e) => go({ ws: e.target.value })} aria-label="Scope to a workspace">
        <option value="">Any workspace</option>
        {workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}{w.adult ? " (18+ enabled)" : ""}</option>)}
      </select>
    </form>
  );
}
