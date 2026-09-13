---
name: workflow-author
description: Use when someone wants a content pipeline or workflow built for a client from an idea, a plain-language brief, or by combining existing workflows — "make a workflow for <client>", "build the pipeline for idea V02", "turn this idea into a workflow", "combine the music video and rollout workflows", "chain these workflows", "what steps would this need", "can the studio do X yet". Produces a studio canvas workflow (*.studio.json) that the EPALLE Studio UI opens and edits, with every step bound to a real ComfyUI workflow, hosted model or studio module, and every missing capability declared as a gap.
---

# Workflow author

Turns ideas and briefs into **client workflows** for the studio canvas, and **combines**
workflows into bigger ones. Repo: `C:\Users\inkno\Documents\GitHub\comfy`.

The canvas (`packages/studio-ui`, run `npm run dev --prefix packages/studio-ui`) and this
author read and write the same files.

## Where things live

| What | Path |
|---|---|
| Node catalogue (the only list of steps) | `packages/studio-ui/catalog/nodes.json` |
| Author and validator | `packages/strategy/workflow_author.py` |
| Client workflows | `brands/<client>/workflows/*.studio.json` |
| One template per business idea | `brands/_templates/workflows/*.studio.json` |
| The 50 ideas and their pipelines | `brands/_business/ideas.yaml` |

A client is any folder in `brands/` that has a `brand.yaml`.

## Commands

```bash
uv run --with pyyaml packages/strategy/workflow_author.py --list
uv run --with pyyaml packages/strategy/workflow_author.py --idea V02 --client ongea-pesa
uv run --with pyyaml packages/strategy/workflow_author.py --brief "Sheng WhatsApp status ad for a mama mboga" --client ongea-pesa
uv run --with pyyaml packages/strategy/workflow_author.py --combine M01 M04 --client epalle --title "Music video to rollout"
uv run --with pyyaml packages/strategy/workflow_author.py --all-ideas
uv run --with pyyaml packages/strategy/workflow_author.py --check
```

- **`--idea`** expands the idea's pipeline. Idea references inside a pipeline, such as
  M07 = M02 + M03 + M04, expand too.
- **`--brief`** picks steps from the words used, and sets the voiceover language when the
  brief says Sheng, Kiswahili or French.
- **`--combine`** takes idea ids, saved workflow ids for that client, or file paths, in the
  order they should run.
- **`--json`** prints the workflow instead of saving it.

## How combining works

1. Each part's node ids get a letter prefix (`a`, `b`, …), so parts never collide.
2. The brand kit merges into one node, and so does a brief with identical text.
3. Each part's finished image or video replaces the next part's empty placeholder input.
   These links are marked `married` and animate on the canvas.
4. Only the last part keeps its publish or export step.

## Rules this skill must keep

- **Gaps are shown, never faked.** A step with no backend is a declared gap: LoRA training,
  relight, restore, translate, motion graphics, or any unmapped pipeline word. Tell the user
  what cannot run yet. Do not swap in a different step silently.
- **Only catalogue nodes.** To add a capability, add a node to `nodes.json` that points at a
  real backend: a ComfyUI workflow in `workflows/manifest.json`, a router profile, or a repo
  module. Then run `--check` and `uv run studio.py test`.
- **Consent.** Workflows with dataset, RefMod, face swap or lip-sync steps carry
  `consent_required: true`. Say so, and use only owned or consented likenesses.
- **Planning only.** Authoring and the canvas's "Check run plan" never run models, spend
  money or publish. Live runs follow the content-studio skill's dry-run and approval rules.
- **Templates are read-only on the canvas.** Make a client copy with `--idea`, then edit
  that copy.

## Verify

```bash
uv run --with pyyaml packages/strategy/workflow_author.py --check
uv run studio.py test
```

`tests/test_workflow_author.py` proves:
- all 50 ideas author valid workflows;
- gaps are declared;
- type mismatches are caught;
- combining marries media and keeps gaps;
- seeded client workflows exist.
