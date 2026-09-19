---
name: workflow-author
description: Use when someone wants a content pipeline or workflow built for a workspace in Director from an idea, a plain-language brief, or by combining existing workflows: "make a workflow for <brand>", "build the pipeline for idea V02", "turn this idea into a workflow", "combine the music video and rollout workflows", "chain these workflows", "what steps would this need", "can the studio do X yet", "run this step for each reference image". Produces a studio canvas workflow (*.studio.json) that the studio UI opens and edits, with every step bound to a real ComfyUI workflow, hosted model or studio module, every missing capability declared as a gap, and fan-out steps spelled <step>@each.
---

# Workflow author

Turns ideas and briefs into **workspace workflows** for the studio canvas, and **combines**
workflows into bigger ones. Repo: `C:\Users\ADMIN\Documents\GitHub\ngoma`. Run with plain
`python` (`uv` is not on PATH here) and `PYTHONIOENCODING=utf-8`.

The canvas (`packages/studio-ui`, run `npm run dev --prefix packages/studio-ui`) and this
author read and write the same files.

## Where things live

| What | Path |
|---|---|
| Node catalogue (the only list of steps) | `packages/studio-ui/catalog/nodes.json` |
| Author and validator | `packages/strategy/workflow_author.py` |
| Workspace scaffold and check | `packages/strategy/workspace.py` |
| Workspace workflows | `brands/<key>/workflows/*.studio.json` |
| One template per business idea | `brands/_templates/workflows/*.studio.json` |
| The 50 ideas and their pipelines | `brands/_business/ideas.yaml` |
| The minimum kit | `brands/_kit/README.md` |

A workspace is any folder in `brands/` that has a `brand.yaml`. The CLI flag is still
`--client <key>`; it takes the workspace key. If the workspace does not exist yet, open it
first:

```bash
python packages/strategy/workspace.py new <key> --name "Display Name" --dry-run
python packages/strategy/workspace.py new <key> --name "Display Name"
```

## Commands

```bash
python packages/strategy/workflow_author.py --list
python packages/strategy/workflow_author.py --idea V02 --client ongea-pesa
python packages/strategy/workflow_author.py --brief "Sheng WhatsApp status ad for a mama mboga" --client ongea-pesa
python packages/strategy/workflow_author.py --combine M01 M04 --client epalle --title "Music video to rollout"
python packages/strategy/workflow_author.py --all-ideas
python packages/strategy/workflow_author.py --check
```

- **`--idea`** expands the idea's pipeline. Idea references inside a pipeline, such as
  M07 = M02 + M03 + M04, expand too.
- **`--brief`** picks steps from the words used, and sets the voiceover language when the
  brief says Sheng, Kiswahili or French.
- **`--combine`** takes idea ids, saved workflow ids for that workspace, or file paths, in
  the order they should run.
- **`--json`** prints the workflow instead of saving it.

The Director (`python packages/engine/cli.py say --client <key> --session <s> --text "..."`)
is the other way a workflow grows, from speech under a profile and a preset; it writes the
same `*.studio.json`. A unified `describe` command that decides between the two routes and
returns a plan card is specified (design spec, Part 2C) and in progress.

## Fan-out: `<step>@each`

A step spelled `<step>@each` in a pipeline or a brief runs once per item on its iterated
input, and the node carries `data.each: true` (`data.each_port` names the port when it is
not the first required image or video input). `workflow_author.is_each(node)` and
`iterated_port(node, cat)` are the helpers every side uses; `split_each` parses the
spelling. Validation refuses `each` on inputs, the brand kit, human decisions and
publishers, requires an image or video input to iterate, requires something feeding it, and
relaxes the pick's "keep k of offered" check when a fan-out feeds the pick. `combine`
preserves the flag. `tests/test_fan_out_contract.py` pins all of it.

The worked case: `reference-images` (the batch), `reference-images` (the persona face),
`character-swap@each` (an alias on `klein-headswap`), `pick`, `carousel@each` with
`slides: 10`, `brand-kit`, `compositor`, `export`. The runner loop that executes it per item
is in progress (design spec, Part 2D).

## How combining works

1. Each part's node ids get a letter prefix (`a`, `b`, ...), so parts never collide.
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
  module. Then run `--check` and `python -m pytest -q`.
- **Consent.** Workflows with dataset, RefMod, face swap, head swap or lip-sync steps carry
  `consent_required: true`. Say so, and use only owned, fictional or released likenesses. A
  real face without a written release is a gap, not a step.
- **Planning only.** Authoring and the canvas's "Check run plan" never run models, spend
  money or publish. Live runs follow the content-studio skill's dry-run and approval rules.
- **Templates are read-only on the canvas.** Make a workspace copy with `--idea`, then edit
  that copy.
- **Workspace before workflow.** `--client` refuses a key without `brands/<key>/brand.yaml`.
  Scaffold with `workspace.py new`, never by hand-copying another workspace's folder.

## Verify

```bash
python packages/strategy/workflow_author.py --check
python packages/strategy/workspace.py check <key>
python -m pytest -q
```

`tests/test_workflow_author.py` proves:
- all 50 ideas author valid workflows;
- gaps are declared;
- type mismatches are caught;
- combining marries media and keeps gaps;
- seeded workspace workflows exist.

`tests/test_fan_out_contract.py` proves the `@each` rules. `tests/test_workspace.py` proves
the scaffold writes a kit `check` accepts and refuses reserved keys.
