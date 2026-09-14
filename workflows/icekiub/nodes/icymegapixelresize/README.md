# Icy Megapixel Resize

A small ComfyUI custom node that resizes an image to a target **megapixel** count
while preserving its aspect ratio. With no image connected it doubles as a
megapixels → dimensions converter.

## Node: Icy Megapixel Resize

Category: `image/upscaling`

### Inputs

| Input             | Type    | Default  | Required | Description                                                                 |
|-------------------|---------|----------|----------|-----------------------------------------------------------------------------|
| `megapixels`      | FLOAT   | 1.0      | yes      | Target total pixel count in megapixels (1.0 = 1,000,000 pixels).            |
| `upscale_method`  | combo   | bilinear | yes      | `nearest-exact`, `bilinear`, `area`, `bicubic`, `lanczos`.                  |
| `divisible_by`    | INT     | 1        | yes      | Round output dimensions down to a multiple of this value. `1` = no rounding.|
| `aspect_ratio`    | combo   | 1:1      | yes      | Aspect ratio used to derive width/height when **no image** is connected.    |
| `image`           | IMAGE   | —        | no       | Image to resize. If omitted, a blank image of the target size is produced.  |

### Outputs

| Output   | Type | Description                                            |
|----------|------|--------------------------------------------------------|
| `IMAGE`  | IMAGE| The resized image, or a blank image of the target size when no image is connected. |
| `width`  | INT  | Resulting width.                                       |
| `height` | INT  | Resulting height.                                      |

### Two modes

**Image connected** — the image is resized to `megapixels` preserving its own
aspect ratio. `aspect_ratio` is ignored.

**No image connected** — width/height are derived from `megapixels` and the
selected `aspect_ratio`, and a blank (black) image of that exact size is emitted
on the `IMAGE` output. Useful for feeding target dimensions into other nodes.

### How the math works

Given a target budget of `total_pixels = megapixels * 1_000_000` and an aspect
ratio `AR`, the output dimensions are solved in closed form so the product stays
at the budget and the ratio is preserved:

```
new_width  = sqrt(total_pixels * AR)
new_height = sqrt(total_pixels / AR)
```

Both values are truncated to `int` (so the result lands slightly *under* the
requested budget, never over), then optionally snapped down to a multiple of
`divisible_by`. The resampling is delegated to ComfyUI's built-in
`comfy.utils.common_upscale`, matching the behavior of the core `ImageScale` node.
