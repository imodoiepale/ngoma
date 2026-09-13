import Link from "next/link";

// A workflow at a glance: its chain of steps as coloured beads, one per node, coloured by
// what each step produces.
export function WorkflowTile({ href, wf, catalog, compact = false }) {
  const byKind = Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
  const colour = (kind) => {
    const spec = byKind[kind];
    if (!spec || spec.backend.kind === "gap") return "var(--gap)";
    const type = spec.outputs[0]?.type || "post";
    return catalog.types[type]?.color || "var(--muted)";
  };
  return (
    <Link href={href} className={`tile${compact ? " tile-compact" : ""}`}>
      <span className="tile-title">{wf.title}</span>
      <span className="beads" aria-hidden>
        {wf.kinds.map((k, i) => (
          <i key={i} style={{ background: colour(k) }} />
        ))}
      </span>
      <span className="tile-foot">
        <span>{wf.nodes} steps</span>
        {wf.combined && <span className="chip">Combined</span>}
        {wf.gaps > 0 && <span className="chip chip-gap">{wf.gaps} not runnable yet</span>}
        {wf.consent && <span className="chip chip-consent">Needs consent</span>}
      </span>
    </Link>
  );
}
