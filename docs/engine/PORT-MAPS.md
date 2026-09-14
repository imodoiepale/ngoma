# Port maps: where studio inputs land in a ComfyUI workflow

A **port map** is a hand-written JSON file that sits next to a workflow (`<name>.ports.json`
beside `<name>.json`). It tells the runner which ComfyUI node and widget holds each studio input
(image paths, prompt, negative prompt, seed, batch count) and which node saves the output. Nothing
in the engine guesses node ids at run time: if a map does not name a node, the runner cannot drive
that port.

Code: `packages/engine/ports.py`. Check: `uv run --quiet --with pyyaml python packages/engine/cli.py ports-check`
(or `tests/test_engine_ports.py`).

## Schema

```json
{
  "workflow": "icekiub/Any_Clothes_9B_-_Subs_-_Icekiub_V1.3.json",
  "sha256":   "<sha256 of the workflow bytes = workflows/manifest.json entry .sha256>",
  "format":   "ui" | "api",
  "inputs":   {"<studio port id>": {"node": "15", "class": "LoadImage", "field": "image", "widget_index": 0, "note": "..."}},
  "prompt":   {"node": "6",  "class": "CLIPTextEncode",   "field": "text",       "widget_index": 0},
  "negative": {"node": "..", "class": "CLIPTextEncode",   "field": "text",       "widget_index": 0},
  "seed":     {"node": "3",  "class": "KSampler",         "field": "seed",       "widget_index": 0},
  "count":    {"node": "9",  "class": "EmptyLatentImage", "field": "batch_size", "widget_index": 2},
  "outputs":  {"<studio output id>": {"node": "4", "class": "SaveImage", "kind": "image", "note": "..."}},
  "unknown":  ["<port id>: why it could not be mapped"],
  "notes":    ["anything a human must do before the workflow runs as mapped"]
}
```

- `node` is always a string. UI-format ids can live in `definitions.subgraphs[].nodes` too.
- `widget_index` (UI only) indexes that node's `widgets_values` list. Nodes whose `widgets_values`
  is a dict (VHS_LoadVideo, VHS_VideoCombine) omit it; `field` is the dict key.
- `field` is the ComfyUI input name. For API-format graphs it is the key in `inputs`.
- If a value is wired in from another node, the map points at the node that **owns the widget**
  (e.g. `PrimitiveStringMultiline`, `CR Prompt List`), not the consumer.
- `negative`, `seed`, `count` are optional. `unknown` must list every required studio port that is
  not in `inputs`, prefixed with the port id and a colon.

`validate_port_maps(catalog)` checks, for each kind in `ENGINE_KINDS`: the map exists and parses,
`sha256` equals the manifest entry, every referenced node exists with the stated class, every UI
`widget_index` is in range, every API `field` exists, every required studio port is mapped or
declared unknown, and `outputs` is not empty.

`bind(graph, pm, bindings)` returns a deep copy with the values written in and a change log; keys
the map does not cover are logged as `skipped <key>: ...`, never dropped silently.

## Writing one for a new workflow

1. Register the workflow so `workflows/manifest.json` has its `sha256`.
2. Dump the node list (id, type, title, `widgets_values`, linked inputs) and trace the links from the
   sampler back to the loaders, and from the final decode forward to the save node. Bypassed nodes
   (`mode: 4`) still count as existing but will not run; say so in `notes`.
3. For each studio port of the catalogue node (`packages/studio-ui/catalog/nodes.json`), name the
   loader node. Never invent an id: if there is no node for a port, write it into `unknown`.
4. Prefer the **final** save node (after loops, de-rope, upscale), and name the previews/side-by-sides
   in its `note`.
5. Run `ports-check`. Whenever the workflow bytes change, re-read the map and update `sha256`.

## Maps written

Studio ports come from the catalogue. "-" means the workflow has no such widget.

| Kind | Workflow | Inputs mapped | Unknown | prompt | negative | seed | count | Output node |
|---|---|---|---|---|---|---|---|---|
| krea2-t2i | icekiub/Krea2Icy_-Subs_1.1 | pose -> LoadImage 19 (bypassed control path) | - | CLIPTextEncode 12 | CLIPTextEncode 6 | KSampler 3 | EmptyLatentImage 18 | SaveImage 1 |
| h3-reference-image | icekiub/H3_Icy_image | identity -> IcyMultiRefLoader 81 line 1; references -> lines 2-5 | - | PrimitiveStringMultiline 50 via LM Studio compiler 93 | - | RandomNoise 6 | EmptyLatentImage 53 | PreviewImage 62 (no SaveImage) |
| character-sheet | icekiub/icy_ref_character_sheet_for_minimax | image -> LoadImage 2220 | - | CLIPTextEncode 2234 | CLIPTextEncode 2239 | RandomNoise 2242 | EmptyFlux2LatentImage 2241 | SaveImage 2249 |
| refmod-create | h3-refmods/franckyb-refmod-create-from-folder | images -> H3RefModCreateFromFolder 32 `folder` (a folder path, not a file) | - | - | - | - | - | node 32 writes the RefMod (`name` widget 3) |
| wardrobe | icekiub/Any_Clothes_9B_-_Subs_-_Icekiub_V1.3 | image -> LoadImage 15, clothes -> LoadImage 19 (extra slots 27, 26) | - | CLIPTextEncode 6 | - (ConditioningZeroOut) | KSampler 3 | EmptyLatentImage 9 | PreviewImage 4 (no SaveImage) |
| consistent-room | icekiub/Consistent_Room_WF_v3.1-_Icekiub_Subs | room -> LoadImage 238 (enables 238/239); param character_lora -> LoraLoaderModelOnly 361 | - | PrimitiveStringMultiline 178 | CLIPTextEncode 170 | ClownsharKSampler_Beta 350 [7] | EmptyFlux2LatentImage 351 | SaveImage 173 (+ room/angle saves) |
| image-edit | icekiub/QWEN_IMAGE_UNLEASHED_ICEKIUB_SUBS_-_v1_ | image -> LoadImage 122 | - | TextEncodeQwenImageEditPlus 3 | - (ConditioningZeroOut) | KSampler 27 | EmptyLatentImage 81 | SaveImage 120 |
| image-to-video | icekiub/I2V_Infinite_extender_-_SUBS_-_Icekiub_v1 | image -> LoadImage 33 | - | CLIPTextEncode 189 | CLIPTextEncode 186 | KSamplerAdvanced 190 [1] (loop 294 same) | - | VHS_VideoCombine 244 (full video) |
| motion-control | icekiub/Motion_Control_Icy_-SUBS | character -> BetterImageLoader 161 [1], video -> VHS_LoadVideo 33 `video` | - | CLIPTextEncode 3 | CLIPTextEncode 4 | KSampler 154 (loop 174 same) | - | VHS_VideoCombine 181 (clean, with audio) |
| upscale-video | h3/NEW_-_V2V_Latent_Motion_Transfer_with_upscale_and_de-rope_ | video -> VHS_LoadVideo 1 `video` | - | PrimitiveStringMultiline 121 | - | RandomNoise 30 (pass 2: 146) | - | VHS_VideoCombine 143 (de-roped) |
| klein-t2i | api-tests/klein-t2i-test (API format) | - | - | 4 `text` | 5 `text` | 8 `seed` | 7 `batch_size` | SaveImage 10 |
| carousel | icekiub/Carousel_Pose_changer_-_Icekiub_V1.7 | image -> LoadImage 13 | - | CR Prompt List 16 [1] (one pose per line) | CLIPTextEncode 8 | KSampler 9 | - (one image per line) | SaveImage 10 |
| lipsync | MiniMax-H3-Simple-WF/IMG-_-Audio-To-Video | image -> LoadImage 139; audio -> VHS_LoadVideo 155 `video` (audio_to_video) | - | PrimitiveStringMultiline 142 | - | RandomNoise 129 | - | SaveVideo 92 |
| character-video | h3-refmods/dainamo-refmod-generate | character -> MiniMaxH3RefModsLoader 200 [1] (RefMod name) | - | MiniMaxH3ImageToVideo 127 [0] | - | RandomNoise 128 | - | SaveVideo 136 |

Things a human must still do (see each map's `notes`):

- **h3-reference-image**: the prompt passes through `ICYLMStudioMultimodalPrompt` 93, which needs a
  local LM Studio server; there is no SaveImage (output is a PreviewImage in `temp/`).
- **wardrobe**: model-vs-clothes loader assignment is inferred from canvas layout (no node titles);
  no SaveImage either.
- **consistent-room**: binding `room` switches nodes 238/239 on (`enable_nodes`). The character is
  a trained LoRA, not an image: the `character_lora` parameter sets LoraLoaderModelOnly 361, and
  the director only adds this step when the role has a `lora`; otherwise the room is a gap.
- **krea2-t2i**: the pose/depth control group is bypassed in the shipped file.
- **lipsync**: the voice is read from VHS_LoadVideo 155's soundtrack. The `audio` port carries
  `transform: audio_to_video`: the runner wraps the audio in a black video with ffmpeg, uploads
  it, and `set` resets `skip_first_frames` and `frame_load_cap` to 0 so the whole track plays.
- **character-video** / **refmod-create**: RefMods only from references the client owns
  (`docs/H3-REFMODS.md`); the `MiniMaxH3RefModsLoader` field name is inferred from widget layout.
- **upscale-video**: performer references (LoadImage 64 and 108) are not studio ports; set by hand.
