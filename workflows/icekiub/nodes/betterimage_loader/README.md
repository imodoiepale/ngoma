# ❄️ Icy Loader

Custom nodes for ComfyUI by **icekiub**.

## Nodes

### Icy Image Loader
Loads a single image from the `input` or `output` folder and returns `IMAGE` + `MASK`.
Use the **Open Gallery** button on the node to visually browse both folders in a grid
(search, sort, preview) and pick a file.

### Icy MultiRef Loader
Loads multiple reference media with an ordered, drag-and-drop grid on the node.

- Drop image or video files onto the node or its grid — they upload to the input
  folder and append in order. References show as a responsive grid of square
  thumbnail tiles; each tile is numbered in order and reveals remove (✕) and
  move (◀ ▶) controls on hover; a **Clear all** button wipes the list.
- Or use the **Open Gallery** button / click the drop zone to multi-select files
  (videos included, first frame is used as the reference). Gallery picks are
  added to what is already loaded — nothing is cleared until you remove tiles or
  press Clear all.
- Outputs:
  - `IMAGE_1` … `IMAGE_8` — each reference separately, in list order, at native
    size. Wire them straight into separate image inputs such as ICY LM Studio's
    `image`, `image2` … `image8`. Empty slots output nothing.
  - `IMAGE` + `MASK` — the full ordered batch, resized to the first image's size.
