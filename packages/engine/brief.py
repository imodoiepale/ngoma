"""What the director engine is told, and what it decides. Plain dataclasses, JSON in and out."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

USES = ("inspiration", "data")
RIGHTS = ("owned", "licensed", "unclear")
ANGLE_CHOICES = (3, 5, 10, 20)


@dataclass
class RefCollection:
    """A folder of references. `use: data` feeds generation directly; `inspiration` only
    shapes prompts. Anything with unclear rights can only inspire."""
    name: str
    kind: str = "image"              # image | video | audio
    use: str = "inspiration"
    rights: str = "unclear"
    consent: bool = False            # a real person's likeness, released in writing
    path: str = ""                   # brands/<client>/references/<name>
    count: int = 0

    def may_feed(self) -> bool:
        return self.use == "data" and self.rights in ("owned", "licensed")


@dataclass
class Role:
    name: str
    consent: bool = False
    fictional: bool = True
    ref_collection: str = ""        # a RefCollection name with the role's photos
    lora: str = ""                  # a trained character LoRA file on the pod, when one exists


@dataclass
class EngineBrief:
    client: str
    title: str
    idea: str = ""                   # what the piece is, in the user's words
    profile: str = "lookbook"        # the craft: beats, narration, locks (profiles.yaml)
    preset: str = "minimal-editorial"  # the look (directors.yaml)
    ratio: str = "9:16"
    theme: str | None = None         # light | dark for profiles that have themes
    scenes: int = 3
    scene_hints: list[str] = field(default_factory=list)   # "rooftop at golden hour", ...
    angles_per_scene: int = 5
    seeds_per_angle: int = 1
    video_seconds: list[int] = field(default_factory=lambda: [4])
    vfx: list[str] = field(default_factory=list)
    roles: list[Role] = field(default_factory=list)
    refs: list[RefCollection] = field(default_factory=list)
    adult: bool = False
    outputs: list[str] = field(default_factory=lambda: ["export"])
    language: str | None = None
    run_mode: str = "dry-run"

    def by_purpose(self, purpose: str) -> list[RefCollection]:
        return [r for r in self.refs if r.name.startswith(purpose)]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "EngineBrief":
        d = dict(d)
        d["roles"] = [Role(**r) for r in d.get("roles", [])]
        d["refs"] = [RefCollection(**r) for r in d.get("refs", [])]
        return EngineBrief(**d)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Scene:
    n: int
    title: str
    setting: str
    action: str
    framing: str
    blocking: str
    duration_s: int
    roles: list[str] = field(default_factory=list)
    wardrobe: str = ""               # RefCollection name
    location: str = ""
    jewellery: str = ""


@dataclass
class ShotSpec:
    scene: int
    angle: int
    camera: str                      # "wide", "close", ...
    lens: str
    fragments: list[str]


def check_brief(b: EngineBrief) -> list[str]:
    problems = []
    if b.scenes < 1 or b.scenes > 40:
        problems.append("scenes must be between 1 and 40")
    if b.angles_per_scene not in ANGLE_CHOICES:
        problems.append(f"angles_per_scene must be one of {ANGLE_CHOICES}")
    if not b.video_seconds or any(s < 3 or s > 30 for s in b.video_seconds):
        problems.append("video_seconds must be 3 to 30")
    for r in b.refs:
        if r.use not in USES or r.rights not in RIGHTS:
            problems.append(f"reference {r.name}: use must be one of {USES}, rights one of {RIGHTS}")
    for role in b.roles:
        if not role.fictional and not role.consent:
            problems.append(f"role {role.name} is a real person without a consent release")
    return problems
