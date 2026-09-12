---
chapter: Foundation
title: Persistent RunPod architecture
lesson_type: text
embed_type: null
embed_id: null
references:
  - https://www.youtube.com/watch?v=1uL5-dlYb18
---

# Persistent RunPod architecture

The most expensive mistake in GPU creative work is rebuilding your environment. Weights are
large, custom node trees are fragile, and compiled extensions take real time to build. This
lesson covers a layout that survives.

## Separate the machine from the data

A GPU pod is disposable. A network volume is not. Everything you would hate to lose lives on
the volume; the pod is a temporary engine you attach to it. RunPod network volumes persist
independently of any individual pod, so you can delete or replace a pod and reattach the same
volume. That is what makes this model work.

## Layout

```
/workspace/epalle/
  ComfyUI/        runtime
  models/         persistent model store
  workflows/      reviewed workflow library
  workflow-api/   graphs admitted by the serverless handler
  state/          idempotency and job state
  outputs/        generated results
  cache/          Hugging Face cache and build artefacts
  manifests/      model hashes, pip freeze, node commits
  logs/
```

Two details make the discipline pay off:

- `extra_model_paths.yaml` points ComfyUI at `models/` on the volume, so a fresh pod finds
  every weight already present.
- `manifests/` records a pinned commit per custom-node repo plus a pip freeze. When something
  breaks after an update, you can tell *what* changed.

## Two execution modes

**Development pod.** Interactive. Open ComfyUI in a browser, wire nodes, test at low
resolution, iterate. Billed hourly while running, so stop it when you step away. This is where
you build and where things are allowed to break.

**Serverless endpoint.** Scale-to-zero. Boots a worker on demand, runs one named graph,
returns a result, shuts down. Billed per second of execution. This is where *reviewed* graphs
run repeatably from an API call.

The rule: nothing reaches serverless until it works interactively. Serverless is not a
debugger.

## Capacity is a real constraint

Your volume lives in one data centre, and a pod must run in that same data centre to attach
it. If the region has no free GPU of the type you requested, you wait. The models are not the
bottleneck — the silicon is.

The mitigation is to accept a *list* of GPU types rather than one. If your graphs fit in 40 GB
of VRAM then several card types will serve, and asking for any of them instead of one specific
card dramatically improves your odds of starting. Pin a single type only when a graph
genuinely needs that card's memory or architecture.

Plan for this. It is normal cloud GPU life, not an error state.

## Model integrity

Record size and SHA-256 for every weight, plus the repo revision you pulled it from. Two
reasons: a truncated download produces baffling generation artefacts rather than a clean
error, and a model repo can change under a moving tag. Pin revisions, verify hashes, store
both in the manifest.

## Cost discipline

- Stop the development pod when idle. Storage keeps costing; GPU time should not.
- Keep serverless at minimum zero workers.
- Size storage with real headroom. Video work spills — extracted frames, latents and
  intermediate renders can dwarf the model store, and filling the volume mid-render fails the
  render.
- Know which steps call a paid external API, and default those to off.

## Deliverable

A smoke-tested request that runs end to end on your own endpoint, plus a recovery drill:
delete the pod, create a new one, reattach the volume, confirm models and workflows survived.
Do the drill before you need it.

## Reference viewing

- KiubAI — [Ideogram 4 AI influencers: ComfyUI pipeline and LoRA training on RunPod](https://www.youtube.com/watch?v=1uL5-dlYb18)
