import math

import torch

import comfy.utils


def _dims_for_megapixels(megapixels, aspect_ratio, divisible_by):
    total_pixels = megapixels * 1_000_000
    new_width = int(math.sqrt(total_pixels * aspect_ratio))
    new_height = int(math.sqrt(total_pixels / aspect_ratio))
    if divisible_by > 1:
        new_width -= new_width % divisible_by
        new_height -= new_height % divisible_by
    return max(new_width, 1), max(new_height, 1)


class IcyMegapixelResize:
    upscale_methods = ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]
    aspect_ratios = ["1:1", "4:3", "3:4", "3:2", "2:3", "16:9", "9:16", "2:1", "1:2"]

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "megapixels": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.01,
                    "max": 16.0,
                    "step": 0.01,
                    "tooltip": "Target total pixel count in megapixels (1.0 = 1,000,000 pixels). Aspect ratio is preserved.",
                }),
                "upscale_method": (cls.upscale_methods,),
                "divisible_by": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 512,
                    "step": 1,
                    "tooltip": "Round output dimensions down to a multiple of this value. 1 disables rounding.",
                }),
                "aspect_ratio": (cls.aspect_ratios, {
                    "default": "1:1",
                    "tooltip": "Aspect ratio used to derive width/height when no image is connected. Ignored when an image is provided.",
                }),
            },
            "optional": {
                "image": ("IMAGE", {
                    "tooltip": "If omitted, the node outputs a blank image of the target size plus the computed width/height.",
                }),
            },
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT")
    RETURN_NAMES = ("IMAGE", "width", "height")
    FUNCTION = "resize"
    CATEGORY = "image/upscaling"
    DESCRIPTION = "Resize an image to a target megapixel count while preserving aspect ratio. With no image, derive dimensions from megapixels and aspect ratio."

    def resize(self, megapixels, upscale_method, divisible_by, aspect_ratio, image=None):
        if image is None:
            aw, ah = aspect_ratio.split(":")
            ar = int(aw) / int(ah)
            new_width, new_height = _dims_for_megapixels(megapixels, ar, divisible_by)
            blank = torch.zeros((1, new_height, new_width, 3))
            return (blank, new_width, new_height)

        _, H, W, _ = image.shape
        new_width, new_height = _dims_for_megapixels(megapixels, W / H, divisible_by)
        samples = image.movedim(-1, 1)
        s = comfy.utils.common_upscale(samples, new_width, new_height, upscale_method, "disabled")
        s = s.movedim(1, -1)
        return (s, new_width, new_height)


NODE_CLASS_MAPPINGS = {
    "IcyMegapixelResize": IcyMegapixelResize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "IcyMegapixelResize": "Icy Megapixel Resize",
}
