"""LoRA training job for a character: the ostris/ai-toolkit config, the dataset with captions,
the pod command and a manifest. Plans on this machine; trains only on the pod, by hand.

The `lora-train` catalogue step (S01 "RefMod or LoRA as a service", X01) sells a trained
character LoRA. Training is not a ComfyUI graph, it is an ai-toolkit run on the pod, so this
module does everything that can be done without a GPU and writes the one command that
cannot. Nothing here runs training, downloads a model or spends a minute of GPU time.

    python packages/engine/lora_train.py --client epalle --collection red-dress --trigger rdrss --dry-run
    python packages/engine/lora_train.py --client epalle --collection red-dress --trigger rdrss --base klein-9b --steps 3000 --rank 16
    python packages/engine/lora_train.py --client epalle --collection red-dress --trigger rdrss --captions brands/epalle/runs/<wf>/caption-dataset/<run>

What it writes, under brands/<client>/runs/training/<collection>/ (brands/*/runs/ is gitignored):
    config.yaml     the ai-toolkit job (sd_trainer process, LoRA network, dataset, base model)
    launch.sh       scp the folder to the pod and start `run.py config.yaml` in tmux
    dataset/        (not in --dry-run) the images and one <stem>.txt caption per image
    captions.txt    (only when no captions exist) a template: `<file>\\t<trigger> <caption>` per line
    manifest.json   (not in --dry-run) rights gate, counts, base model, paths, needs_setup

The rights gate refuses before writing anything. `collection.json` must say `use: data`,
`rights: owned` or `licensed`, and the character must be fictional (`fictional: true`, or a
note containing "fictional") or a real person with `consent: true`. A folder with no
collection.json is `rights: unclear` and is refused; so is `use: inspiration` (a mood board
is not a training set).

Captions: `--captions` names a folder of `<stem>.txt` files or a JSON/JSONL from the
`caption-dataset` step (the Icekiub Qwen3-VL captioning workflow writes one text file per
image beside the image or in its output folder; a JSONL of `{"file": ..., "caption": ...}`
is also read). Without it, `<stem>.txt` files beside the images are used; failing that a
`captions.txt` template is written and the manifest says `captions: template`, which the
launch command refuses to ship (`--allow-uncaptioned` overrides for a trigger-word-only run).

Base models (`--base`, or `base` in collection.json):
    klein-9b   FLUX.2 Klein 9B.  ai-toolkit arch `flux2`.  Pod path /workspace/epalle/models/diffusion_models/flux-2-klein-9b-fp8.safetensors
               (download-plan `black-forest-labs/FLUX.2-klein-9b-fp8`); HF repo black-forest-labs/FLUX.2-klein-9B for the text encoder/VAE.
    krea-2     Krea 2 (FLUX-family, Comfy-Org/Krea-2).  Pod path /workspace/epalle/models/diffusion_models/krea2_turbo_fp8_scaled.safetensors.
               ai-toolkit has no first-class Krea 2 arch at the time of writing; the config uses `flux2` with the Krea 2
               weights and the manifest marks it `verify_arch`.

What must exist on the pod before launch.sh works (none of it is installed by setup-pod.sh yet;
this is recorded as `needs_setup` in the manifest and on the catalogue node, not as a change
to the infra scripts, which another workstream owns):
    /workspace/epalle/ai-toolkit        git clone https://github.com/ostris/ai-toolkit, `pip install -r requirements.txt`
                                        into /workspace/epalle/venv (the ComfyUI venv; torch is already there)
    base model file                     the path above, from infra/runpod/download_planned.py (Klein needs the accepted
                                        FLUX.2 licence, docs/BLOCKERS.md item 3)
    text encoder + VAE                  qwen_3_8b_fp8mixed.safetensors and flux2-vae.safetensors are on the volume for
                                        ComfyUI; ai-toolkit loads them from the HF repo by default, so HF_TOKEN in the
                                        pod environment or `model.extras_name_or_path` pointed at the files
    ~60 GB free on the volume           latent cache and 4 checkpoints for a 9B model
Output: /workspace/epalle/training/<name>/<name>.safetensors, copied back with scp into
brands/<client>/runs/training/<collection>/ and named on the role as `roles[].lora` for consistent-room.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BRANDS = REPO / "brands"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
POD_ROOT = "/workspace/epalle"
POD_TRAINING = f"{POD_ROOT}/training"
POD_AI_TOOLKIT = f"{POD_ROOT}/ai-toolkit"
POD_PYTHON = f"{POD_ROOT}/venv/bin/python"
SSH_KEY = "infra/epalle_runpod_ed25519"

BASES: dict[str, dict[str, Any]] = {
    "klein-9b": {"label": "FLUX.2 Klein 9B", "arch": "flux2", "verify_arch": False,
                 "path": f"{POD_ROOT}/models/diffusion_models/flux-2-klein-9b-fp8.safetensors",
                 "hf": "black-forest-labs/FLUX.2-klein-9B", "plan_file": "flux-2-klein-9b-fp8.safetensors",
                 "licence": "FLUX.2 Klein licence must be accepted on Hugging Face (docs/BLOCKERS.md item 3)"},
    "krea-2": {"label": "Krea 2", "arch": "flux2", "verify_arch": True,
               "path": f"{POD_ROOT}/models/diffusion_models/krea2_turbo_fp8_scaled.safetensors",
               "hf": "Comfy-Org/Krea-2", "plan_file": "krea2_turbo_fp8_scaled.safetensors",
               "licence": "check the Krea 2 model licence allows fine-tuning for commercial output"},
}
DEFAULT_BASE = "klein-9b"
NEEDS_SETUP = [
    f"clone ostris/ai-toolkit to {POD_AI_TOOLKIT} and install its requirements into {POD_ROOT}/venv",
    "base model file present on the volume (infra/runpod/download_planned.py)",
    "HF_TOKEN in the pod environment for the text encoder and VAE, or model.extras_name_or_path pointed at the volume files",
    "about 60 GB free on the network volume for the latent cache and checkpoints",
]


class LoraTrainError(RuntimeError):
    pass


# ---------------------------------------------------------------- rights gate

def read_collection(client: str, name: str) -> tuple[Path, dict[str, Any]]:
    folder = BRANDS / client / "references" / name
    if not folder.is_dir():
        raise LoraTrainError(f"no reference collection at brands/{client}/references/{name}")
    meta_path = folder / "collection.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig")) if meta_path.exists() else {}
    return folder, meta


def is_fictional(meta: dict[str, Any]) -> bool:
    if meta.get("fictional") is True:
        return True
    return any("fictional" in str(n).lower() for n in meta.get("notes") or [])


def rights_gate(meta: dict[str, Any], name: str) -> tuple[bool, str]:
    """May this collection train a character LoRA? Owned or licensed data of a fictional
    character, or of a real person who signed a release. Anything else is refused."""
    rights = meta.get("rights", "unclear")
    if rights not in ("owned", "licensed"):
        return False, f"{name}: rights are {rights!r}; a LoRA is trained only on owned or licensed images"
    if meta.get("use", "inspiration") != "data":
        return False, f"{name}: use is {meta.get('use', 'inspiration')!r}; a mood board is not a training set (set use: data)"
    if meta.get("consent") is True:
        return True, f"{name}: {rights} data, written consent on file"
    if is_fictional(meta):
        return True, f"{name}: {rights} data, fictional character (no real-person likeness)"
    return False, (f"{name}: a real person's likeness needs consent: true in collection.json, or mark the "
                   f"character fictional: true")


# ---------------------------------------------------------------- dataset and captions

def image_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXT)


def load_captions(images: list[Path], captions: Path | None) -> tuple[dict[str, str], str]:
    """(stem -> caption, source). Sources: `folder` of <stem>.txt, `jsonl`/`json` from the
    captioning step, `sidecar` files beside the images, or `none`."""
    found: dict[str, str] = {}
    if captions is not None:
        c = Path(captions)
        if not c.exists():
            raise LoraTrainError(f"captions not found: {c}")
        if c.is_dir():
            for img in images:
                t = c / f"{img.stem}.txt"
                if t.exists():
                    found[img.stem] = t.read_text(encoding="utf-8-sig").strip()
            return found, "folder"
        if c.suffix.lower() in (".jsonl", ".json"):
            text = c.read_text(encoding="utf-8-sig")
            rows = [json.loads(l) for l in text.splitlines() if l.strip()] if c.suffix.lower() == ".jsonl" else json.loads(text)
            rows = rows if isinstance(rows, list) else rows.get("captions", [])
            for r in rows:
                f, cap = r.get("file") or r.get("image") or "", r.get("caption") or r.get("text") or ""
                if f and cap:
                    found[Path(f).stem] = str(cap).strip()
            return {k: v for k, v in found.items() if k in {i.stem for i in images}}, c.suffix.lower().lstrip(".")
        raise LoraTrainError(f"captions must be a folder of <stem>.txt, a .json or a .jsonl: {c}")
    for img in images:
        t = img.with_suffix(".txt")
        if t.exists():
            found[img.stem] = t.read_text(encoding="utf-8-sig").strip()
    return found, "sidecar" if found else "none"


def caption_template(images: list[Path], trigger: str) -> str:
    L = ["# one line per image: <file>\t<caption>. Start every caption with the trigger word.",
         "# Fill this in, or run the caption-dataset step and pass its output with --captions."]
    L += [f"{img.name}\t{trigger} " for img in images]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- the config

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "lora"


def build_config(name: str, trigger: str, base: str, steps: int, rank: int, resolution: list[int],
                 pod_dir: str) -> dict[str, Any]:
    """An ostris/ai-toolkit job (`run.py config.yaml`). Keys follow the toolkit's example
    configs; values are the conservative defaults for a 9B FLUX-family character LoRA."""
    b = BASES[base]
    return {
        "job": "extension",
        "config": {
            "name": name,
            "process": [{
                "type": "sd_trainer",
                "training_folder": pod_dir,
                "device": "cuda:0",
                "trigger_word": trigger,
                "network": {"type": "lora", "linear": rank, "linear_alpha": rank},
                "save": {"dtype": "float16", "save_every": max(250, steps // 8), "max_step_saves_to_keep": 4},
                "datasets": [{"folder_path": f"{pod_dir}/dataset", "caption_ext": "txt", "caption_dropout_rate": 0.05,
                              "shuffle_tokens": False, "cache_latents_to_disk": True, "resolution": resolution}],
                "train": {"batch_size": 1, "steps": steps, "gradient_accumulation_steps": 1, "train_unet": True,
                          "train_text_encoder": False, "gradient_checkpointing": True, "noise_scheduler": "flowmatch",
                          "optimizer": "adamw8bit", "lr": 1e-4, "dtype": "bf16", "ema_config": {"use_ema": True, "ema_decay": 0.99}},
                "model": {"name_or_path": b["path"], "arch": b["arch"], "quantize": True,
                          "extras_name_or_path": b["hf"]},
                "sample": {"sampler": "flowmatch", "sample_every": max(250, steps // 8), "width": 1024, "height": 1024,
                           "prompts": [f"{trigger}, portrait, natural window light, phone photo",
                                       f"{trigger}, full body, walking in a city street at dusk"],
                           "seed": 42, "walk_seed": True, "guidance_scale": 4, "sample_steps": 20},
            }],
        },
        "meta": {"name": "[name]", "version": "1.0", "written_by": "packages/engine/lora_train.py", "date": date.today().isoformat()},
    }


def to_yaml(doc: Any, indent: int = 0) -> str:
    """A small YAML writer so the config needs no dependency beyond the standard library."""
    pad = "  " * indent
    if isinstance(doc, dict):
        lines = []
        for k, v in doc.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{k}:")
                lines.append(to_yaml(v, indent + 1))
            else:
                lines.append(f"{pad}{k}: {_scalar(v)}")
        return "\n".join(lines)
    if isinstance(doc, list):
        lines = []
        for item in doc:
            if isinstance(item, dict):
                body = to_yaml(item, indent + 1).splitlines()
                lines.append(f"{pad}- {body[0].strip()}")
                lines += body[1:]
            elif isinstance(item, list):
                lines.append(f"{pad}- {json.dumps(item)}")
            else:
                lines.append(f"{pad}- {_scalar(item)}")
        return "\n".join(lines)
    return f"{pad}{_scalar(doc)}"


def _scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return repr(v) if isinstance(v, float) else str(v)
    if isinstance(v, list):
        return json.dumps(v)
    if isinstance(v, dict) and not v:
        return "{}"
    s = str(v)
    # quote anything YAML would read as something other than this string: markers, numbers,
    # dates, booleans, null, leading or trailing space
    if (s == "" or re.search(r"[:#\[\]{},&*!|>'\"%@`]|^\s|\s$|^(true|false|null|yes|no|on|off|~)$", s, re.I)
            or s.startswith("-") or re.fullmatch(r"[-+]?(\d[\d_]*\.?\d*(e[-+]?\d+)?|\.\d+|0x[0-9a-f]+|\.inf|\.nan)", s, re.I)
            or re.fullmatch(r"\d{4}-\d{2}-\d{2}([T ].*)?", s)):
        return json.dumps(s)
    return s


def _rel(p: Path) -> str:
    """Repo-relative posix path when inside the repo, else the absolute path."""
    try:
        return p.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def launch_script(local_dir: Path, name: str, pod_dir: str, uncaptioned: bool) -> str:
    rel = _rel(local_dir)
    guard = ("" if not uncaptioned else
             "# WARNING: dataset has no captions (trigger word only). Re-run with --captions once the caption-dataset step has run.\n")
    return f"""#!/usr/bin/env bash
# Written by packages/engine/lora_train.py. Run from the repo root with the pod RUNNING
# (infra/runpod/README.md section 3). Fill in the pod's public IP and SSH port from the console.
# Nothing here is executed by the studio; a person runs it and watches the cost.
set -euo pipefail
POD_IP="${{POD_IP:?set POD_IP}}"
POD_PORT="${{POD_PORT:?set POD_PORT}}"
KEY="{SSH_KEY}"
{guard}
# 1. ship the dataset and config
ssh -i "$KEY" -p "$POD_PORT" "root@$POD_IP" "mkdir -p {pod_dir}"
scp -i "$KEY" -P "$POD_PORT" -r {rel}/dataset {rel}/config.yaml "root@$POD_IP:{pod_dir}/"
# 2. preconditions (ai-toolkit clone, base model, HF token) - fails loudly instead of burning GPU minutes
ssh -i "$KEY" -p "$POD_PORT" "root@$POD_IP" 'test -f {POD_AI_TOOLKIT}/run.py || {{ echo "ai-toolkit missing: git clone https://github.com/ostris/ai-toolkit {POD_AI_TOOLKIT} && {POD_PYTHON} -m pip install -r {POD_AI_TOOLKIT}/requirements.txt"; exit 2; }}'
ssh -i "$KEY" -p "$POD_PORT" "root@$POD_IP" 'grep -q name_or_path {pod_dir}/config.yaml && test -f "$(grep -m1 " name_or_path:" {pod_dir}/config.yaml | awk "{{print \\$2}}")" || {{ echo "base model missing on the volume (infra/runpod/download_planned.py)"; exit 3; }}'
ssh -i "$KEY" -p "$POD_PORT" "root@$POD_IP" 'test -n "${{HF_TOKEN:-}}" || echo "HF_TOKEN not set on the pod: ai-toolkit will fail to fetch the text encoder and VAE"'
# 3. train in tmux so an SSH drop does not kill the run; watch with: tmux attach -t lora-{name}
ssh -i "$KEY" -p "$POD_PORT" "root@$POD_IP" "cd {POD_AI_TOOLKIT} && tmux new-session -d -s lora-{name} '{POD_PYTHON} run.py {pod_dir}/config.yaml 2>&1 | tee {pod_dir}/train.log'"
echo "training started in tmux session lora-{name}; the LoRA lands at {pod_dir}/{name}/{name}.safetensors"
echo "when done:  scp -i $KEY -P $POD_PORT root@$POD_IP:{pod_dir}/{name}/{name}.safetensors {rel}/"
echo "then stop the pod: python infra/runpod/provision_pod.py --status"
"""


# ---------------------------------------------------------------- the job

def plan_job(client: str, collection: str, trigger: str, *, base: str | None = None, steps: int = 3000,
             rank: int = 16, resolution: list[int] | None = None, captions: Path | None = None,
             out: Path | None = None, dataset: Path | None = None, allow_uncaptioned: bool = False,
             dry_run: bool = True) -> dict[str, Any]:
    """Gate, plan and write. Dry-run writes config.yaml and launch.sh only; a full plan also
    stages the dataset with captions and writes manifest.json. Training never runs here."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,23}", trigger or ""):
        raise LoraTrainError("trigger must be 3-24 lowercase letters, digits or underscores, starting with a letter")
    if steps < 100 or steps > 20000:
        raise LoraTrainError("steps must be between 100 and 20000")
    if rank not in (4, 8, 16, 32, 64, 128):
        raise LoraTrainError("rank must be one of 4, 8, 16, 32, 64, 128")
    folder, meta = read_collection(client, collection)
    ok, why = rights_gate(meta, collection)
    if not ok:
        raise LoraTrainError("refused: " + why)
    base = base or meta.get("base") or DEFAULT_BASE
    if base not in BASES:
        raise LoraTrainError(f"base must be one of {sorted(BASES)}")
    src_dir = Path(dataset) if dataset else folder
    images = image_files(src_dir)
    if len(images) < 4:
        raise LoraTrainError(f"{_rel(src_dir)}: {len(images)} image(s); a character LoRA needs at least 4 "
                             f"(20 to 40 is the usual set)")
    caps, cap_source = load_captions(images, captions)
    uncaptioned = [i.name for i in images if i.stem not in caps]
    name = _slug(f"{collection}-{trigger}-{base}")
    out_dir = Path(out) if out else BRANDS / client / "runs" / "training" / collection
    pod_dir = f"{POD_TRAINING}/{name}"
    resolution = resolution or [512, 768, 1024]
    config = build_config(name, trigger, base, steps, rank, resolution, pod_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.yaml").write_text(
        f"# ostris/ai-toolkit job written by packages/engine/lora_train.py on {date.today().isoformat()}\n"
        f"# collection brands/{client}/references/{collection}: {why}\n" + to_yaml(config) + "\n", encoding="utf-8")
    (out_dir / "launch.sh").write_text(launch_script(out_dir, name, pod_dir, bool(uncaptioned)), encoding="utf-8", newline="\n")
    if uncaptioned and cap_source == "none":
        (out_dir / "captions.txt").write_text(caption_template(images, trigger), encoding="utf-8")
    needs = list(NEEDS_SETUP) + [BASES[base]["licence"]]
    if BASES[base]["verify_arch"]:
        needs.append(f"verify ai-toolkit's arch name for {BASES[base]['label']} (config says {BASES[base]['arch']!r})")
    if uncaptioned and not allow_uncaptioned:
        needs.append(f"{len(uncaptioned)} image(s) have no caption; run caption-dataset or fill captions.txt, "
                     f"or pass --allow-uncaptioned for a trigger-word-only run")
    result: dict[str, Any] = {
        "status": "dry-run" if dry_run else "planned", "client": client, "collection": collection, "trigger": trigger,
        "rights": {"ok": ok, "why": why, "rights": meta.get("rights"), "consent": bool(meta.get("consent")),
                   "fictional": is_fictional(meta)},
        "base": {"id": base, **{k: v for k, v in BASES[base].items() if k != "verify_arch"}},
        "steps": steps, "rank": rank, "resolution": resolution, "images": len(images),
        "captions": {"source": cap_source, "captioned": len(images) - len(uncaptioned), "uncaptioned": uncaptioned[:10]},
        "config": _rel(out_dir / "config.yaml"), "launch": _rel(out_dir / "launch.sh"),
        "pod_dir": pod_dir, "output": f"{pod_dir}/{name}/{name}.safetensors",
        "command": f"bash {_rel(out_dir / 'launch.sh')}",
        "needs_setup": needs,
        "gpu_estimate": {"steps": steps, "basis": "planning", "note": "about 1.2 s/step for a 9B model at rank 16 on an A100 80GB: "
                         f"roughly {round(steps * 1.2 / 60)} min plus latent caching; not measured yet"},
    }
    if dry_run:
        result["note"] = f"config and launch command written to {_rel(out_dir)}; dataset not staged, nothing trained"
        return result
    ds = out_dir / "dataset"
    ds.mkdir(exist_ok=True)
    for img in images:
        shutil.copy2(img, ds / img.name)
        cap = caps.get(img.stem, "").strip()
        text = cap if cap.lower().startswith(trigger.lower()) else f"{trigger} {cap}".strip()
        (ds / f"{img.stem}.txt").write_text(text + "\n", encoding="utf-8")
    result["dataset"] = _rel(ds)
    result["note"] = f"dataset staged ({len(images)} images), config and launch written; run {result['command']} with the pod up"
    (out_dir / "manifest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result["manifest"] = _rel(out_dir / "manifest.json")
    return result


# ---------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Plan an ostris/ai-toolkit character LoRA job from a reference collection: "
                                             "rights gate, config.yaml, captions, pod launch command and manifest. Never trains.")
    ap.add_argument("--client", required=True, help="workspace id (a folder in brands/)")
    ap.add_argument("--collection", required=True, help="reference collection name under brands/<client>/references/")
    ap.add_argument("--trigger", required=True, help="trigger word, e.g. rdrss (3-24 chars, lowercase)")
    ap.add_argument("--base", choices=sorted(BASES), help=f"base model (default: collection.json `base`, else {DEFAULT_BASE})")
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--rank", type=int, default=16, help="LoRA rank (4-128)")
    ap.add_argument("--resolution", type=int, nargs="+", help="training buckets, default 512 768 1024")
    ap.add_argument("--captions", help="folder of <stem>.txt, or a .json/.jsonl from the caption-dataset step")
    ap.add_argument("--dataset", help="image folder when it is not the collection folder itself")
    ap.add_argument("--out", help="where to write (default brands/<client>/runs/training/<collection>/)")
    ap.add_argument("--allow-uncaptioned", action="store_true", help="plan a trigger-word-only run without captions")
    ap.add_argument("--dry-run", action="store_true", help="write config.yaml and launch.sh only; no dataset copy, no manifest")
    a = ap.parse_args(argv)
    try:
        result = plan_job(a.client, a.collection, a.trigger, base=a.base, steps=a.steps, rank=a.rank,
                          resolution=a.resolution, captions=Path(a.captions) if a.captions else None,
                          out=Path(a.out) if a.out else None, dataset=Path(a.dataset) if a.dataset else None,
                          allow_uncaptioned=a.allow_uncaptioned, dry_run=a.dry_run)
    except LoraTrainError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
