import argparse
import sys
import tempfile
from pathlib import Path

from plugins.video.src.backends import ffmpeg_backend, browser_backend
from plugins.video.src.encode import mux_audio
from plugins.video.src.presets import DEFAULT_PRESET
from plugins.video.src.storyboard import (
    Storyboard,
    build_storyboard,
    collect_images,
    crop_warnings,
    load_storyboard,
    resolve_durations,
    total_duration,
    validate_audio,
    validate_images,
)

BACKENDS = {"ffmpeg": ffmpeg_backend, "browser": browser_backend}


def select_backend(sb: Storyboard) -> tuple[str, str]:
    if sb.backend is not None:
        if sb.backend not in BACKENDS:
            raise ValueError(
                f"Unknown backend {sb.backend!r}. Allowed: {', '.join(sorted(BACKENDS))}"
            )
        return sb.backend, f"explicit backend: {sb.backend}"
    captioned = [i for i, s in enumerate(sb.slides) if s.caption]
    if captioned:
        return "browser", f"{len(captioned)} of {len(sb.slides)} slides have captions"
    return "ffmpeg", "no slide has a caption"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render images plus optional audio into an MP4."
    )
    parser.add_argument("storyboard", nargs="?", help="Path to a storyboard JSON file")
    parser.add_argument("--images", help="Glob or directory of images")
    parser.add_argument("--audio", help="Primary audio track to mux; sets the video length")
    parser.add_argument("--music", help="Music bed mixed under --audio, trimmed to fit")
    parser.add_argument("--music-volume", type=float, default=None,
                        help="Gain for --music (1.0 = unchanged, 0.15 = a quiet bed)")
    parser.add_argument("--output", help="Output path (default output/video.mp4)")
    parser.add_argument("--preset", default=None,
                        help="reel | story | square | landscape")
    parser.add_argument("--fit", default=None, help="cover | contain")
    parser.add_argument("--backend", default=None, help="ffmpeg | browser")
    parser.add_argument("--seconds", type=float, default=None,
                        help="Uniform per-slide duration")
    parser.add_argument("--fps", type=int, default=None)
    return parser.parse_args(argv)


STORYBOARD_EXCLUSIVE_FLAGS = (
    "images", "audio", "output", "preset", "fit", "backend", "seconds", "fps",
    "music", "music_volume",
)


def storyboard_from_args(args: argparse.Namespace) -> Storyboard:
    if args.storyboard:
        # Spec: flags and a storyboard path are mutually exclusive; passing both is
        # an error rather than a silent precedence rule.
        supplied = [f"--{n.replace('_', '-')}" for n in STORYBOARD_EXCLUSIVE_FLAGS
                    if getattr(args, n) is not None]
        if supplied:
            raise ValueError(
                f"A storyboard path and {', '.join(supplied)} are mutually exclusive. "
                "Pass a storyboard, or the flags — not both. Set these fields inside "
                "the storyboard JSON instead."
            )
        return load_storyboard(Path(args.storyboard))
    if not args.images:
        raise ValueError("Pass a storyboard path or --images.")

    slides = [{"image": str(p)} for p in collect_images(args.images)]
    if args.seconds is not None:
        for slide in slides:
            slide["seconds"] = args.seconds

    if args.music_volume is not None and not args.music:
        raise ValueError("--music-volume needs a --music file to apply to.")

    data: dict = {"slides": slides, "preset": args.preset or DEFAULT_PRESET}
    if args.audio:
        data["audio"] = args.audio
    if args.music:
        music: dict = {"file": args.music}
        if args.music_volume is not None:
            music["volume"] = args.music_volume
        data["music"] = music
    if args.output:
        data["output"] = args.output
    if args.fit:
        data["fit"] = args.fit
    if args.backend:
        data["backend"] = args.backend
    if args.fps:
        data["fps"] = args.fps
    return build_storyboard(data)


def run(argv: list[str]) -> Path:
    sb = storyboard_from_args(parse_args(argv))
    validate_images(sb.slides)
    validate_audio(sb)
    resolve_durations(sb)

    for warning in crop_warnings(sb):
        print(f"Warning: {warning}")

    name, reason = select_backend(sb)
    print(f"Backend: {name} ({reason})")

    with tempfile.TemporaryDirectory() as tmp:
        silent = BACKENDS[name].render(sb, Path(tmp))
        sb.output.parent.mkdir(parents=True, exist_ok=True)
        output = mux_audio(silent, sb.audio, sb.output, music=sb.music,
                           video_seconds=total_duration(sb))

    print(f"Rendered → {output}")
    return output


if __name__ == "__main__":
    try:
        run(sys.argv[1:])
    except (ValueError, RuntimeError) as exc:
        sys.exit(f"Error: {exc}")
