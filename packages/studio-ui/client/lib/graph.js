// Pure graph logic shared by the server (save, plan) and the canvas (live validation).
// Validation mirrors packages/strategy/workflow_author.validate, including the fan-out rules:
// `each` is a boolean; a fan-out node has a comfy, router, python or gap backend; it has a
// required image or video input (or a valid each_port); that port is fed; and a pick fed by a
// fan-out skips the "keep k of offered" check because the item count is a run-time fact.

export const RUN_MODES = ["dry-run", "stage-approval", "auto"];
export const EACH_BACKENDS = new Set(["comfy", "router", "python", "gap"]);
export const EACH_SUFFIX = "@each";

export function splitEach(step) {
  const s = String(step);
  return s.endsWith(EACH_SUFFIX) ? [s.slice(0, -EACH_SUFFIX.length), true] : [s, false];
}

export function isEach(node) {
  return !!(node?.data && node.data.each);
}

export function byKindOf(catalog) {
  return Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
}

// The input port a fan-out node loops over: data.each_port, else the first required image or
// video input. Null when the node has no such port.
export function iteratedPort(node, spec) {
  if (!spec) return null;
  const want = node?.data?.each_port;
  if (want) return spec.inputs.some((p) => p.id === want) ? want : null;
  for (const p of spec.inputs) {
    if (p.optional) continue;
    if (p.type === "image" || p.type === "video" || p.id === "media") return p.id;
  }
  return null;
}

export function canEach(spec) {
  return !!spec && EACH_BACKENDS.has(spec.backend?.kind) && spec.inputs.some((p) => !p.optional && (p.type === "image" || p.type === "video" || p.id === "media"));
}

export function accepts(port, outType, catalog) {
  if (port.id === "media") return catalog.media_ports.accepts.includes(outType);
  return port.type === outType;
}

// Depth-first search; returns the first loop found as a list of node ids, or null.
export function findCycle(nodes, edges) {
  const out = new Map(nodes.map((n) => [n.id, []]));
  for (const e of edges) if (out.has(e.source) && out.has(e.target)) out.get(e.source).push(e.target);
  const state = new Map();
  const path = [];
  const visit = (v) => {
    state.set(v, 1); path.push(v);
    for (const w of out.get(v)) {
      if (state.get(w) === 1) return path.slice(path.indexOf(w)).concat(w);
      if (!state.has(w)) { const f = visit(w); if (f) return f; }
    }
    path.pop(); state.set(v, 2);
    return null;
  };
  for (const v of out.keys()) if (!state.has(v)) { const f = visit(v); if (f) return f; }
  return null;
}

// A decide step that nobody has answered yet. It is waiting, not broken.
export function pendingPicks(wf, catalog) {
  const byKind = byKindOf(catalog);
  return wf.nodes.filter((n) => byKind[n.kind]?.category === "decide" && !(n.data?.picked || []).length).map((n) => n.id);
}

export function validateWorkflow(wf, catalog) {
  const problems = [];
  const byKind = byKindOf(catalog);
  if (!wf || !Array.isArray(wf.nodes) || !Array.isArray(wf.edges)) return ["A workflow needs nodes and links."];
  const ids = new Map(wf.nodes.map((n) => [n.id, n]));
  if (ids.size !== wf.nodes.length) problems.push("Two nodes share an id.");
  const declared = new Set((wf.gaps || []).map((g) => g.node));
  for (const n of wf.nodes) {
    if (n.kind === "unmapped") {
      if (!declared.has(n.id)) problems.push(`${n.id}: an unmapped step must be listed as a gap.`);
      continue;
    }
    const spec = byKind[n.kind];
    if (!spec) { problems.push(`${n.id}: unknown node type ${n.kind}.`); continue; }
    if (spec.backend.kind === "gap" && !declared.has(n.id)) problems.push(`${n.id}: ${spec.label} cannot run yet and must be listed as a gap.`);
    else if (spec.backend.kind === "human" && spec.category !== "decide") problems.push(`${n.id}: only a decide step may wait on a person.`);
    const d = n.data || {};
    if ("each" in d && typeof d.each !== "boolean") {
      problems.push(`${n.id}: each must be true or false.`);
    } else if (isEach(n)) {
      if (!EACH_BACKENDS.has(spec.backend.kind)) problems.push(`${n.id}: a ${spec.backend.kind} step cannot run once per item.`);
      const port = iteratedPort(n, spec);
      if (port === null) {
        problems.push(`${n.id}: runs once per item but has no image or video input to iterate${d.each_port ? ` (each_port ${d.each_port} is not an input)` : ""}.`);
      } else if (!wf.edges.some((e) => e.target === n.id && e.targetHandle === port)) {
        problems.push(`${n.id}: runs once per item but nothing feeds its ${port} port.`);
      }
    }
    if (spec.category === "decide") {
      const k = d.params?.k;
      const feeders = wf.edges.filter((e) => e.target === n.id).map((e) => ids.get(e.source)).filter(Boolean);
      const offered = feeders.reduce((s, f) => s + Number(f.data?.variant_count || 1), 0);
      if (feeders.length && typeof k === "number" && k > offered && !feeders.some((f) => isEach(f))) {
        problems.push(`${n.id}: asks to keep ${k} but only ${offered} candidate(s) feed it.`);
      }
    }
  }
  if (wf.run_mode != null && !RUN_MODES.includes(wf.run_mode)) problems.push(`run_mode must be one of ${RUN_MODES.join(", ")}.`);
  const loop = findCycle(wf.nodes, wf.edges);
  if (loop) problems.push(`Steps feed back into themselves: ${loop.join(" -> ")}.`);
  for (const e of wf.edges) {
    const s = ids.get(e.source), t = ids.get(e.target);
    if (!s || !t) { problems.push(`${e.id}: a link points at a missing node.`); continue; }
    const ss = byKind[s.kind], ts = byKind[t.kind];
    if (!ss || !ts) continue;
    const out = ss.outputs.find((o) => o.id === e.sourceHandle);
    const port = ts.inputs.find((p) => p.id === e.targetHandle);
    if (!out || !port) problems.push(`${e.id}: a link uses a port that does not exist.`);
    else if (!accepts(port, out.type, catalog)) problems.push(`${e.id}: ${out.type} cannot feed ${ts.label} ${port.id}.`);
  }
  return problems;
}

// Gaps are recomputed on save so the file always states what cannot run.
export function computeGaps(wf, catalog) {
  const byKind = byKindOf(catalog);
  const gaps = [];
  for (const n of wf.nodes) {
    if (n.kind === "unmapped") {
      gaps.push({ node: n.id, step: n.data?.step || "unmapped", reason: `No catalogue node runs '${n.data?.step}' yet.` });
      continue;
    }
    const spec = byKind[n.kind];
    if (!spec) continue;
    if (spec.backend.kind === "gap") gaps.push({ node: n.id, step: n.kind, reason: spec.backend.reason });
    for (const p of spec.inputs) {
      if (p.optional) continue;
      if (!wf.edges.some((e) => e.target === n.id && e.targetHandle === p.id)) {
        gaps.push({ node: n.id, step: n.kind, reason: `Needs a ${p.id === "media" ? "image or video" : p.type} input.` });
      }
    }
  }
  return gaps;
}

// The inputs a saved tool exposes: every param of an input node, plus any param another node
// marks as exposed (data.expose = ["slides"]). Weavy's "graph becomes a tool": the same
// workflow, shown as a form with only the fields a colleague needs.
export function toolInputs(wf, catalog) {
  const byKind = byKindOf(catalog);
  const out = [];
  for (const n of wf.nodes) {
    const spec = byKind[n.kind];
    if (!spec) continue;
    const exposed = new Set(Array.isArray(n.data?.expose) ? n.data.expose : []);
    for (const p of spec.params || []) {
      if (spec.category === "inputs" || exposed.has(p.key)) {
        out.push({ node: n.id, kind: n.kind, nodeLabel: spec.label, key: p.key, label: p.label, type: p.type, options: p.options || null, value: n.data?.params?.[p.key] ?? p.default ?? "" });
      }
    }
  }
  return out;
}

// What would happen if this ran. Nothing is executed and nothing is spent.
export function runPlan(wf, catalog) {
  const byKind = byKindOf(catalog);
  const gaps = computeGaps(wf, catalog);
  const steps = wf.nodes.map((n) => {
    const spec = byKind[n.kind];
    const nodeGaps = gaps.filter((g) => g.node === n.id).map((g) => g.reason);
    if (!spec) return { id: n.id, label: n.data?.step || n.kind, status: "blocked", detail: nodeGaps.join(" ") };
    const be = spec.backend;
    const runs = {
      input: "You provide this.",
      brand: "Read from brand.yaml.",
      comfy: `ComfyUI: workflows/${be.workflow}`,
      router: `Hosted model, profile ${n.data?.params?.profile || be.profile}.`,
      python: `Runs ${be.module}.`,
      publish: `Creates a draft through ${be.module}.`,
      human: (n.data?.picked || []).length ? `You kept ${n.data.picked.length}.` : "Waiting for your pick.",
      gap: be.reason,
    }[be.kind];
    const status = nodeGaps.length ? "blocked" : be.kind === "input" ? "input"
      : be.kind === "human" ? ((n.data?.picked || []).length ? "ready" : "waiting") : "ready";
    return { id: n.id, label: spec.label, status, detail: nodeGaps.length ? nodeGaps.join(" ") : runs, consent: !!spec.consent, backend: be.kind, each: isEach(n) };
  });
  return {
    steps,
    ready: steps.filter((s) => s.status === "ready").length,
    blocked: steps.filter((s) => s.status === "blocked").length,
    waiting: steps.filter((s) => s.status === "waiting").length,
    consent: steps.some((s) => s.consent),
    note: "Check only. Nothing runs, spends money or publishes from this screen.",
  };
}

// Catalogue nodes that could continue from an output of this type and produce a set, for the
// "Continue with" suggestion under a completed step. Carousel first when it fits.
export function continuationsFor(outType, catalog, { allowAdult = false } = {}) {
  const out = [];
  for (const n of catalog.nodes) {
    if (n.adult && !allowAdult) continue;
    if (!["generate", "edit"].includes(n.category)) continue;
    const port = n.inputs.find((p) => !p.optional && (p.type === outType || (p.id === "media" && catalog.media_ports.accepts.includes(outType))));
    if (!port) continue;
    out.push({ kind: n.kind, label: n.label, port: port.id, each: canEach(n), params: n.params || [], consent: !!n.consent, backend: n.backend.kind });
  }
  out.sort((a, b) => (a.kind === "carousel" ? -1 : b.kind === "carousel" ? 1 : a.label.localeCompare(b.label)));
  return out;
}
