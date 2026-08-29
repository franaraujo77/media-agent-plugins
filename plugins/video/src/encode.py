import shutil
import subprocess
from pathlib import Path

FFMPEG_MISSING_HINT = "install with: brew install ffmpeg"
CHROMIUM_MISSING_HINT = "install with: playwright install chromium"

_HINTS = {"ffmpeg": FFMPEG_MISSING_HINT, "ffprobe": FFMPEG_MISSING_HINT}


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        hint = _HINTS.get(name, "")
        raise RuntimeError(f"{name} not found on PATH — {hint}")


def run_ffmpeg(args: list[str]) -> None:
    require_binary("ffmpeg")
    cmd = ["ffmpeg", "-y", "-loglevel", "error"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({result.returncode}):\n{result.stderr}")


def _run_ffprobe(args: list[str]) -> str:
    require_binary("ffprobe")
    cmd = ["ffprobe", "-v", "error"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed ({result.returncode}):\n{result.stderr}")
    return result.stdout.strip()


def probe_duration(path: Path) -> float:
    out = _run_ffprobe([
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])
    return float(out)


def probe_image_size(path: Path) -> tuple[int, int]:
    out = _run_ffprobe([
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0:s=x",
        str(path),
    ]).replace("x", ",")
    width, height = out.split(",")[:2]
    return int(width), int(height)


FRAME_PATTERN = "f%05d.png"


def frames_to_video(frames_dir: Path, fps: int, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-framerate", str(fps),
        "-i", str(frames_dir / FRAME_PATTERN),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(output),
    ])
    return output


AUDIO_CODEC_ARGS = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
TRACK_ATTRS = ("file", "volume", "start", "duration", "fade_in", "fade_out", "loop")


def _as_track(track) -> dict | None:
    """Accept a storyboard AudioTrack or a bare path. Duck-typed rather than
    imported, because storyboard imports this module."""
    if track is None:
        return None
    if isinstance(track, (str, Path)):
        track = Path(track)
        return {"file": track, "volume": 1.0, "start": 0.0, "duration": None,
                "fade_in": 0.0, "fade_out": 0.0, "loop": False}
    return {name: getattr(track, name) for name in TRACK_ATTRS}


def _input_args(track: dict) -> list[str]:
    args = []
    if track["loop"]:
        args += ["-stream_loop", "-1"]
    if track["start"]:
        args += ["-ss", str(track["start"])]
    if track["duration"] is not None:
        args += ["-t", str(track["duration"])]
    return args + ["-i", str(track["file"])]


def _filter_steps(track: dict, label: str, video_seconds: float | None) -> list[str]:
    steps = []
    if track["volume"] != 1.0:
        steps.append(f"volume={track['volume']:g}")
    if track["fade_in"]:
        steps.append(f"afade=t=in:st=0:d={track['fade_in']}")
    if track["fade_out"]:
        # Fade from the end of whatever the track will actually play: its own
        # trimmed length if one was set, else the length of the video it rides on.
        length = track["duration"] if track["duration"] is not None else video_seconds
        if length is None:
            raise ValueError(
                f"'{label}' sets fade_out but its length is unknown. Set 'duration' "
                "on the track, or pass video_seconds to mux_audio()."
            )
        steps.append(f"afade=t=out:st={round(length - track['fade_out'], 3)}:d={track['fade_out']}")
    return steps


def mux_audio(video: Path, audio=None, output: Path = None, music=None,
              video_seconds: float | None = None) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    tracks = [(label, t) for label, t in
              (("audio", _as_track(audio)), ("music", _as_track(music))) if t]

    if not tracks:
        run_ffmpeg(["-i", str(video), "-c", "copy",
                    "-movflags", "+faststart", str(output)])
        return output

    inputs = ["-i", str(video)]
    for _, track in tracks:
        inputs += _input_args(track)

    chains = [_filter_steps(track, label, video_seconds) for label, track in tracks]
    if tracks[0][0] == "music":
        # A bed must never shorten the video: pad it with silence so that -shortest
        # ends on the video rather than on a music file shorter than the slides.
        chains[0].append("apad")

    if len(tracks) == 1 and not chains[0]:
        mapping = ["-map", "0:v", "-map", "1:a"]
        graph = []
    else:
        # anull keeps a track that needs no processing addressable by the mixer.
        parts = [f"[{i + 1}:a]{','.join(steps or ['anull'])}[a{i}]"
                 for i, steps in enumerate(chains)]
        if len(tracks) == 2:
            # normalize=0 so the declared volumes are the ones you hear; amix
            # otherwise divides every input by the number of inputs. duration=first
            # ends the mix on the primary track — the bed never extends or truncates it.
            parts.append("[a0][a1]amix=inputs=2:normalize=0:duration=first[aout]")
        else:
            parts[-1] = parts[-1].replace("[a0]", "[aout]")
        graph = ["-filter_complex", ";".join(parts)]
        mapping = ["-map", "0:v", "-map", "[aout]"]

    run_ffmpeg(
        inputs + graph + mapping
        + ["-c:v", "copy"] + AUDIO_CODEC_ARGS
        + ["-shortest", "-movflags", "+faststart", str(output)]
    )
    return output
