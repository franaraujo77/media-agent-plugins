from dataclasses import dataclass

DEFAULT_FPS = 30
DEFAULT_PRESET = "landscape"

_DIMENSIONS: dict[str, tuple[int, int]] = {
    "reel": (1080, 1920),
    "story": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
}


@dataclass(frozen=True)
class Preset:
    name: str
    width: int
    height: int
    fps: int = DEFAULT_FPS


def resolve_preset(name: str, fps: int | None = None) -> Preset:
    if name not in _DIMENSIONS:
        known = ", ".join(sorted(_DIMENSIONS))
        raise ValueError(f"Unknown preset {name!r}. Known presets: {known}")
    width, height = _DIMENSIONS[name]
    return Preset(name=name, width=width, height=height, fps=fps or DEFAULT_FPS)
