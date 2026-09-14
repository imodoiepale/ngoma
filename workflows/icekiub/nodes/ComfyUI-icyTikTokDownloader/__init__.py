"""
Icy TikTok Downloader Node for ComfyUI
Initializes the node with blue gradient theme and falling snow
"""

from .icy_tiktok_downloader import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

# Web directory for JavaScript extension
WEB_DIRECTORY = "./js"

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
