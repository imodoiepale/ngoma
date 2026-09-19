# ❄️ IcyNodes

All icekiub custom nodes in one pack. Merged from five standalone packs — **node names are unchanged**, so existing workflows load as-is.

| Node | Display name | From pack |
|---|---|---|
| `IcyImageLoader` | ❄️ Icy Image Loader (icekiub) | betterimage_loader |
| `IcyMultiRefLoader` | ❄️ Icy MultiRef Loader (icekiub) | betterimage_loader |
| `IcyVideoLoader` | ❄️ Icy Video Loader (icekiub) | betterimage_loader |
| `ICYLMStudioModels` | ❄️ Icy LM Studio Models (icekiub) | ICYLM |
| `ICYLMStudioMultimodalPrompt` | ❄️ Icy Multimodal Prompt (icekiub) | ICYLM |
| `ICYLMStudioModelControl` | ❄️ Icy Model Control (icekiub) | ICYLM |
| `ICYLMStudioSelectModel` | ❄️ Icy Select Model (icekiub) | ICYLM |
| `PromptListFromFolder` | ❄️ Icy Prompt List From Folder (icekiub) | comfyui-prompt-list-from-folder |
| `IcyMegapixelResize` | Icy Megapixel Resize | icymegapixelresize |
| — *(frontend-only)* | IcyHider sidebar + hide/blur previews | ComfyUI-IcyHider |

## What's inside

- **Icy Loaders** — image / multi-ref / video loaders with an interactive grid-gallery frontend (thumbnails, video preview streaming, drag-and-drop onto MultiRef). Backed by `/icy_loader/*` server routes.
- **Icy LM Studio** — query a local LM Studio (`/v1/models`) from ComfyUI: list models, multimodal prompt with live streaming status panel, model load/unload control, model pick by index.
- **IcyHider** — frontend-only extension: hide previews on selected node classes with sidebar controls, right-click hidden-state actions, cover/blur modes. Works in Classic and Nodes 2.0 renderers.
- **Icy Prompt List From Folder** — reads `.txt` files from a folder and outputs them as a prompt list (sort by name/modified/random).
- **Icy Megapixel Resize** — resize to an exact target megapixel count (aspect-preserving).

## Install

Manual install: drop this folder into `ComfyUI/custom_nodes/` and `pip install -r requirements.txt`.

## Tests

```
python -m unittest discover tests
```
