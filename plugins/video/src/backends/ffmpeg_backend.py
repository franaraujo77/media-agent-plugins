from pathlib import Path

from plugins.video.src.encode import run_ffmpeg
from plugins.video.src.storyboard import Storyboard

ZOOM_MAX = 1.18
PAN_SHIFT = 0.03


def _fit_chain(sb: Storyboard) -> str:
    width, height = sb.preset.width, sb.preset.height
    if sb.fit == "contain":
        return (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black")
    return (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}")


def _zoom_expr(motion: str, frames: int) -> tuple[str, str, str]:
    """Return (z, x, y) zoompan expressions for a motion type."""
    centre_x = "iw/2-(iw/zoom/2)"
    centre_y = "ih/2-(ih/zoom/2)"
    step = (ZOOM_MAX - 1.0) / max(frames, 1)
    if motion == "zoom-in":
        return (f"min(zoom+{step:.6f},{ZOOM_MAX})", centre_x, centre_y)
    if motion == "zoom-out":
        return (f"if(eq(on,0),{ZOOM_MAX},max(zoom-{step:.6f},1.0))", centre_x, centre_y)
    if motion == "pan-left":
        return (f"{1 + PAN_SHIFT:.3f}", f"iw/2-(iw/zoom/2)-(on/{frames})*(iw*{PAN_SHIFT})", centre_y)
    if motion == "pan-right":
        return (f"{1 + PAN_SHIFT:.3f}", f"iw/2-(iw/zoom/2)+(on/{frames})*(iw*{PAN_SHIFT})", centre_y)
    return ("1", centre_x, centre_y)


def build_filtergraph(sb: Storyboard) -> tuple[str, str]:
    width, height, fps = sb.preset.width, sb.preset.height, sb.preset.fps
    parts: list[str] = []

    for i, slide in enumerate(sb.slides):
        frames = max(int(round((slide.seconds or 0.0) * fps)), 1)
        z, x, y = _zoom_expr(slide.motion, frames)
        parts.append(
            f"[{i}:v]{_fit_chain(sb)},scale=8000:-1,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={width}x{height}:fps={fps},"
            f"setsar=1[v{i}]"
        )

    current = "v0"
    timeline = sb.slides[0].seconds or 0.0
    for i in range(1, len(sb.slides)):
        slide = sb.slides[i]
        label = f"x{i}"
        if slide.transition == "cut":
            parts.append(f"[{current}][v{i}]concat=n=2:v=1:a=0[{label}]")
            timeline += slide.seconds or 0.0
        else:
            offset = timeline - slide.transition_seconds
            parts.append(
                f"[{current}][v{i}]xfade=transition=fade:"
                f"duration={slide.transition_seconds}:offset={offset:.3f}[{label}]"
            )
            timeline += (slide.seconds or 0.0) - slide.transition_seconds
        current = label

    return ";".join(parts), current


def build_args(sb: Storyboard, output: Path) -> list[str]:
    args: list[str] = []
    for slide in sb.slides:
        # Exactly one input frame per slide. zoompan's d= parameter alone determines
        # output duration; if the input instead emitted many frames (e.g. -t as an
        # input option without -framerate 1), each would be multiplied by d and the
        # video would run many times too long.
        args += ["-loop", "1", "-framerate", "1", "-t", "1", "-i", str(slide.image)]
    graph, final = build_filtergraph(sb)
    args += [
        "-filter_complex", graph,
        "-map", f"[{final}]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(output),
    ]
    return args


def render(sb: Storyboard, workdir: Path) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    output = workdir / "silent.mp4"
    run_ffmpeg(build_args(sb, output))
    return output
