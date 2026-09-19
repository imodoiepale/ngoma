"""icynodes — unified bundle of the icekiub custom node packs.

Merges, with node names preserved 1:1 (workflows keep loading):
  - betterimage_loader      (Icy Image/MultiRef/Video Loader)
  - ICYLM                   (Icy LM Studio nodes)
  - ComfyUI-IcyHider        (frontend-only JS extension)
  - comfyui-prompt-list-from-folder (PromptListFromFolder)
  - icymegapixelresize      (IcyMegapixelResize)
"""

from .nodes_image_loader import IcyImageLoader, IcyMultiRefLoader, IcyVideoLoader
from .nodes_prompt_list import PromptListFromFolder
from .nodes_megapixel import NODE_CLASS_MAPPINGS as _MP_CLASS, NODE_DISPLAY_NAME_MAPPINGS as _MP_DISPLAY
from .lmstudio_nodes import NODE_CLASS_MAPPINGS as _LM_CLASS, NODE_DISPLAY_NAME_MAPPINGS as _LM_DISPLAY

NODE_CLASS_MAPPINGS = {
    **_LM_CLASS,
    **_MP_CLASS,
    "IcyImageLoader": IcyImageLoader,
    "IcyMultiRefLoader": IcyMultiRefLoader,
    "IcyVideoLoader": IcyVideoLoader,
    "PromptListFromFolder": PromptListFromFolder,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    **_LM_DISPLAY,
    **_MP_DISPLAY,
    "IcyImageLoader": "❄️ Icy Image Loader (icekiub)",
    "IcyMultiRefLoader": "❄️ Icy MultiRef Loader (icekiub)",
    "IcyVideoLoader": "❄️ Icy Video Loader (icekiub)",
    "PromptListFromFolder": "❄️ Icy Prompt List From Folder (icekiub)",
}

# Frontend-only modules: registering the server routes + JS, no node classes.
from . import server_routes_image_loader as _server_routes  # noqa: E402,F401  (registers /icy_loader/* routes on import)

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print("icynodes by icekiub: 9 nodes + IcyHider frontend (5 packs merged) — extension loaded")
