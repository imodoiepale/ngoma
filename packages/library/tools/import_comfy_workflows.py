import hashlib
import json
import shutil
from pathlib import Path

SOURCE = Path(r"C:\Users\inkno\Documents\COMFY")
DEST = Path(__file__).resolve().parents[1] / "workflows" / "local-comfy"
MANIFEST = Path(__file__).resolve().parents[1] / "manifests" / "local-comfy-workflows.json"
MODEL_EXTENSIONS = (".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf")


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)


def analyse(path: Path):
    raw = path.read_bytes()
    data = json.loads(raw)
    nodes = data.get("nodes", []) if isinstance(data, dict) else []
    node_types = sorted({str(node.get("type")) for node in nodes if isinstance(node, dict) and node.get("type")})
    if not nodes and isinstance(data, dict):
        node_types = sorted({str(node.get("class_type")) for node in data.values() if isinstance(node, dict) and node.get("class_type")})
    models = sorted({text for text in strings(data) if text.lower().endswith(MODEL_EXTENSIONS)})
    relative = path.relative_to(SOURCE)
    target = DEST / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    return {
        "source": str(path),
        "library_copy": str(target),
        "relative_path": relative.as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "node_count": len(nodes) if nodes else len(data) if isinstance(data, dict) else 0,
        "node_types": node_types,
        "model_references": models,
    }


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    records = []
    errors = []
    seen = set()
    for path in sorted(SOURCE.rglob("*.json")):
        try:
            record = analyse(path)
            duplicate_of = seen and next((item[1] for item in seen if item[0] == record["sha256"]), None)
            if duplicate_of:
                record["duplicate_of"] = duplicate_of
            else:
                seen.add((record["sha256"], record["relative_path"]))
            records.append(record)
        except Exception as exc:
            errors.append({"source": str(path), "error": str(exc)})
    result = {"source_root": str(SOURCE), "workflow_count": len(records), "workflows": records, "errors": errors}
    MANIFEST.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
