# Batches: N references in, one transform per item, one set per result

A **batch** is a reference folder. Any single-image step can run once per item in it by
marking the node `each` (`data.each: true`, spelled `<step>@each` in a pipeline, a brief or the
describe bar). The runner loops; the author, the canvas and the describe parser only mark the
node. This document is the runtime half of the contract in
`docs/superpowers/specs/2026-09-20-general-creative-studio-design.md` (Part 2D and W3).

The worked case: fifty owned reference images of one character go through `character-swap@each`
(one head swap per image, the persona's face bound once to every item), then `carousel@each`
with `slides: 10` (ten pose slides per swapped image), then the compositor (logo and exact copy
on every slide) and export, which lands fifty folders of ten slides, one folder per post.

Code: `packages/engine/runner.py` (`_run_each`, `upstream_items`, `rights_gate`),
`packages/engine/cost.py`, `packages/engine/edit.py` (compositor, claim check, hooks, transcribe,
grouped export). Template: `brands/_templates/workflows/batch-character-to-carousels.studio.json`.
Tests: `tests/test_fan_out_runtime.py`, `tests/test_engine_runner.py`.

## What the runner does with `each`

1. **Items.** The items are the files that reach the node's iterated port
   (`workflow_author.iterated_port`: `data.each_port`, else the first required image or video
   input) after `upstream_items`: a reference folder gives its files, a pick gives only its
   picks, an upstream fan-out gives the files of its *completed* items. Other ports bind once
   and are shared by every item (the persona's face reference is uploaded once).
2. **Seeds.** Item `i`, variant `v` gets `base_seed + i * variants + v`, where `base_seed` is
   `data.seed` or a hash of the node id. Rerunning one item reproduces it.
3. **Submissions.** One ComfyUI job per item per variant. Queued is not success: an item is
   `completed` only when history shows outputs and they were fetched.
4. **Group.** Every item carries `group`: the index of the source item it descends from. A
   swap over a folder gives groups `0..N-1`; a carousel fed by that swap inherits the group of
   the image it received; the compositor keeps the group of every image it dresses; export
   uses it for the post layout. A pick after a fan-out passes the group along with the file.
5. **Status.** `completed` when every item completed; `partial` when some failed (downstream
   receives the completed items, the manifest names the failed ones in `failed` and `detail`);
   `error` when none did. After `EACH_STOP_AFTER` (3) consecutive failures the rest are marked
   `skipped` and nothing more is submitted: three failures in a row is a broken pod, not three
   bad images.
6. **Cap.** `max_items` in `brands/_presets/engine.yaml` (default 100). More items than that on
   the iterated port blocks the node with a note instead of submitting; split the folder or
   raise the cap on purpose.
7. **Retry.** `data.retry_items: [indices]` restricts a run to those items; their seeds are the
   same as in the full run.

Stage-less workflows (authored templates) run as one stage called `all`; a workflow with
`stages` runs as before. Inputs and the brand kit are resolved from disk before any stage runs.

## Layout on disk

```
brands/<ws>/runs/<workflow>/<node>/<run>/
  manifest.json                    the result below
  inputs/                          converted inputs, if the port map asked for a conversion
  items/<index>/<files>            one folder per item (fan-out nodes)

brands/<ws>/runs/<workflow>/<export node>/<run>/export/
  posts/<group>/slide-01.png       one folder per post, slides numbered within the post
  posts/<group>/slide-02.png
  posts.json                       {layout, posts: {group: [slide files]}}
```

Files that never passed through a fan-out have no group; export then copies them flat, as it
always did.

## The manifest of an `each` run

```json
{
  "run_id": "r-20260920-011636-aracter-swap",
  "workflow": "batch-red-dress-carousels",             // the studio workflow id
  "node": "swap.character-swap",
  "kind": "klein-headswap",
  "each": true,
  "status": "dry-run | completed | partial | error | blocked",
  "backend": "pod",
  "comfy_workflow": "icekiub/I2I_no_lora_faceswap_subs.json",
  "each_port": "image",
  "bindings": {"face": "brands/epalle/references/persona/face.png"},   // shared by every item
  "item_count": 3,                                      // items on the port (before retry_items)
  "items": [
    {"index": 0, "group": "0", "input": "brands/epalle/references/red-dress/look-a.png",
     "from": "refs.batch", "seeds": [5790594], "status": "completed",
     "files": ["brands/epalle/runs/.../items/0/p1.png"], "sha256": ["..."], "prompt_ids": ["p1"],
     "uploaded": "studio/look-a.png", "gpu_seconds_actual": 11.8}
  ],
  "layout": "items/<index>/",
  "seeds": [5790594, 5790595, 5790596],                 // every item's seeds, flattened
  "files": ["..."], "sha256": ["..."], "groups": ["0", "1", "2"],   // completed items, flattened, parallel
  "failed": [], "detail": "", "prompt_ids": ["p1", "p2", "p3"],
  "cost_estimate": {"usd": 0.0164, "gpu_seconds": 36.0, "basis": "assumed", "items": 3,
                    "per_item_gpu_seconds": 12.0, "per": "image", "formula": "12 s x 1 unit(s) x 3 item(s)",
                    "rate": "A100 80GB $1.64/h (assumed)"},
  "gpu_seconds_actual": 36.2, "log": ["set image: ..."],
  "rights_warning": "...",                              // dry runs only, when a collection has no collection.json
  "started": "...", "finished": "...", "note": "3 of 3 item(s) completed"
}
```

In a dry run `items[].status` is `dry-run`, `files` are empty and an item fed by an upstream
dry run has a placeholder input such as `<swap.character-swap#1>`; the count is still exact
because the reference folder is on disk and every dry-run result records its items. For the
carousel the estimate also carries `slides`.

Plain (non-`each`) manifests keep their shape, plus `each: false`, `comfy_workflow` (the
`workflow` key is now always the studio workflow id) and `cost_estimate.items = 1`. Local steps
that keep groups (compositor) record `groups` parallel to `files`; their dry runs record
`expected: {files, groups}`. Export records `layout` and `posts`.

`run_stage` returns `cost_estimate` totals for the stage (`usd`, `gpu_seconds`, `items`,
`basis`) and, per result, `each`, `items`, `item_count`, `failed`, `groups`; `cli.py run` prints
that JSON, so a dry run shows the cost before anything is approved.

## Cost

```
estimate = seconds_per_unit[kind].seconds x units x items
units    = variants                       (per: image, the default)
         = variants x seconds_of_video    (per: second_of_video)
         = variants x slides              (per: slide, the carousel)
```

`engine.yaml` keys: `gpu` (rate key), `budget_usd`, `max_items`, and `seconds_per_unit.<kind>`
with `seconds`, `basis: measured | assumed`, optional `per` and `source`. New entries:
`klein-headswap` 12 s, `klein-i2i` 12 s, `faceswap` 15 s (assumed) and `carousel` now `per: slide`.
Fifty images through `wardrobe@each` then `carousel@each` with ten slides is
`50 x 12 + 50 x 10 x 10 = 5,600` GPU seconds, about 1.6 GPU hours at the A100 rate, and the
estimate says `assumed` until a pod run replaces the figure.

The control-plane task for a stage carries the total over every item (`estimate.items`), so
the approval reads "3 item(s), est $0.02, assumed" and never a per-item surprise. Budget
`budget_usd` still caps everything.

## The rights gate

A step the catalogue flags `consent: true` (`klein-headswap` alias `character-swap`, `klein-i2i`,
`faceswap`, `h3-reference-image`, ...) consumes a face or character reference. Before it runs,
the runner checks every `reference-images` collection upstream of it, at any distance:

- `collection.json` must say `use: data` (a `study` or `inspiration` collection informs the
  grammar, it never feeds a model), and `rights: owned | licensed | fictional` (or
  `fictional: true`).
- A real person (`real_person: true`, or `subject` / `likeness` naming a real person) needs a
  written release recorded as `consent: true`, ideally with `release: <path>`. Without it the
  swap is refused: "collection X is a real person without a written release ...".
- No `collection.json` at all: a dry run proceeds and records `rights_warning`; a live run
  blocks. When the director planned the workflow it attached the brief's rights to the input
  node (`data.ref`), and that record is used in place of a missing file.

The block is a node result with `status: blocked`, `reason: rights` and the message in `note`;
nothing is submitted and the stage is not ok. The fixture `brands/epalle/references/red-dress`
(owned, fictional persona) passes.

## Local steps

`runner.LOCAL_STEPS` now also runs `compositor`, `claim-check`, `hooks` and `transcribe` on this
machine, deterministically and without a model:

- **compositor**: `edit.composite_batch` places the brand's logo master and the exact copy
  (line 1 headline, line 2 subhead, line 3 call to action from the `copy` port; attribution and
  disclosure from `brand.yaml`) on every image with `packages/compositor/compositor.py`, keeping
  each image's group and numbering slides within a post. It needs `palette.measured` with
  `ground`, `surface`, `accent`, `hairline` (a kit that names its colours differently gets the
  roles by luminance, and the manifest says so) and `logo.master` with `min_width_pct > 0`; a
  kit that declares no mark to place (EPALLE) blocks with that reason.
- **claim-check**: fixed rules for money promises, guarantees, risk-free and instant-credit
  claims, superlatives and health claims, plus `claim_safety.banned_phrases` from `brand.yaml`.
  A flag blocks the node and everything after it; a person rewrites the copy.
- **hooks**: `count` opening lines from fixed patterns on the brief's subject, seeded by the
  node; the claim check still applies downstream.
- **transcribe**: a sidecar `<clip>.txt` or `.srt` wins; otherwise faster-whisper when it is
  installed; otherwise the node blocks and says so. Never a hosted API.

Text made by a step (`result.text`) feeds the next text port the same way a brief's
`params.text` does.

## Port maps for the swap steps

`workflows/icekiub/I2I_no_lora_faceswap_subs.ports.json` (`klein-headswap`: image -> LoadImage 11,
face -> LoadImage 16, prompt 13, negative 12, seed KSampler 31, count EmptyLatentImage 10,
output PreviewImage 2), `Image_to_image_Klein_edit_-_Icekiub_v1.5.ports.json` (`klein-i2i`:
image -> LoadImage 11, prompt 13, negative 12, seed 31, count 10, output PreviewImage 2; the
character is a LoRA plus LoadImage 16, set by hand) and
`QWEN_ICY_Faceswap_-_SUBS_-_Icekiub_v1.ports.json` (`faceswap`: image -> LoadImage 789,
face -> LoadImage 788, prompt TextEncodeQwenImageEditPlus 174, negative 111, seed FaceDetailer
722 [3], output SaveImage 821). Two of the three graphs have a folder loader
(`LoadImageListFromDir //Inspire`) behind a switch; the maps bind the single-image path and let
the runner loop, because the folder loader reads the pod's disk and would hide the item list,
the seeds and the groups from the manifests. `cli.py ports-check` covers all three.

## Limits

- Items run one after another on one pod; no parallel submissions.
- `max_items` is a hard cap per node, not per workflow.
- A `partial` node counts as finished for `--stage next`; rerun it with `retry_items` to fill
  the gaps, or pick the good items and continue.
- `klein-i2i` is `adult: true` in the catalogue and needs review before it is offered generally;
  the carousel depends on the Klein 9B licence (BLOCKERS 3).
- The compositor cannot dress a kit with no mark to place; the pipeline then ends at export
  with the raw slides.
