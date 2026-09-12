# epalle-nodes — custom ComfyUI node pack (not yet written)

Deliberately empty. Planned nodes, from the Phase 4 design:

- brief → `CR Prompt List` expander
- brand-kit applier (palette + negative prompt injection from `brand.yaml`)
- compositor bridge (hand a render straight to `packages/compositor`)
- output-manifest emitter (sha256 + campaign id, for `packages/publish`)

**Why a new pack rather than extending `matrix-power-nodes`:** its `nodes/*.py` and
`_core/runtime.py` are compiler-generated ("regenerate instead of hand-editing"), the
compiler is not in that repo, and its CI asserts against generated constants. A
hand-authored node there would be overwritten on the next regeneration. See
`docs/LICENSING.md` and `packages/library/node_pack_sources.yaml`.

Pattern to follow when writing these: one module per node, each self-registering with its
own `NODE_CLASS_MAPPINGS`, `async def execute`, and a CPU-safe import guard
(`try: import folder_paths / except ModuleNotFoundError`) so the tests run without ComfyUI.
