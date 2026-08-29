import glob
import json
from dataclasses import dataclass
from pathlib import Path

from plugins.video.src.encode import probe_duration, probe_image_size
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
    found = sorted(found)  # full-path lexicographic order, per the spec
    if not found:
        raise ValueError(f"No images matched {spec!r}")
    return found


def validate_images(slides: list[Slide]) -> None:
    missing = [str(s.image) for s in slides if not s.image.exists()]
    if missing:
        raise ValueError("Image files not found:\n  " + "\n  ".join(missing))


def validate_audio(sb: "Storyboard") -> None:
    """Fail with the module's actionable message rather than a raw `ffprobe failed`."""
    if sb.audio is not None and not sb.audio.exists():
        raise ValueError(f"Audio file not found:\n  {sb.audio}")


CROP_WARN_THRESHOLD = 0.15


def overlap_total(sb: Storyboard) -> float:
    return sum(s.transition_seconds for s in sb.slides[1:] if s.transition != "cut")


def total_duration(sb: Storyboard) -> float:
    return sum(s.seconds or 0.0 for s in sb.slides) - overlap_total(sb)


def resolve_durations(sb: Storyboard) -> Storyboard:
    explicit = [i for i, s in enumerate(sb.slides) if s.seconds is not None]
    omitted = [i for i, s in enumerate(sb.slides) if s.seconds is None]

    if sb.audio is None:
        for s in sb.slides:
            if s.seconds is None:
                s.seconds = DEFAULT_SECONDS
        return sb

    audio_seconds = probe_duration(sb.audio)

    if explicit and omitted:
        raise ValueError(
            "Cannot mix explicit and omitted 'seconds' when audio is present. "
            f"Slides with 'seconds': {explicit}. Slides without: {omitted}. "
            "Set 'seconds' on every slide, or on none of them."
        )

    if omitted:
        per_slide = (audio_seconds + overlap_total(sb)) / len(sb.slides)
        for s in sb.slides:
            s.seconds = per_slide
        return sb

    drift = total_duration(sb) - audio_seconds
    if abs(drift) > 0.5:
        print(
            f"Warning: video is {total_duration(sb):.1f}s but audio is "
            f"{audio_seconds:.1f}s ({drift:+.1f}s). Output will be trimmed to the shorter."
        )
    return sb


def crop_warnings(sb: Storyboard) -> list[str]:
    if sb.fit != "cover":
        return []
    target = sb.preset.width / sb.preset.height
    warnings = []
    for s in sb.slides:
        width, height = probe_image_size(s.image)
        source = width / height
        # cover scales to fill, so the discarded fraction is along the longer axis
        kept = min(source, target) / max(source, target)
        discarded = 1.0 - kept
        if discarded > CROP_WARN_THRESHOLD:
            warnings.append(
                f"{s.image}: {width}x{height} cropped to "
                f"{sb.preset.width}x{sb.preset.height} discards {discarded:.0%} of the image"
            )
    return warnings
