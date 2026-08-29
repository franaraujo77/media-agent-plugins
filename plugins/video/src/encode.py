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


def mux_audio(video: Path, audio: Path | None, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    if audio is None:
        run_ffmpeg(["-i", str(video), "-c", "copy", str(output)])
        return output
    run_ffmpeg([
        "-i", str(video),
        "-i", str(audio),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-shortest",
        "-movflags", "+faststart",
        str(output),
    ])
    return output
