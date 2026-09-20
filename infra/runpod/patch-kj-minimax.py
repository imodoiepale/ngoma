#!/usr/bin/env python3
from pathlib import Path

p = Path("/workspace/runpod-slim/ComfyUI/custom_nodes/ComfyUI-KJNodes/__init__.py")
text = p.read_text(encoding="utf-8")
needle = "def generate_node_mappings(node_config):"
if "MiniMaxChunkFeedForward" in text:
    print("ALREADY")
else:
    block = '''
#minimax
try:
    from .nodes.minimax_nodes import MiniMaxChunkFeedForward, MiniMaxLowVRAMAttention, MiniMaxH3TokenCounter
    NODE_CONFIG.update({
    "MiniMaxChunkFeedForward": {"class": MiniMaxChunkFeedForward, "name": "MiniMax H3 ChunkFeedForward"},
    "MiniMaxLowVRAMAttention": {"class": MiniMaxLowVRAMAttention, "name": "MiniMax H3 Low VRAM Attention"},
    "MiniMaxH3TokenCounter": {"class": MiniMaxH3TokenCounter, "name": "MiniMax H3 Token Counter"},
    })
except Exception as e:
    logging.warning(f"KJNodes: MiniMax nodes could not be imported. MiniMax nodes will be unavailable. Error: {e}", exc_info=True)

'''
    if needle not in text:
        raise SystemExit("NO_ANCHOR")
    text = text.replace(needle, block + needle, 1)
    p.write_text(text, encoding="utf-8")
    print("PATCHED")
