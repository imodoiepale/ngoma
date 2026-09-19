"""Workspaces: create, list and check the brand folders the studio works in.

A workspace is `brands/<key>/` with a `brand.yaml`. Nothing else is required for the
author, the canvas or the engine to see it. This tool scaffolds one from the example kit
in `brands/_kit/`, validates the minimum the studio reads, and refuses keys that collide
with the studio's own folders.

    new   <key> --name "Display Name" [--accent "#RRGGBB"] [--kind fashion] [--from epalle] [--dry-run] [--root DIR]
    list  [--root DIR] [--json]
    check <key> [--root DIR] [--json]

`new` writes brand.yaml, references/README.md, workflows/, runs/ (gitignored) and
assets/logo/. With --dry-run it prints the plan and writes nothing. With --from it starts
from an existing workspace's brand.yaml and styles/ instead of the example.
`check` exits 1 on a kit missing a required field; warnings do not fail it.

    python packages/strategy/workspace.py new demo-brand --name "Demo Brand" --dry-run
    python packages/strategy/workspace.py list
    python packages/strategy/workspace.py check epalle
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
BRANDS = REPO / "brands"
KIT = BRANDS / "_kit"
GITIGNORE = REPO / ".gitignore"

RESERVED = {"_presets", "_templates", "_business", "_kit"}
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
KINDS = ("music", "fintech", "fashion", "agency", "product", "education", "other")
USES = ("inspiration", "data")
RIGHTS = ("owned", "licensed", "unclear")
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov"}
RUNS_IGNORE = "brands/*/runs/"
DEFAULT_ACCENT = "#C9A45C"

# Required: `check` fails without them. Each is (dotted path, why the studio needs it).
REQUIRED = [
    ("brand", "the key; workflow_author and the UI list the folder by it"),
    ("display_name|name", "the name the UI and the author show"),
    ("palette.measured", "brandkit and the compositor read the palette from here"),
    ("logo.master", "the compositor composites this file; nothing generates it"),
    ("logo.rule", "COMPOSITE_ONLY, the rule the compositor follows"),
    ("claim_safety.disclosure", "the disclosure line set on AI-assisted imagery"),
]
# Recommended: `check` warns.
RECOMMENDED = [
    ("kind", "music, fintech, fashion, agency, product, education or other"),
    ("palette.measured.accent", "the workspace accent the UI shows"),
    ("positioning", "the compositor's copy block: tagline, promise, ctas, attribution_line"),
    ("voice", "register, tone and the words the brand never uses"),
    ("languages.primary", "brandkit's default language mix"),
    ("typography", "the compositor's type; copy is never rendered by a model"),
    ("masters", "output sizes per ratio"),
]


class WorkspaceError(ValueError):
    pass


@dataclass
class Report:
    key: str
    root: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "path": str(self.root), "ok": self.ok,
                "errors": self.errors, "warnings": self.warnings, "info": self.info}


# ---------------------------------------------------------------- helpers

def _brands(root: Path | None) -> Path:
    return Path(root).resolve() if root else BRANDS


def validate_key(key: str, root: Path | None = None) -> None:
    if isinstance(key, str) and (key in RESERVED or key.startswith("_")):
        raise WorkspaceError(f"key {key!r} is reserved for the studio's own folders "
                             f"({', '.join(sorted(RESERVED))}); a workspace key cannot start with '_'")
    if not isinstance(key, str) or not KEY_RE.match(key):
        raise WorkspaceError(f"key {key!r} must be lowercase a-z, 0-9 and hyphens")
    if (_brands(root) / key).exists():
        raise WorkspaceError(f"brands/{key}/ already exists; pick another key or remove it first")


def _get(doc: dict[str, Any], dotted: str) -> Any:
    cur: Any = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _has(doc: dict[str, Any], spec: str) -> bool:
    return any(_get(doc, alt) not in (None, "", {}, []) for alt in spec.split("|"))


def _fill(text: str, values: dict[str, str]) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{(\w+)\}\}", text)
    if left:
        raise WorkspaceError(f"kit template still has unfilled placeholders: {sorted(set(left))}")
    return text


def _rewrite_kit(text: str, key: str, name: str, source: str) -> str:
    """Start from another workspace's brand.yaml: rewrite key and name, keep the rest."""
    lines = text.splitlines()
    out, saw_brand, saw_name = [], False, False
    for line in lines:
        if re.match(r"^brand:\s*\S", line):
            out.append(f"brand: {key}")
            saw_brand = True
            continue
        if re.match(r"^(display_name|name):\s*\S", line):
            out.append(f'display_name: "{name}"')
            saw_name = True
            continue
        out.append(line)
    header = [f"# {name} - workspace kit, started from brands/{source}/brand.yaml on {date.today().isoformat()}",
              f"# The palette, arc and grammars below are {source}'s. Re-measure before the first run.", ""]
    if not saw_brand:
        header.append(f"brand: {key}")
    if not saw_name:
        header.append(f'display_name: "{name}"')
    return "\n".join(header + out) + "\n"


def brand_doc(folder: Path) -> dict[str, Any]:
    p = folder / "brand.yaml"
    if not p.exists():
        raise WorkspaceError(f"{p} does not exist")
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise WorkspaceError(f"{p} did not parse to a mapping")
    return doc


def display_name(doc: dict[str, Any], key: str) -> str:
    for k in ("display_name", "name"):
        if isinstance(doc.get(k), str):
            return doc[k]
    if isinstance(doc.get("brand"), dict) and isinstance(doc["brand"].get("name"), str):
        return doc["brand"]["name"]
    return key.replace("-", " ").title()


# ---------------------------------------------------------------- new

def plan_new(key: str, name: str, accent: str = DEFAULT_ACCENT, kind: str = "other",
             source: str | None = None, root: Path | None = None) -> dict[str, Any]:
    """Everything `new` would write, as {relative path: content | None for a folder}."""
    validate_key(key, root)
    if not name or not name.strip():
        raise WorkspaceError("--name is required and cannot be blank")
    if not HEX_RE.match(accent):
        raise WorkspaceError(f"accent {accent!r} must be #RRGGBB")
    if kind not in KINDS:
        raise WorkspaceError(f"kind {kind!r} must be one of {', '.join(KINDS)}")
    brands = _brands(root)
    dest = brands / key
    values = {"key": key, "name": name.strip(), "name_upper": name.strip().upper(),
              "accent": accent.upper(), "kind": kind, "date": date.today().isoformat()}

    files: dict[str, str | None] = {}
    if source:
        # the source may live in the repo even when --root points elsewhere
        src = next((b / source for b in (brands, BRANDS) if (b / source / "brand.yaml").exists()), brands / source)
        if source.startswith("_") or not (src / "brand.yaml").exists():
            raise WorkspaceError(f"--from {source!r}: brands/{source}/brand.yaml does not exist")
        files["brand.yaml"] = _rewrite_kit((src / "brand.yaml").read_text(encoding="utf-8"), key, values["name"], source)
        for p in sorted((src / "styles").glob("*.yaml")) if (src / "styles").exists() else []:
            files[f"styles/{p.name}"] = p.read_text(encoding="utf-8")
    else:
        files["brand.yaml"] = _fill((KIT / "brand.yaml.example").read_text(encoding="utf-8"), values)
    files["references/README.md"] = _fill((KIT / "references.README.md").read_text(encoding="utf-8"), values)
    files["workflows/.gitkeep"] = ""
    files["assets/logo/.gitkeep"] = ""
    files["runs/"] = None
    return {"key": key, "dest": dest, "source": source, "values": values, "files": files}


def create(plan: dict[str, Any]) -> Path:
    dest: Path = plan["dest"]
    if dest.exists():
        raise WorkspaceError(f"{dest} already exists")
    for rel, content in plan["files"].items():
        p = dest / rel
        if content is None:
            p.mkdir(parents=True, exist_ok=True)
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")
    return dest


def describe_plan(plan: dict[str, Any], dry_run: bool) -> str:
    dest: Path = plan["dest"]
    try:
        shown = dest.relative_to(REPO)
    except ValueError:
        shown = dest
    head = "would write" if dry_run else "writing"
    lines = [f"{head} workspace {plan['key']!r} ({plan['values']['name']}) at {shown}"]
    if plan["source"]:
        lines.append(f"  starting from brands/{plan['source']}/brand.yaml and its styles/")
    for rel, content in plan["files"].items():
        if content is None:
            lines.append(f"  {rel:<28} folder (gitignored by {RUNS_IGNORE})")
        else:
            n = content.count("\n")
            lines.append(f"  {rel:<28} {n} line(s)" if n else f"  {rel:<28} empty")
    lines.append("  next: put the logo master at " + str(_get(yaml.safe_load(plan["files"]["brand.yaml"]), "logo.master")))
    lines.append("        measure the palette from the real product and replace the placeholders")
    lines.append(f"        python packages/strategy/workspace.py check {plan['key']}" + (f" --root {dest.parent}" if dest.parent != BRANDS else ""))
    return "\n".join(lines)


# ---------------------------------------------------------------- check

def check_collection(folder: Path) -> tuple[list[str], list[str]]:
    """Errors and warnings for one references/<name>/ folder."""
    errors, warnings = [], []
    media = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in MEDIA_EXT]
    meta_p = folder / "collection.json"
    if not meta_p.exists():
        if media:
            warnings.append(f"references/{folder.name}: {len(media)} media file(s) and no collection.json; "
                            "inspiration only until it has one")
        return errors, warnings
    raw = meta_p.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        warnings.append(f"references/{folder.name}/collection.json starts with a UTF-8 BOM; "
                        "packages/engine/references.py reads it as plain utf-8 and json.loads rejects a BOM. "
                        "Rewrite the file without one.")
    try:
        meta = json.loads(raw.decode("utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        errors.append(f"references/{folder.name}/collection.json is not valid JSON: {e}")
        return errors, warnings
    if not isinstance(meta, dict):
        errors.append(f"references/{folder.name}/collection.json must be an object")
        return errors, warnings
    use, rights, consent = meta.get("use"), meta.get("rights"), meta.get("consent", False)
    if use not in USES:
        errors.append(f"references/{folder.name}: use must be one of {USES}, got {use!r}")
    if rights not in RIGHTS:
        errors.append(f"references/{folder.name}: rights must be one of {RIGHTS}, got {rights!r}")
    if not isinstance(consent, bool):
        errors.append(f"references/{folder.name}: consent must be true or false")
    if use == "data" and rights == "unclear":
        errors.append(f"references/{folder.name}: use: data needs rights owned or licensed; unclear can only inspire")
    if consent is True and not any("release" in str(n).lower() for n in meta.get("notes", [])):
        warnings.append(f"references/{folder.name}: consent is true; note where the written release is kept")
    if meta.get("name") and meta["name"] != folder.name:
        warnings.append(f"references/{folder.name}: collection.json name is {meta['name']!r}, folder is {folder.name!r}")
    return errors, warnings


def check(key: str, root: Path | None = None) -> Report:
    brands = _brands(root)
    folder = brands / key
    rep = Report(key=key, root=folder)
    if key.startswith("_") or key in RESERVED:
        rep.errors.append(f"{key!r} is a studio folder, not a workspace")
        return rep
    if not folder.is_dir():
        rep.errors.append(f"brands/{key}/ does not exist")
        return rep
    try:
        doc = brand_doc(folder)
    except (WorkspaceError, yaml.YAMLError) as e:
        rep.errors.append(str(e))
        return rep

    for spec, why in REQUIRED:
        if not _has(doc, spec):
            rep.errors.append(f"brand.yaml is missing {spec.replace('|', ' or ')}: {why}")
    if isinstance(doc.get("brand"), str) and doc["brand"] != key:
        rep.errors.append(f"brand.yaml says brand: {doc['brand']!r} but the folder is {key!r}")

    measured = _get(doc, "palette.measured")
    if isinstance(measured, dict):
        bad = {k: v for k, v in measured.items() if isinstance(v, str) and not HEX_RE.match(v)}
        if bad:
            rep.errors.append(f"palette.measured has non-#RRGGBB values: {bad}")
        if not any(isinstance(v, str) and HEX_RE.match(v) for v in measured.values()):
            rep.errors.append("palette.measured has no #RRGGBB value")
    elif measured is not None:
        rep.errors.append("palette.measured must be a mapping of names to #RRGGBB")

    rule = _get(doc, "logo.rule")
    if rule and rule != "COMPOSITE_ONLY":
        rep.errors.append(f"logo.rule is {rule!r}; the compositor only knows COMPOSITE_ONLY")
    master = _get(doc, "logo.master")
    if isinstance(master, str):
        if not (folder / master).exists():
            rep.warnings.append(f"logo master declared but absent: {master}; put the file there before compositing")

    for spec, why in RECOMMENDED:
        if not _has(doc, spec):
            rep.warnings.append(f"brand.yaml has no {spec}: {why}")

    refs = folder / "references"
    if refs.is_dir():
        if not (refs / "README.md").exists():
            rep.warnings.append("references/README.md is missing; the rights rules should sit next to the files")
        for sub in sorted(p for p in refs.iterdir() if p.is_dir()):
            e, w = check_collection(sub)
            rep.errors += e
            rep.warnings += w
        n = sum(1 for p in refs.iterdir() if p.is_dir() and (p / "collection.json").exists())
        rep.info.append(f"{n} reference collection(s) with collection.json")
    else:
        rep.warnings.append("no references/ folder")

    wfs = folder / "workflows"
    if wfs.is_dir():
        rep.info.append(f"{len(list(wfs.glob('*.studio.json')))} workflow(s)")
    else:
        rep.warnings.append("no workflows/ folder; the author and the canvas write *.studio.json there")

    styles = folder / "styles"
    if not styles.is_dir() or not [p for p in styles.glob("*.yaml") if p.stem != "index"]:
        rep.warnings.append("no style grammar under styles/; brandkit needs at least one to build a request")

    if GITIGNORE.exists() and RUNS_IGNORE not in GITIGNORE.read_text(encoding="utf-8"):
        rep.warnings.append(f".gitignore no longer has {RUNS_IGNORE}; run results would be tracked")
    else:
        rep.info.append(f"runs/ is gitignored ({RUNS_IGNORE})")
    return rep


def list_workspaces(root: Path | None = None) -> list[dict[str, Any]]:
    brands = _brands(root)
    out = []
    if not brands.is_dir():
        return out
    for d in sorted(brands.iterdir()):
        if not d.is_dir() or d.name.startswith("_") or not (d / "brand.yaml").exists():
            continue
        try:
            doc = brand_doc(d)
        except (WorkspaceError, yaml.YAMLError):
            doc = {}
        rep = check(d.name, root)
        out.append({"key": d.name, "name": display_name(doc, d.name),
                    "kind": doc.get("kind") or "", "accent": _get(doc, "palette.measured.accent") or "",
                    "workflows": len(list((d / "workflows").glob("*.studio.json"))) if (d / "workflows").is_dir() else 0,
                    "collections": sum(1 for p in (d / "references").iterdir() if p.is_dir() and (p / "collection.json").exists())
                    if (d / "references").is_dir() else 0,
                    "ok": rep.ok, "errors": len(rep.errors), "warnings": len(rep.warnings)})
    return out


# ---------------------------------------------------------------- cli

def _print_report(rep: Report) -> None:
    print(f"{rep.key}: {'ok' if rep.ok else 'FAIL'}  ({len(rep.errors)} error(s), {len(rep.warnings)} warning(s))")
    for e in rep.errors:
        print(f"  error    {e}")
    for w in rep.warnings:
        print(f"  warning  {w}")
    for i in rep.info:
        print(f"  info     {i}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="scaffold brands/<key>/ from brands/_kit/")
    n.add_argument("key", help="folder name: lowercase, a-z 0-9 and hyphens")
    n.add_argument("--name", required=True, help="display name, e.g. \"Demo Brand\"")
    n.add_argument("--accent", default=DEFAULT_ACCENT, help="#RRGGBB accent the UI shows for the workspace")
    n.add_argument("--kind", default="other", choices=KINDS, help="what kind of brand this is")
    n.add_argument("--from", dest="source", metavar="KEY", help="start from this workspace's brand.yaml and styles/")
    n.add_argument("--dry-run", action="store_true", help="print the plan; write nothing")
    n.add_argument("--root", type=Path, help="a brands/ folder other than the repo's (tests)")

    l = sub.add_parser("list", help="every workspace with its name, kind and check status")
    l.add_argument("--root", type=Path)
    l.add_argument("--json", action="store_true")

    c = sub.add_parser("check", help="validate one workspace's kit and references")
    c.add_argument("key")
    c.add_argument("--root", type=Path)
    c.add_argument("--json", action="store_true")

    a = ap.parse_args(argv)
    try:
        if a.cmd == "new":
            plan = plan_new(a.key, a.name, a.accent, a.kind, a.source, a.root)
            print(describe_plan(plan, a.dry_run))
            if a.dry_run:
                return 0
            create(plan)
            rep = check(a.key, a.root)
            _print_report(rep)
            return 0 if rep.ok else 1
        if a.cmd == "list":
            rows = list_workspaces(a.root)
            if a.json:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
                return 0
            if not rows:
                print("no workspaces (a workspace is brands/<key>/brand.yaml)")
                return 0
            w = max(len(r["key"]) for r in rows)
            for r in rows:
                status = "ok" if r["ok"] else f"{r['errors']} error(s)"
                print(f"{r['key']:<{w}}  {r['name']:<24} {r['kind'] or '-':<10} {r['accent'] or '-':<8} "
                      f"{r['workflows']:>3} workflow(s) {r['collections']:>3} collection(s)  {status}, {r['warnings']} warning(s)")
            return 0
        if a.cmd == "check":
            rep = check(a.key, a.root)
            if a.json:
                print(json.dumps(rep.to_dict(), indent=2, ensure_ascii=False))
            else:
                _print_report(rep)
            return 0 if rep.ok else 1
    except WorkspaceError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
