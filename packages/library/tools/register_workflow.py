"""Register a ComfyUI workflow file in workflows/manifest.json.

One implementation for every import path (creator downloads, bought packs, RefMod
examples), so attribution rules cannot drift between them:

1. a node's own `properties.cnr_id` / `aux_id` names its pack;
2. otherwise a class listed in CLASS_PACK (read from that pack's NODE_CLASS_MAPPINGS,
   with the date it was read) names it;
3. otherwise ComfyUI core types and subgraph UUIDs are `comfy-core`;
4. anything else is recorded under `unattributed_node_types`. It is never guessed.

The manifest hash is of the stored bytes. `.gitattributes` keeps workflows/** out of
line-ending conversion so that hash survives a clone.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "workflows" / "manifest.json"

# Read from each repo's NODE_CLASS_MAPPINGS on 2026-09-13.
CLASS_PACK: dict[str, str] = {
    **{k: "FranckyB/ComfyUI-H3RefModPicker" for k in (
        "H3RefModCreateFromFolder", "H3RefModCreateFromInputs", "H3RefModLoader",
        "H3RefModApplySimple", "H3RefModVisualPicker")},
    **{k: "Luisacaotica/ComfyUI-MiniMaxH3Mod" for k in (
        "MiniMaxH3RefModBundleSave", "MiniMaxH3RefModTextEncode", "MiniMaxH3RefModSave",
        "MiniMaxH3RefModMasterExtract", "MiniMaxH3RefModInspect", "MiniMaxH3RefModAudioExtract",
        "MiniMaxH3RefModExtract", "MiniMaxH3RefModFolderLoader", "MiniMaxH3RefModsLoader",
        "MiniMaxH3RefModsAxis", "MiniMaxH3RefModApply", "MiniMaxH3RefModStepCurve",
        "MiniMaxH3RefModConfig", "MiniMaxH3RefModContinuumBridge", "MiniMaxH3RefModBridgeDisarm")},
    "SpectrumApplyMiniMaxH3": "xmarre/ComfyUI-Spectrum-MiniMax-H3",
}

CORE_TYPES = {
    "VAELoader", "CLIPLoader", "UNETLoader", "CheckpointLoaderSimple", "LoraLoader",
    "LoraLoaderModelOnly", "RandomNoise", "BasicGuider", "CFGGuider", "KSampler",
    "KSamplerAdvanced", "KSamplerSelect", "BasicScheduler", "SamplerCustomAdvanced",
    "VAEDecode", "VAEEncode", "VAEDecodeAudio", "CreateVideo", "SaveVideo", "SaveImage",
    "PreviewImage", "LoadImage", "EmptyLatentImage", "EmptySD3LatentImage", "EmptyImage",
    "CLIPTextEncode", "ConditioningZeroOut", "PrimitiveFloat", "PrimitiveInt",
    "PrimitiveString", "PrimitiveStringMultiline", "PrimitiveBoolean", "ComfyMathExpression",
    "MiniMaxH3ImageToVideo", "MiniMaxH3SigmaShift", "MiniMaxH3CustomKeyframes", "Reroute",
    "Note", "MarkdownNote", "ImageScale", "ImageScaleBy", "ImageScaleToTotalPixels",
    "GetImageSize", "ModelSamplingFlux", "FluxGuidance", "DualCLIPLoader",
}
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-")
MODEL_RE = re.compile(r"[\w.\-]+\.(?:safetensors|gguf|ckpt|pt|pth)")


class NotAWorkflow(ValueError):
    pass


def graph_nodes(d: Any) -> list[dict[str, Any]]:
    """Nodes of a UI-format graph (with subgraphs) or an API-format prompt."""
    if isinstance(d, dict) and isinstance(d.get("nodes"), list):
        return list(d["nodes"]) + [n for sg in (d.get("definitions") or {}).get("subgraphs") or []
                                   for n in sg.get("nodes", [])]
    if isinstance(d, dict) and d and all(isinstance(v, dict) and "class_type" in v for v in d.values()):
        return [{"type": v["class_type"], "properties": {}} for v in d.values()]
    raise NotAWorkflow("not a ComfyUI graph: no `nodes` list and not an API-format prompt")


def analyse(raw: bytes) -> dict[str, Any]:
    d = json.loads(raw)
    nodes = graph_nodes(d)
    packs, unattributed = set(), set()
    for n in nodes:
        t = n.get("type") or ""
        props = n.get("properties") or {}
        pid = props.get("cnr_id") or props.get("aux_id")
        if pid:
            packs.add(pid)
        elif t in CLASS_PACK:
            packs.add(CLASS_PACK[t])
        elif t in CORE_TYPES or UUID.match(t):
            packs.add("comfy-core")
        elif t:
            unattributed.add(t)
    out = {
        "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "node_count": len(nodes),
        "node_types": sorted({n.get("type") for n in nodes if n.get("type")}),
        "node_packs": sorted(packs),
        "models": sorted(set(MODEL_RE.findall(json.dumps(d)))),
    }
    if unattributed:
        out["unattributed_node_types"] = sorted(unattributed)
    return out


def register(path: Path, sources: list[str], manifest: Path = MANIFEST) -> dict[str, Any]:
    """Add or replace the manifest entry for `path` (which must live under workflows/)."""
    path = path.resolve()
    rel = path.relative_to(REPO / "workflows").as_posix()
    entry = {**analyse(path.read_bytes()), "sources": sources,
             "file": rel, "canonical": f"workflows/{rel}"}
    man = json.loads(manifest.read_text(encoding="utf-8"))
    man["workflows"] = [w for w in man["workflows"] if w["canonical"] != entry["canonical"]]
    man["workflows"].append(entry)
    man["count"] = len(man["workflows"])
    manifest.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return entry
