import glob
import json
from dataclasses import dataclass
from pathlib import Path

from plugins.video.src.presets import Preset, resolve_preset, DEFAULT_PRESET

DEFAULT_SECONDS = 4.0
DEFAULT_TRANSITION_SECONDS = 0.5
MOTIONS = {"zoom-in", "zoom-out", "pan-left", "pan-right", "none"}
TRANSITIONS = {"fade", "cut"}
FITS = {"cover", "contain"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_OUTPUT = Path("output/video.mp4")


@dataclass
class Slide:
    image: Path
    caption: str | None
    seconds: float | None
    motion: str
    transition: str
    transition_seconds: float


@dataclass
class Storyboard:
    preset: Preset
    slides: list[Slide]
    audio: Path | None = None
    output: Path = DEFAULT_OUTPUT
    fit: str = "cover"
    backend: str | None = None


def _check(value: str, allowed: set[str], label: str) -> str:
    if value not in allowed:
        raise ValueError(f"Unknown {label} {value!r}. Allowed: {', '.join(sorted(allowed))}")
    return value


def _build_slide(raw: dict, index: int) -> Slide:
    if not raw.get("image"):
        raise ValueError(f"Slide {index} is missing the required 'image' field")
    return Slide(
        image=Path(raw["image"]),
        caption=raw.get("caption") or None,
        seconds=float(raw["seconds"]) if raw.get("seconds") is not None else None,
        motion=_check(raw.get("motion", "zoom-in"), MOTIONS, "motion"),
        transition=_check(raw.get("transition", "fade"), TRANSITIONS, "transition"),
        transition_seconds=float(raw.get("transition_seconds", DEFAULT_TRANSITION_SECONDS)),
    )


def build_storyboard(data: dict) -> Storyboard:
    raw_slides = data.get("slides") or []
    if not raw_slides:
        raise ValueError("Storyboard must contain at least one entry in 'slides'")
    return Storyboard(
        preset=resolve_preset(data.get("preset", DEFAULT_PRESET), data.get("fps")),
        slides=[_build_slide(raw, i) for i, raw in enumerate(raw_slides)],
        audio=Path(data["audio"]) if data.get("audio") else None,
        output=Path(data.get("output", DEFAULT_OUTPUT)),
        fit=_check(data.get("fit", "cover"), FITS, "fit"),
        backend=data.get("backend"),
    )


def load_storyboard(path: Path) -> Storyboard:
    return build_storyboard(json.loads(Path(path).read_text()))


def collect_images(spec: str) -> list[Path]:
    target = Path(spec)
    if target.is_dir():
        found = [p for p in target.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS]
    else:
        found = [Path(p) for p in glob.glob(spec)]
    found = sorted(found, key=lambda p: p.name)
    if not found:
        raise ValueError(f"No images matched {spec!r}")
    return found


def validate_images(slides: list[Slide]) -> None:
    missing = [str(s.image) for s in slides if not s.image.exists()]
    if missing:
        raise ValueError("Image files not found:\n  " + "\n  ".join(missing))
