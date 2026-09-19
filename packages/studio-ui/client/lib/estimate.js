// Cost estimates in USD, mirroring packages/engine/cost.estimate: GPU seconds per unit from
// brands/_presets/engine.yaml times the GPU rate, times variants, times seconds of video
// where the step is priced per second, times items when the node runs once per item. Every
// figure carries its basis: "measured" came from a pod run, "assumed" is a planning figure.
// Pure functions only, so the canvas can price a graph in the browser.

export function estimateNode(kind, spec, params = {}, pricing, opts = {}) {
  const unit = pricing?.seconds_per_unit?.[kind];
  const rate = pricing?.rate?.usd_per_hour || 0;
  if (!unit) {
    return { usd: 0, gpu_seconds: 0, basis: "none", note: `${kind} uses no GPU time in this model`, units: 0 };
  }
  const variants = Math.max(1, Number(opts.variants || params.variants || 1));
  const seconds = Number(opts.seconds || params.seconds || 0);
  let units = unit.per === "second_of_video" ? variants * (seconds || 1) : variants;
  // A carousel is priced per output image: one GPU pass per slide.
  if (kind === "carousel" && Number(params.slides) > 0) units *= Number(params.slides);
  const items = Math.max(1, Number(opts.items || 1));
  units *= items;
  const gpu = Number(unit.seconds) * units;
  return {
    usd: Math.round((gpu / 3600) * rate * 10000) / 10000,
    gpu_seconds: Math.round(gpu * 10) / 10,
    basis: unit.basis || "assumed",
    units,
    items,
    rate: pricing?.rate ? `${pricing.rate.name} $${pricing.rate.usd_per_hour}/h (${pricing.rate.basis})` : "",
  };
}

// Item counts flow from reference folders: a fan-out node iterates the files that reach its
// iterated port. Counts are known before a run only when the folder is on disk; otherwise the
// estimate says "per item" and the total stays a lower bound.
export function itemCountFor(node, wf, byKind, refCounts = {}) {
  if (!node?.data?.each) return 1;
  const port = iteratedPortOf(node, byKind[node.kind]);
  const feeders = wf.edges.filter((e) => e.target === node.id && e.targetHandle === port).map((e) => wf.nodes.find((n) => n.id === e.source)).filter(Boolean);
  let count = 0;
  for (const f of feeders) {
    if (f.kind === "reference-images" || f.kind === "product-photo" || f.kind === "video-clip") {
      const folder = f.data?.params?.folder || f.data?.ref?.path || "";
      const name = folder.split("/").filter(Boolean).pop();
      count += Number(f.data?.ref?.count) || refCounts[folder] || refCounts[name] || 0;
    } else if (f.data?.each) {
      count += itemCountFor(f, wf, byKind, refCounts);
    } else {
      const last = latestResult(f.data?.results);
      count += last?.files?.length || Number(f.data?.variant_count || 1);
    }
  }
  return count || 0;
}

export function iteratedPortOf(node, spec) {
  if (!spec) return null;
  const want = node?.data?.each_port;
  if (want) return spec.inputs.some((p) => p.id === want) ? want : null;
  for (const p of spec.inputs) {
    if (p.optional) continue;
    if (p.type === "image" || p.type === "video" || p.id === "media") return p.id;
  }
  return null;
}

export function latestResult(results) {
  return (results || []).slice().sort((a, b) => String(b.finished || "").localeCompare(String(a.finished || "")))[0] || null;
}

export function estimateWorkflow(wf, catalog, pricing, refCounts = {}) {
  const byKind = Object.fromEntries(catalog.nodes.map((n) => [n.kind, n]));
  const nodes = {};
  let usd = 0, gpu = 0, unknownItems = 0;
  const bases = new Set();
  for (const n of wf.nodes || []) {
    const spec = byKind[n.kind];
    if (!spec) continue;
    const items = n.data?.each ? itemCountFor(n, wf, byKind, refCounts) : 1;
    const est = estimateNode(n.kind, spec, n.data?.params || {}, pricing, {
      variants: n.data?.variant_count, seconds: n.data?.seconds || n.data?.params?.seconds, items: items || 1,
    });
    if (n.data?.each && !items) unknownItems++;
    nodes[n.id] = { ...est, each: !!n.data?.each, itemsKnown: !n.data?.each || items > 0 };
    if (est.basis !== "none") bases.add(est.basis);
    usd += est.usd; gpu += est.gpu_seconds;
  }
  const basis = bases.size === 0 ? "none" : bases.size === 1 ? [...bases][0] : "mixed";
  return { usd: Math.round(usd * 10000) / 10000, gpu_seconds: Math.round(gpu * 10) / 10, basis, nodes, unknownItems, budget_usd: pricing?.budget_usd ?? 0 };
}

export function fmtUsd(v) {
  const n = Number(v || 0);
  if (n === 0) return "$0.00";
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}
