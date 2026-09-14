# ComfyUI-IcyHider

A lightweight ComfyUI extension that hides previews on selected node classes until hover or selection.

This version removes the old generated "Icy" node wrappers and works directly with normal ComfyUI nodes.

## What Changed

- No dynamic wrapper nodes are created anymore
- No separate "Icy" node variants are required
- You choose which node classes should be affected
- Blur/Cover mode is applied to those selected classes
- Main controls are now available in a dedicated ComfyUI sidebar tab
- Nodes can be added to a forced hidden state from right-click context menu

## Features

- Hide previews until hover or selection
- Two hide modes: `cover` and `blur`
- Adjustable blur amount
- Customizable cover style (gradient, border, icon, text)
- Animated media safety: video/gif-like previews are always covered
- Sidebar controls for enable/disable, mode, blur, target classes, and hidden-state nodes
- Right-click node action to add/remove a node from hidden state

## Installation

1. Clone this repository into your ComfyUI custom nodes folder:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/icekiub-ai/ComfyUI-IcyHider.git
```

2. Restart ComfyUI.

## Settings

Open ComfyUI Settings and find the `IcyHider` section.

- `Enable Preview Hiding`
- `Target Node Classes`
- `Auto-Detect Targets From Graph`
- `Hide Mode`
- `Blur Amount`
- `Gradient Start Color`
- `Gradient End Color`
- `Border Color`
- `Icon`
- `Text`
- `Text Color`

Most daily interaction is intended from the **Icy Hider** sidebar tab.

## Sidebar UI

Open the **Icy Hider** tab in the ComfyUI sidebar.

You can:

- Enable/disable preview hiding
- Switch between cover and blur mode
- Adjust blur amount live
- Edit and save target node classes
- Auto-detect target classes from the current graph
- Manage the forced hidden-state node list

## Right-click Context Menu

Right-click any node and use:

- `IcyHider: Add Node to Hidden State`
- `IcyHider: Remove Node from Hidden State`

Hidden-state nodes are persisted and managed in the sidebar list.

### Target Node Classes

Use a comma-separated list of Comfy node class names.

Default:

```text
PreviewImage, LoadImage, SaveImage
```

Examples:

```text
PreviewImage, SaveImage, VHS_VideoCombine
```

If you are unsure of a class name, check your workflow JSON and use the node `type` value.

### Auto-Detect Targets From Graph

Set this toggle to `ON` to scan the current graph and automatically fill `Target Node Classes` with discovered preview-capable classes. The toggle resets to `OFF` after running.

## Usage

1. Add your normal preview-capable nodes to a workflow.
2. Set `Target Node Classes` to the node classes you want to hide.
3. Choose `cover` or `blur` mode.
4. Hover over or select a targeted node to reveal its preview.

## License

MIT
