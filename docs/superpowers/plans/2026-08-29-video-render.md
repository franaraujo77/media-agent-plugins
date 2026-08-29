# Video Render Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone `video` plugin that renders a set of images plus an optional audio track into a finished MP4, using only ffmpeg and Playwright already present on this machine.

**Architecture:** A JSON storyboard (or equivalent CLI flags) is normalized into a `Storyboard` dataclass, durations are resolved against the audio track, and one of two backends renders a silent constant-frame-rate MP4 — `ffmpeg` (zoompan Ken Burns + xfade) for pure imagery, `browser` (HTML/CSS animated via the Web Animations API, seeked frame-by-frame and captured by Playwright) when any slide carries a caption. A shared `encode` module then muxes the audio. Backends never touch audio, so each is independently testable and replaceable.

**Tech Stack:** Python 3, ffmpeg/ffprobe, Playwright (Chromium), pytest + pytest-mock.

**Spec:** `docs/superpowers/specs/2026-08-29-video-render-design.md`

## Global Constraints

- **No new Python dependencies.** Only `playwright>=1.40.0`, `pytest>=8.0.0`, `pytest-mock>=3.12.0` — all already used by the media plugin.
- **Never import Pillow.** Image dimensions are probed with `ffprobe`. Pillow is installed on this machine but is not declared in any `requirements.txt`, so importing it would be an undeclared dependency.
- **`page.screenshot()` must never be passed `animations="disabled"`.** It fast-forwards finite animations to completion and silently produces a valid MP4 with correct dimensions, fps, frame count and duration containing zero motion.
- **`zoompan` must always be preceded by an upscale** (`scale=8000:-1`). Without it, integer pan offsets make the motion visibly step.
- Default fps is `30` for every preset.
- Default slide duration is `4.0` seconds; default `transition_seconds` is `0.5`.
- Output defaults to `output/video.mp4`.
- Playwright is always wrapped in `try/finally` so the browser closes on error (per `CLAUDE.md`).
- ffmpeg failures surface full stderr; errors use `sys.exit("Error: ...")` matching `tts_generate.py`.
- Code style follows `plugins/media/src/`: module-level functions with type hints, a `run()` entry point, `if __name__ == "__main__":` at the bottom.

## File Structure

| File | Responsibility |
|---|---|
| `plugins/video/.claude-plugin/plugin.json` | Plugin manifest |
| `plugins/video/requirements.txt` | Standalone dependency declaration |
| `plugins/video/__init__.py` | Package marker (required for `plugins.video.src.*` imports) |
| `plugins/video/src/__init__.py` | Package marker |
| `plugins/video/src/presets.py` | Named preset → dimensions + fps. No other logic. |
| `plugins/video/src/encode.py` | All ffmpeg/ffprobe subprocess calls: binary checks, probes, frames→video, audio mux |
| `plugins/video/src/storyboard.py` | Parse/normalize/validate input; resolve durations; crop warnings |
| `plugins/video/src/backends/__init__.py` | Package marker |
| `plugins/video/src/backends/ffmpeg_backend.py` | Filtergraph construction + render |
| `plugins/video/src/backends/browser_backend.py` | Scene HTML generation + Playwright frame capture |
| `plugins/video/src/video_render.py` | CLI parsing, backend selection, orchestration |
| `plugins/video/skills/video-render/SKILL.md` | Skill definition |
| `pytest.ini` | Register the `integration` marker |
| `tests/test_presets.py` | Preset resolution |
| `tests/test_encode.py` | Probes, binary checks, mux |
| `tests/test_storyboard.py` | Parsing, validation, duration rules |
| `tests/test_video_render.py` | Backend selection, filtergraph guards, frame-difference, E2E smoke |

Every ffmpeg/ffprobe subprocess call lives in `encode.py`. Backends build argument lists and hand them over; they never call `subprocess` themselves. This keeps subprocess mocking confined to one module.

---

### Task 1: Plugin scaffold and presets

**Files:**
- Create: `plugins/video/.claude-plugin/plugin.json`
- Create: `plugins/video/requirements.txt`
- Create: `plugins/video/__init__.py`
- Create: `plugins/video/src/__init__.py`
- Create: `plugins/video/src/backends/__init__.py`
- Create: `plugins/video/src/presets.py`
- Create: `pytest.ini`
- Test: `tests/test_presets.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Preset` (frozen dataclass with `.name: str`, `.width: int`, `.height: int`, `.fps: int`), `resolve_preset(name: str, fps: int | None = None) -> Preset`, `DEFAULT_FPS: int = 30`, `DEFAULT_PRESET: str = "landscape"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_presets.py`:

```python
import pytest
from plugins.video.src.presets import resolve_preset, DEFAULT_FPS, DEFAULT_PRESET


def test_reel_is_vertical_1080x1920():
    p = resolve_preset("reel")
    assert (p.width, p.height) == (1080, 1920)


def test_story_matches_reel():
    assert resolve_preset("story").width == resolve_preset("reel").width
    assert resolve_preset("story").height == resolve_preset("reel").height


def test_square_and_landscape():
    assert (resolve_preset("square").width, resolve_preset("square").height) == (1080, 1080)
    assert (resolve_preset("landscape").width, resolve_preset("landscape").height) == (1920, 1080)


def test_default_fps_is_30():
    assert resolve_preset("reel").fps == DEFAULT_FPS == 30


def test_fps_override():
    assert resolve_preset("reel", fps=60).fps == 60


def test_default_preset_is_landscape():
    assert DEFAULT_PRESET == "landscape"


def test_unknown_preset_raises_naming_the_value():
    with pytest.raises(ValueError) as exc:
        resolve_preset("tiktok")
    assert "tiktok" in str(exc.value)


def test_preset_is_immutable():
    p = resolve_preset("reel")
    with pytest.raises(Exception):
        p.width = 999
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_presets.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plugins.video'`

- [ ] **Step 3: Create the package markers and manifest**

```bash
mkdir -p plugins/video/.claude-plugin plugins/video/src/backends plugins/video/skills/video-render
touch plugins/video/__init__.py plugins/video/src/__init__.py plugins/video/src/backends/__init__.py
```

`plugins/video/.claude-plugin/plugin.json`:

```json
{
  "name": "video",
  "version": "0.1.0",
  "description": "Render images and audio into a finished MP4 using local ffmpeg and Playwright. No external AI service.",
  "author": { "name": "francisaraujo", "email": "francis.araujo@gmail.com" },
  "skills": ["./skills/video-render"]
}
```

`plugins/video/requirements.txt`:

```
playwright>=1.40.0
pytest>=8.0.0
pytest-mock>=3.12.0
```

`pytest.ini`:

```ini
[pytest]
markers =
    integration: tests that shell out to real ffmpeg or launch a real browser
```

- [ ] **Step 4: Write the presets module**

`plugins/video/src/presets.py`:

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_presets.py -v`
Expected: PASS (8 tests)

- [ ] **Step 6: Verify the plugin manifest validates**

Run: `bash scripts/validate-plugins.sh`
Expected: `✔ Validation passed` for all three plugins, including `plugins/video`.

- [ ] **Step 7: Commit**

```bash
git add plugins/video pytest.ini tests/test_presets.py
git commit -m "feat(video): scaffold plugin and add preset resolution"
```

---

### Task 2: ffmpeg/ffprobe helpers

**Files:**
- Create: `plugins/video/src/encode.py`
- Test: `tests/test_encode.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `require_binary(name: str) -> None`, `run_ffmpeg(args: list[str]) -> None`, `probe_duration(path: Path) -> float`, `probe_image_size(path: Path) -> tuple[int, int]`, `FFMPEG_MISSING_HINT: str`, `CHROMIUM_MISSING_HINT: str`.

`run_ffmpeg` takes arguments *after* the `ffmpeg` binary name and always prepends `-y -loglevel error`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_encode.py`:

```python
import subprocess
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from plugins.video.src.encode import (
    require_binary,
    run_ffmpeg,
    probe_duration,
    probe_image_size,
)


def test_require_binary_passes_when_present():
    with patch("plugins.video.src.encode.shutil.which", return_value="/usr/bin/ffmpeg"):
        require_binary("ffmpeg")  # must not raise


def test_require_binary_gives_actionable_message_for_ffmpeg():
    with patch("plugins.video.src.encode.shutil.which", return_value=None):
        with pytest.raises(RuntimeError) as exc:
            require_binary("ffmpeg")
    assert "brew install ffmpeg" in str(exc.value)


def test_run_ffmpeg_surfaces_full_stderr_on_failure():
    failure = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="Invalid argument xyz")
    with patch("plugins.video.src.encode.shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("plugins.video.src.encode.subprocess.run", return_value=failure):
        with pytest.raises(RuntimeError) as exc:
            run_ffmpeg(["-i", "missing.png", "out.mp4"])
    assert "Invalid argument xyz" in str(exc.value)


def test_run_ffmpeg_prepends_overwrite_and_quiet_flags():
    ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch("plugins.video.src.encode.shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("plugins.video.src.encode.subprocess.run", return_value=ok) as mock_run:
        run_ffmpeg(["-i", "a.png", "out.mp4"])
    called = mock_run.call_args[0][0]
    assert called[:4] == ["ffmpeg", "-y", "-loglevel", "error"]


def test_probe_duration_parses_seconds():
    ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="182.5\n", stderr="")
    with patch("plugins.video.src.encode.shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("plugins.video.src.encode.subprocess.run", return_value=ok):
        assert probe_duration(Path("episode.mp3")) == pytest.approx(182.5)


def test_probe_image_size_parses_dimensions():
    ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="1024,1536\n", stderr="")
    with patch("plugins.video.src.encode.shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("plugins.video.src.encode.subprocess.run", return_value=ok):
        assert probe_image_size(Path("a.png")) == (1024, 1536)


def test_probe_image_size_raises_on_unreadable_file():
    bad = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="Invalid data")
    with patch("plugins.video.src.encode.shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("plugins.video.src.encode.subprocess.run", return_value=bad):
        with pytest.raises(RuntimeError):
            probe_image_size(Path("broken.png"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_encode.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plugins.video.src.encode'`

- [ ] **Step 3: Write the implementation**

`plugins/video/src/encode.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_encode.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/video/src/encode.py tests/test_encode.py
git commit -m "feat(video): add ffmpeg/ffprobe helpers with actionable errors"
```

---

### Task 3: Storyboard model, parsing and validation

**Files:**
- Create: `plugins/video/src/storyboard.py`
- Test: `tests/test_storyboard.py`

**Interfaces:**
- Consumes: `resolve_preset`, `DEFAULT_PRESET` from `presets`; `probe_image_size` from `encode`.
- Produces: `Slide` (dataclass: `image: Path`, `caption: str | None`, `seconds: float | None`, `motion: str`, `transition: str`, `transition_seconds: float`), `Storyboard` (dataclass: `preset: Preset`, `slides: list[Slide]`, `audio: Path | None`, `output: Path`, `fit: str`, `backend: str | None`), `load_storyboard(path: Path) -> Storyboard`, `collect_images(spec: str) -> list[Path]`, `validate_images(slides: list[Slide]) -> None`, constants `DEFAULT_SECONDS = 4.0`, `DEFAULT_TRANSITION_SECONDS = 0.5`, `MOTIONS`, `TRANSITIONS`, `FITS`, `IMAGE_EXTENSIONS`.

Duration resolution is deliberately **not** in this task — it lands in Task 4.

- [ ] **Step 1: Write the failing test**

Create `tests/test_storyboard.py`:

```python
import json
import pytest
from pathlib import Path
from plugins.video.src.storyboard import (
    load_storyboard,
    collect_images,
    validate_images,
    Slide,
    DEFAULT_SECONDS,
    DEFAULT_TRANSITION_SECONDS,
    IMAGE_EXTENSIONS,
)


def write_sb(tmp_path, data):
    p = tmp_path / "sb.json"
    p.write_text(json.dumps(data))
    return p


def test_loads_minimal_storyboard_with_defaults(tmp_path):
    sb = load_storyboard(write_sb(tmp_path, {"slides": [{"image": "a.png"}]}))
    assert sb.preset.name == "landscape"
    assert sb.fit == "cover"
    assert sb.backend is None
    assert sb.output == Path("output/video.mp4")
    assert sb.audio is None
    slide = sb.slides[0]
    assert slide.caption is None
    assert slide.seconds is None
    assert slide.motion == "zoom-in"
    assert slide.transition == "fade"
    assert slide.transition_seconds == DEFAULT_TRANSITION_SECONDS


def test_explicit_fields_are_kept(tmp_path):
    sb = load_storyboard(write_sb(tmp_path, {
        "preset": "reel",
        "audio": "output/episode.mp3",
        "output": "out/x.mp4",
        "fit": "contain",
        "backend": "browser",
        "slides": [{"image": "a.png", "caption": "Hook", "seconds": 3.5,
                    "motion": "pan-left", "transition": "cut", "transition_seconds": 0.25}],
    }))
    assert sb.preset.name == "reel"
    assert sb.audio == Path("output/episode.mp3")
    assert sb.output == Path("out/x.mp4")
    assert sb.fit == "contain"
    assert sb.backend == "browser"
    assert sb.slides[0].caption == "Hook"
    assert sb.slides[0].seconds == 3.5
    assert sb.slides[0].motion == "pan-left"
    assert sb.slides[0].transition == "cut"


def test_fps_key_overrides_preset_fps(tmp_path):
    sb = load_storyboard(write_sb(tmp_path, {"fps": 60, "slides": [{"image": "a.png"}]}))
    assert sb.preset.fps == 60


def test_empty_slides_is_an_error(tmp_path):
    with pytest.raises(ValueError) as exc:
        load_storyboard(write_sb(tmp_path, {"slides": []}))
    assert "slides" in str(exc.value).lower()


def test_slide_without_image_is_an_error(tmp_path):
    with pytest.raises(ValueError) as exc:
        load_storyboard(write_sb(tmp_path, {"slides": [{"caption": "no image"}]}))
    assert "image" in str(exc.value).lower()


@pytest.mark.parametrize("field,value", [
    ("motion", "spin"),
    ("transition", "wipe"),
])
def test_unknown_slide_enum_names_the_value(tmp_path, field, value):
    with pytest.raises(ValueError) as exc:
        load_storyboard(write_sb(tmp_path, {"slides": [{"image": "a.png", field: value}]}))
    assert value in str(exc.value)


def test_unknown_fit_names_the_value(tmp_path):
    with pytest.raises(ValueError) as exc:
        load_storyboard(write_sb(tmp_path, {"fit": "stretch", "slides": [{"image": "a.png"}]}))
    assert "stretch" in str(exc.value)


def test_collect_images_from_glob_is_sorted(tmp_path):
    for name in ["c.png", "a.png", "b.png"]:
        (tmp_path / name).touch()
    found = collect_images(str(tmp_path / "*.png"))
    assert [p.name for p in found] == ["a.png", "b.png", "c.png"]


def test_collect_images_from_directory_filters_extensions(tmp_path):
    for name in ["a.png", "b.JPG", "c.webp", "notes.txt", "clip.mp4"]:
        (tmp_path / name).touch()
    found = collect_images(str(tmp_path))
    assert [p.name for p in found] == ["a.png", "b.JPG", "c.webp"]


def test_collect_images_empty_result_is_an_error(tmp_path):
    with pytest.raises(ValueError):
        collect_images(str(tmp_path / "*.png"))


def test_image_extensions_cover_expected_formats():
    assert IMAGE_EXTENSIONS == {".png", ".jpg", ".jpeg", ".webp"}


def test_validate_images_reports_every_missing_file_at_once(tmp_path):
    present = tmp_path / "here.png"
    present.touch()
    slides = [
        Slide(image=tmp_path / "gone1.png", caption=None, seconds=None,
              motion="zoom-in", transition="fade", transition_seconds=0.5),
        Slide(image=present, caption=None, seconds=None,
              motion="zoom-in", transition="fade", transition_seconds=0.5),
        Slide(image=tmp_path / "gone2.png", caption=None, seconds=None,
              motion="zoom-in", transition="fade", transition_seconds=0.5),
    ]
    with pytest.raises(ValueError) as exc:
        validate_images(slides)
    message = str(exc.value)
    assert "gone1.png" in message and "gone2.png" in message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storyboard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plugins.video.src.storyboard'`

- [ ] **Step 3: Write the implementation**

`plugins/video/src/storyboard.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storyboard.py -v`
Expected: PASS (14 tests, counting both parametrized cases)

- [ ] **Step 5: Commit**

```bash
git add plugins/video/src/storyboard.py tests/test_storyboard.py
git commit -m "feat(video): add storyboard model, parsing and validation"
```

---

### Task 4: Duration resolution and crop warnings

**Files:**
- Modify: `plugins/video/src/storyboard.py` (append functions)
- Test: `tests/test_storyboard.py` (append tests)

**Interfaces:**
- Consumes: `Slide`, `Storyboard` from Task 3; `probe_duration`, `probe_image_size` from `encode`.
- Produces: `resolve_durations(sb: Storyboard) -> Storyboard` (mutates and returns the same object, with every `slide.seconds` set to a float), `total_duration(sb: Storyboard) -> float`, `crop_warnings(sb: Storyboard) -> list[str]`, `overlap_total(sb: Storyboard) -> float`.

The three duration rules from the spec:
1. **No audio** — omitted `seconds` default to `4.0`; mixing explicit and omitted is permitted.
2. **Audio + all explicit** — honored; warn if `abs(total_duration - audio_duration) > 0.5`.
3. **Audio + all omitted** — distribute evenly: each slide gets `(audio_duration + overlap_total) / n`.

Mixing explicit and omitted `seconds` **with audio present** is an error naming the offending slide indices.

Total duration accounts for transition overlap: `sum(seconds) - overlap_total`, where `overlap_total` sums `transition_seconds` for slides `[1:]` whose transition is not `cut`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_storyboard.py`:

```python
from unittest.mock import patch
from plugins.video.src.storyboard import (
    build_storyboard, resolve_durations, total_duration, overlap_total, crop_warnings,
)


def sb_with(slides, **kw):
    return build_storyboard({"slides": slides, **kw})


def test_rule1_no_audio_defaults_missing_seconds():
    sb = resolve_durations(sb_with([{"image": "a.png"}, {"image": "b.png"}]))
    assert [s.seconds for s in sb.slides] == [DEFAULT_SECONDS, DEFAULT_SECONDS]


def test_rule1_no_audio_permits_mixing_explicit_and_omitted():
    sb = resolve_durations(sb_with([{"image": "a.png", "seconds": 2}, {"image": "b.png"}]))
    assert [s.seconds for s in sb.slides] == [2.0, DEFAULT_SECONDS]


def test_overlap_total_ignores_first_slide_and_cuts():
    sb = sb_with([
        {"image": "a.png", "transition": "fade", "transition_seconds": 0.5},
        {"image": "b.png", "transition": "fade", "transition_seconds": 0.5},
        {"image": "c.png", "transition": "cut", "transition_seconds": 0.5},
    ])
    # slide 0's transition is ignored; slide 2 is a cut; only slide 1 counts
    assert overlap_total(sb) == pytest.approx(0.5)


def test_total_duration_subtracts_overlap():
    sb = resolve_durations(sb_with([
        {"image": "a.png", "seconds": 4},
        {"image": "b.png", "seconds": 4, "transition_seconds": 1.0},
    ]))
    assert total_duration(sb) == pytest.approx(7.0)


def test_rule2_explicit_durations_are_honored_with_audio():
    sb = sb_with([{"image": "a.png", "seconds": 3}, {"image": "b.png", "seconds": 3}],
                 audio="e.mp3")
    with patch("plugins.video.src.storyboard.probe_duration", return_value=5.5):
        resolved = resolve_durations(sb)
    assert [s.seconds for s in resolved.slides] == [3.0, 3.0]


def test_rule2_warns_when_audio_and_video_differ_by_more_than_half_a_second(capsys):
    sb = sb_with([{"image": "a.png", "seconds": 3}], audio="e.mp3")
    with patch("plugins.video.src.storyboard.probe_duration", return_value=30.0):
        resolve_durations(sb)
    assert "Warning" in capsys.readouterr().out


def test_rule2_stays_quiet_within_half_a_second(capsys):
    sb = sb_with([{"image": "a.png", "seconds": 3}], audio="e.mp3")
    with patch("plugins.video.src.storyboard.probe_duration", return_value=3.2):
        resolve_durations(sb)
    assert "Warning" not in capsys.readouterr().out


def test_rule3_distributes_audio_evenly():
    sb = sb_with([{"image": "a.png"}, {"image": "b.png"}, {"image": "c.png"}],
                 audio="e.mp3")
    with patch("plugins.video.src.storyboard.probe_duration", return_value=30.0):
        resolved = resolve_durations(sb)
    # overlap: slides 1 and 2 fade at 0.5 each = 1.0; each slide = (30 + 1.0) / 3
    assert [s.seconds for s in resolved.slides] == pytest.approx([31.0 / 3] * 3)
    assert total_duration(resolved) == pytest.approx(30.0)


def test_rule3_result_plays_exactly_as_long_as_the_audio():
    sb = sb_with([{"image": "a.png"}, {"image": "b.png"}], audio="e.mp3")
    with patch("plugins.video.src.storyboard.probe_duration", return_value=182.5):
        resolved = resolve_durations(sb)
    assert total_duration(resolved) == pytest.approx(182.5)


def test_mixing_explicit_and_omitted_with_audio_raises_naming_indices():
    sb = sb_with([{"image": "a.png", "seconds": 2}, {"image": "b.png"}, {"image": "c.png"}],
                 audio="e.mp3")
    with patch("plugins.video.src.storyboard.probe_duration", return_value=10.0):
        with pytest.raises(ValueError) as exc:
            resolve_durations(sb)
    message = str(exc.value)
    assert "1" in message and "2" in message


def test_crop_warning_fires_for_a_codex_portrait_image_into_a_reel():
    """The motivating case: Codex emits 1024x1536 (2:3). Covering a 9:16 target
    scales to height 1920 -> width 1280, cropped to 1080: 200/1280 = 15.6% lost."""
    sb = sb_with([{"image": "a.png"}], preset="reel")  # target 1080x1920 (9:16)
    with patch("plugins.video.src.storyboard.probe_image_size", return_value=(1024, 1536)):
        warnings = crop_warnings(sb)
    assert len(warnings) == 1
    assert "a.png" in warnings[0]
    assert "16%" in warnings[0]


def test_crop_warning_fires_hard_for_a_square_image_into_a_reel():
    """1254x1254 (1:1) into 9:16 discards 43.75% — the loudest realistic case."""
    sb = sb_with([{"image": "a.png"}], preset="reel")
    with patch("plugins.video.src.storyboard.probe_image_size", return_value=(1254, 1254)):
        assert len(crop_warnings(sb)) == 1


def test_crop_warning_silent_just_below_the_threshold():
    """1080x1800 into 9:16: kept = 0.5625/0.6 = 93.75%, so 6.25% lost — quiet."""
    sb = sb_with([{"image": "a.png"}], preset="reel")
    with patch("plugins.video.src.storyboard.probe_image_size", return_value=(1080, 1800)):
        assert crop_warnings(sb) == []


def test_crop_warning_silent_when_aspect_already_matches():
    sb = sb_with([{"image": "a.png"}], preset="reel")
    with patch("plugins.video.src.storyboard.probe_image_size", return_value=(1080, 1920)):
        assert crop_warnings(sb) == []


def test_crop_warning_silent_under_contain_fit():
    sb = sb_with([{"image": "a.png"}], preset="reel", fit="contain")
    with patch("plugins.video.src.storyboard.probe_image_size", return_value=(1024, 1536)):
        assert crop_warnings(sb) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storyboard.py -v -k "rule or overlap or crop or total_duration"`
Expected: FAIL — `ImportError: cannot import name 'resolve_durations'`

- [ ] **Step 3: Write the implementation**

Add to the imports at the top of `plugins/video/src/storyboard.py`:

```python
from plugins.video.src.encode import probe_duration, probe_image_size
```

Append to `plugins/video/src/storyboard.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storyboard.py -v`
Expected: PASS (all tests from Tasks 3 and 4)

- [ ] **Step 5: Commit**

```bash
git add plugins/video/src/storyboard.py tests/test_storyboard.py
git commit -m "feat(video): resolve slide durations against audio, warn on heavy crops"
```

---

### Task 5: Frames to video and audio muxing

**Files:**
- Modify: `plugins/video/src/encode.py` (append functions)
- Test: `tests/test_encode.py` (append tests)

**Interfaces:**
- Consumes: `run_ffmpeg` from Task 2.
- Produces: `frames_to_video(frames_dir: Path, fps: int, output: Path) -> Path`, `mux_audio(video: Path, audio: Path | None, output: Path) -> Path`.

`mux_audio` with `audio=None` copies the video stream through to `output` rather than re-encoding. Frame files are named `f%05d.png`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_encode.py`:

```python
from plugins.video.src.encode import frames_to_video, mux_audio


def test_frames_to_video_uses_framerate_and_yuv420p(tmp_path):
    with patch("plugins.video.src.encode.run_ffmpeg") as mock:
        frames_to_video(tmp_path / "frames", 30, tmp_path / "silent.mp4")
    args = mock.call_args[0][0]
    assert "-framerate" in args
    assert args[args.index("-framerate") + 1] == "30"
    assert "yuv420p" in args
    assert "f%05d.png" in " ".join(args)


def test_mux_audio_maps_both_streams_and_uses_shortest(tmp_path):
    with patch("plugins.video.src.encode.run_ffmpeg") as mock:
        mux_audio(tmp_path / "silent.mp4", tmp_path / "e.mp3", tmp_path / "out.mp4")
    args = mock.call_args[0][0]
    assert "-shortest" in args
    assert "aac" in args
    assert args.count("-i") == 2


def test_mux_audio_without_audio_copies_stream(tmp_path):
    with patch("plugins.video.src.encode.run_ffmpeg") as mock:
        mux_audio(tmp_path / "silent.mp4", None, tmp_path / "out.mp4")
    args = mock.call_args[0][0]
    assert args.count("-i") == 1
    assert "copy" in args


def test_mux_audio_returns_the_output_path(tmp_path):
    out = tmp_path / "out.mp4"
    with patch("plugins.video.src.encode.run_ffmpeg"):
        assert mux_audio(tmp_path / "silent.mp4", None, out) == out


def test_frames_to_video_creates_parent_directory(tmp_path):
    out = tmp_path / "nested" / "dir" / "silent.mp4"
    with patch("plugins.video.src.encode.run_ffmpeg"):
        frames_to_video(tmp_path / "frames", 30, out)
    assert out.parent.is_dir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_encode.py -v -k "frames_to_video or mux_audio"`
Expected: FAIL — `ImportError: cannot import name 'frames_to_video'`

- [ ] **Step 3: Write the implementation**

Append to `plugins/video/src/encode.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_encode.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/video/src/encode.py tests/test_encode.py
git commit -m "feat(video): add frame encoding and audio muxing"
```

---

### Task 6: ffmpeg backend

**Files:**
- Create: `plugins/video/src/backends/ffmpeg_backend.py`
- Test: `tests/test_ffmpeg_backend.py`

**Interfaces:**
- Consumes: `Storyboard`, `Slide` from `storyboard`; `run_ffmpeg` from `encode`.
- Produces: `build_filtergraph(sb: Storyboard) -> tuple[str, str]` returning `(filter_complex, final_label)`, `build_args(sb: Storyboard, output: Path) -> list[str]`, `render(sb: Storyboard, workdir: Path) -> Path`.

`render` returns the path to a **silent** MP4 in `workdir`. Audio is never touched here.

**Critical:** every per-slide chain must place `scale=8000:-1` immediately before `zoompan`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ffmpeg_backend.py`:

```python
import pytest
from pathlib import Path
from unittest.mock import patch
from plugins.video.src.storyboard import build_storyboard, resolve_durations
from plugins.video.src.backends.ffmpeg_backend import build_filtergraph, build_args, render


def sb(slides, **kw):
    return resolve_durations(build_storyboard({"slides": slides, **kw}))


def test_upscales_before_zoompan_to_avoid_jitter():
    graph, _ = build_filtergraph(sb([{"image": "a.png"}]))
    assert "scale=8000:-1,zoompan=" in graph


def test_one_labelled_chain_per_slide():
    graph, _ = build_filtergraph(sb([{"image": "a.png"}, {"image": "b.png"}]))
    assert "[v0]" in graph and "[v1]" in graph


def test_single_slide_final_label_is_v0():
    _, final = build_filtergraph(sb([{"image": "a.png"}]))
    assert final == "v0"


def test_fade_transition_uses_xfade_with_offset():
    graph, final = build_filtergraph(sb([
        {"image": "a.png", "seconds": 4},
        {"image": "b.png", "seconds": 4, "transition": "fade", "transition_seconds": 1.0},
    ]))
    assert "xfade=transition=fade:duration=1.0" in graph
    assert "offset=3.000" in graph  # 4.0 - 1.0
    assert final == "x1"


def test_cut_transition_uses_concat_not_xfade():
    graph, _ = build_filtergraph(sb([
        {"image": "a.png", "seconds": 4},
        {"image": "b.png", "seconds": 4, "transition": "cut"},
    ]))
    assert "concat=n=2:v=1:a=0" in graph
    assert "xfade" not in graph


def test_cover_fit_crops_to_preset():
    graph, _ = build_filtergraph(sb([{"image": "a.png"}], preset="reel"))
    assert "force_original_aspect_ratio=increase" in graph
    assert "crop=1080:1920" in graph


def test_contain_fit_pads_to_preset():
    graph, _ = build_filtergraph(sb([{"image": "a.png"}], preset="reel", fit="contain"))
    assert "force_original_aspect_ratio=decrease" in graph
    assert "pad=1080:1920" in graph


def test_zoom_out_starts_zoomed_in():
    graph, _ = build_filtergraph(sb([{"image": "a.png", "motion": "zoom-out"}]))
    assert "1.18" in graph


def test_motion_none_holds_a_constant_zoom():
    graph, _ = build_filtergraph(sb([{"image": "a.png", "motion": "none"}]))
    assert "zoompan=z='1'" in graph


def test_build_args_supplies_one_loop_input_per_slide():
    args = build_args(sb([{"image": "a.png"}, {"image": "b.png"}]), Path("out.mp4"))
    assert args.count("-loop") == 2
    assert "a.png" in args and "b.png" in args


def test_build_args_maps_the_final_label():
    args = build_args(sb([{"image": "a.png"}]), Path("out.mp4"))
    assert "-map" in args
    assert "[v0]" in args


def test_render_writes_silent_mp4_into_workdir(tmp_path):
    with patch("plugins.video.src.backends.ffmpeg_backend.run_ffmpeg") as mock:
        out = render(sb([{"image": "a.png"}]), tmp_path)
    assert out.parent == tmp_path
    assert out.suffix == ".mp4"
    # audio must never be referenced by this backend
    assert "-c:a" not in mock.call_args[0][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ffmpeg_backend.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plugins.video.src.backends.ffmpeg_backend'`

- [ ] **Step 3: Write the implementation**

`plugins/video/src/backends/ffmpeg_backend.py`:

```python
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
        args += ["-loop", "1", "-t", f"{slide.seconds:.3f}", "-i", str(slide.image)]
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ffmpeg_backend.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/video/src/backends/ffmpeg_backend.py tests/test_ffmpeg_backend.py
git commit -m "feat(video): add ffmpeg zoompan backend"
```

---

### Task 7: Browser backend

**Files:**
- Create: `plugins/video/src/backends/browser_backend.py`
- Test: `tests/test_browser_backend.py`

**Interfaces:**
- Consumes: `Storyboard` from `storyboard`; `total_duration` from `storyboard`; `frames_to_video`, `require_binary`, `CHROMIUM_MISSING_HINT` from `encode`.
- Produces: `build_scene_html(sb: Storyboard) -> str`, `capture_frames(sb: Storyboard, workdir: Path) -> Path` (returns the frames directory), `render(sb: Storyboard, workdir: Path) -> Path`.

**Critical:** `page.screenshot()` must be called with **only** a `path` argument. Passing `animations="disabled"` fast-forwards every finite animation to completion, producing a full sequence of identical end-state frames — a valid MP4 with correct metadata and no motion.

- [ ] **Step 1: Write the failing test**

Create `tests/test_browser_backend.py`:

```python
import re
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from plugins.video.src.storyboard import build_storyboard, resolve_durations
from plugins.video.src.backends.browser_backend import build_scene_html, capture_frames, render


def sb(slides, **kw):
    return resolve_durations(build_storyboard({"slides": slides, **kw}))


def test_scene_html_embeds_every_slide_image():
    html = build_scene_html(sb([{"image": "a.png"}, {"image": "b.png"}]))
    assert "a.png" in html and "b.png" in html


def test_scene_html_embeds_captions():
    html = build_scene_html(sb([{"image": "a.png", "caption": "The hook"}]))
    assert "The hook" in html


def test_scene_html_escapes_caption_markup():
    html = build_scene_html(sb([{"image": "a.png", "caption": "<script>bad()</script>"}]))
    assert "<script>bad()</script>" not in html


def test_scene_html_pauses_all_animations():
    html = build_scene_html(sb([{"image": "a.png"}]))
    assert "pause()" in html


def test_scene_html_exposes_a_seek_hook():
    html = build_scene_html(sb([{"image": "a.png"}]))
    assert "__seek" in html
    assert "currentTime" in html


def test_scene_html_sizes_the_stage_to_the_preset():
    html = build_scene_html(sb([{"image": "a.png"}], preset="reel"))
    assert "1080px" in html and "1920px" in html


def test_scene_html_uses_contain_for_contain_fit():
    html = build_scene_html(sb([{"image": "a.png"}], fit="contain"))
    assert "contain" in html


def _mock_playwright(page):
    browser = MagicMock()
    browser.new_page.return_value = page
    chromium = MagicMock()
    chromium.launch.return_value = browser
    ctx = MagicMock()
    ctx.__enter__.return_value = MagicMock(chromium=chromium)
    return ctx, browser


def test_capture_frames_never_disables_animations(tmp_path):
    """Regression guard. animations='disabled' fast-forwards finite animations to
    completion, yielding identical end-state frames: a valid MP4 with zero motion."""
    page = MagicMock()
    ctx, _ = _mock_playwright(page)
    with patch("plugins.video.src.backends.browser_backend.sync_playwright", return_value=ctx):
        capture_frames(sb([{"image": "a.png", "seconds": 0.1}]), tmp_path)
    for call in page.screenshot.call_args_list:
        assert "animations" not in call.kwargs


def test_capture_frames_seeks_a_distinct_time_per_frame(tmp_path):
    page = MagicMock()
    ctx, _ = _mock_playwright(page)
    board = sb([{"image": "a.png", "seconds": 1.0}], fps=10)
    with patch("plugins.video.src.backends.browser_backend.sync_playwright", return_value=ctx):
        capture_frames(board, tmp_path)
    seeks = [c[0][1] for c in page.evaluate.call_args_list]
    assert seeks == sorted(seeks)
    assert len(set(seeks)) == len(seeks) == 10


def test_capture_frames_closes_browser_on_error(tmp_path):
    page = MagicMock()
    page.screenshot.side_effect = RuntimeError("boom")
    ctx, browser = _mock_playwright(page)
    with patch("plugins.video.src.backends.browser_backend.sync_playwright", return_value=ctx):
        with pytest.raises(RuntimeError):
            capture_frames(sb([{"image": "a.png", "seconds": 0.1}]), tmp_path)
    browser.close.assert_called_once()


def test_capture_frames_names_files_for_the_encoder(tmp_path):
    page = MagicMock()
    ctx, _ = _mock_playwright(page)
    with patch("plugins.video.src.backends.browser_backend.sync_playwright", return_value=ctx):
        frames_dir = capture_frames(sb([{"image": "a.png", "seconds": 0.2}], fps=10), tmp_path)
    names = [Path(c.kwargs["path"]).name for c in page.screenshot.call_args_list]
    assert names[0] == "f00000.png"
    assert all(re.fullmatch(r"f\d{5}\.png", n) for n in names)
    assert frames_dir.is_dir()


@pytest.mark.integration
def test_real_capture_produces_frames_that_actually_differ(tmp_path):
    """The only test that catches animations='disabled'. Metadata-based checks
    all pass on a motionless video; comparing frame bytes does not."""
    from plugins.video.src.encode import run_ffmpeg
    image = tmp_path / "src.png"
    run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=640x480:duration=1", "-frames:v", "1", str(image)])

    board = sb([{"image": str(image), "seconds": 1.0, "motion": "zoom-in"}],
               preset="square", fps=4)
    frames_dir = capture_frames(board, tmp_path)
    frames = sorted(frames_dir.glob("*.png"))
    assert len(frames) == 4
    assert frames[0].read_bytes() != frames[-1].read_bytes(), \
        "All frames identical — animations are not being seeked"


def test_render_encodes_captured_frames(tmp_path):
    with patch("plugins.video.src.backends.browser_backend.capture_frames",
               return_value=tmp_path / "frames") as cap, \
         patch("plugins.video.src.backends.browser_backend.frames_to_video") as enc:
        enc.return_value = tmp_path / "silent.mp4"
        out = render(sb([{"image": "a.png"}]), tmp_path)
    cap.assert_called_once()
    enc.assert_called_once()
    assert out == tmp_path / "silent.mp4"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_browser_backend.py -v -m "not integration"`
Expected: FAIL — `ModuleNotFoundError: No module named 'plugins.video.src.backends.browser_backend'`

- [ ] **Step 3: Write the implementation**

`plugins/video/src/backends/browser_backend.py`:

```python
import html as html_lib
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from plugins.video.src.encode import frames_to_video
from plugins.video.src.storyboard import Storyboard, total_duration

_TEMPLATE = """<!doctype html><meta charset="utf-8"><style>
html,body{{margin:0;background:#000;overflow:hidden}}
.stage{{position:relative;width:{width}px;height:{height}px;overflow:hidden}}
.layer{{position:absolute;inset:0;background-repeat:no-repeat;background-position:center;
        background-size:{fit};opacity:0}}
.cap{{position:absolute;left:6%;right:6%;bottom:9%;
      font:700 {caption_px}px/1.15 -apple-system,system-ui,Segoe UI,sans-serif;
      color:#fff;text-shadow:0 4px 40px rgba(0,0,0,.85);opacity:0}}
</style>
<div class="stage" id="stage"></div>
<script>
const SLIDES = {slides_json};
const MOTION = {{
  'zoom-in':  ['scale(1)',            'scale(1.18)'],
  'zoom-out': ['scale(1.18)',         'scale(1)'],
  'pan-left': ['scale(1.15) translateX(3%)',  'scale(1.15) translateX(-3%)'],
  'pan-right':['scale(1.15) translateX(-3%)', 'scale(1.15) translateX(3%)'],
  'none':     ['scale(1)',            'scale(1)'],
}};
const stage = document.getElementById('stage');
const anims = [];
let start = 0;
SLIDES.forEach((s, i) => {{
  const layer = document.createElement('div');
  layer.className = 'layer';
  layer.style.backgroundImage = 'url("' + s.src + '")';
  stage.appendChild(layer);

  const dur = s.seconds * 1000;
  const tr  = s.transition_seconds * 1000;
  if (i > 0) start = start + SLIDES[i - 1].seconds * 1000 - tr;

  const [from, to] = MOTION[s.motion];
  anims.push(layer.animate([{{transform: from}}, {{transform: to}}],
    {{duration: dur, delay: start, fill: 'both'}}));

  if (i === 0) {{
    layer.style.opacity = 1;
  }} else {{
    anims.push(layer.animate([{{opacity: 0}}, {{opacity: 1}}],
      {{duration: Math.max(tr, 1), delay: start, fill: 'both'}}));
  }}

  if (s.caption) {{
    const cap = document.createElement('div');
    cap.className = 'cap';
    cap.textContent = s.caption;
    stage.appendChild(cap);
    anims.push(cap.animate(
      [{{opacity: 0, transform: 'translateY(40px)'}}, {{opacity: 1, transform: 'translateY(0)'}}],
      {{duration: 700, delay: start + 300, easing: 'cubic-bezier(.2,.8,.2,1)', fill: 'both'}}));
    anims.push(cap.animate([{{opacity: 1}}, {{opacity: 0}}],
      {{duration: 500, delay: start + dur - 500, fill: 'both'}}));
  }}
}});
anims.forEach(a => a.pause());
window.__seek = t => {{ anims.forEach(a => {{ a.currentTime = t; }}); }};
window.__seek(0);
</script>
"""


def build_scene_html(sb: Storyboard) -> str:
    slides = [
        {
            "src": slide.image.resolve().as_uri(),
            "caption": html_lib.escape(slide.caption) if slide.caption else "",
            "seconds": slide.seconds,
            "motion": slide.motion,
            "transition_seconds": 0.0 if slide.transition == "cut" else slide.transition_seconds,
        }
        for slide in sb.slides
    ]
    return _TEMPLATE.format(
        width=sb.preset.width,
        height=sb.preset.height,
        fit="contain" if sb.fit == "contain" else "cover",
        caption_px=max(int(sb.preset.width * 0.045), 24),
        slides_json=json.dumps(slides),
    )


def capture_frames(sb: Storyboard, workdir: Path) -> Path:
    frames_dir = workdir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    scene = workdir / "scene.html"
    scene.write_text(build_scene_html(sb))

    fps = sb.preset.fps
    frame_count = max(int(round(total_duration(sb) * fps)), 1)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            args=["--force-device-scale-factor=1", "--hide-scrollbars"]
        )
        try:
            page = browser.new_page(
                viewport={"width": sb.preset.width, "height": sb.preset.height}
            )
            page.goto(scene.resolve().as_uri())
            page.wait_for_timeout(400)  # let images decode before the first capture
            for i in range(frame_count):
                page.evaluate("t => window.__seek(t)", i * 1000.0 / fps)
                # NEVER pass animations="disabled" here — it fast-forwards every
                # finite animation to completion and yields identical frames.
                page.screenshot(path=str(frames_dir / f"f{i:05d}.png"))
        finally:
            browser.close()

    return frames_dir


def render(sb: Storyboard, workdir: Path) -> Path:
    frames_dir = capture_frames(sb, workdir)
    return frames_to_video(frames_dir, sb.preset.fps, workdir / "silent.mp4")
```

- [ ] **Step 4: Run the unit tests**

Run: `pytest tests/test_browser_backend.py -v -m "not integration"`
Expected: PASS (13 tests)

- [ ] **Step 5: Run the integration guard against a real browser**

Run: `pytest tests/test_browser_backend.py -v -m integration`
Expected: PASS. If it fails with "All frames identical", `animations="disabled"` has crept back into the `page.screenshot()` call.

- [ ] **Step 6: Commit**

```bash
git add plugins/video/src/backends/browser_backend.py tests/test_browser_backend.py
git commit -m "feat(video): add browser backend with seeked frame capture"
```

---

### Task 8: CLI, backend selection and orchestration

**Files:**
- Create: `plugins/video/src/video_render.py`
- Test: `tests/test_video_render.py`

**Interfaces:**
- Consumes: everything from Tasks 1–7.
- Produces: `select_backend(sb: Storyboard) -> tuple[str, str]` returning `(name, reason)`, `parse_args(argv: list[str]) -> argparse.Namespace`, `storyboard_from_args(args) -> Storyboard`, `run(argv: list[str]) -> Path`.

Auto-selection: any slide with a non-empty caption → `browser`; otherwise → `ffmpeg`. An explicit `sb.backend` always wins.

- [ ] **Step 1: Write the failing test**

Create `tests/test_video_render.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import patch
from plugins.video.src.storyboard import build_storyboard, resolve_durations
from plugins.video.src.video_render import select_backend, parse_args, storyboard_from_args, run


def sb(slides, **kw):
    return resolve_durations(build_storyboard({"slides": slides, **kw}))


def test_captions_select_the_browser_backend():
    name, reason = select_backend(sb([{"image": "a.png", "caption": "Hook"}]))
    assert name == "browser"
    assert "caption" in reason.lower()


def test_no_captions_select_the_ffmpeg_backend():
    name, reason = select_backend(sb([{"image": "a.png"}, {"image": "b.png"}]))
    assert name == "ffmpeg"
    assert "caption" in reason.lower()


def test_one_caption_among_many_still_selects_browser():
    name, _ = select_backend(sb([{"image": "a.png"}, {"image": "b.png", "caption": "Hi"}]))
    assert name == "browser"


def test_empty_caption_does_not_select_browser():
    name, _ = select_backend(sb([{"image": "a.png", "caption": ""}]))
    assert name == "ffmpeg"


def test_explicit_backend_overrides_auto_selection():
    name, reason = select_backend(sb([{"image": "a.png", "caption": "Hook"}], backend="ffmpeg"))
    assert name == "ffmpeg"
    assert "explicit" in reason.lower()


def test_unknown_explicit_backend_is_an_error():
    with pytest.raises(ValueError) as exc:
        select_backend(sb([{"image": "a.png"}], backend="premiere"))
    assert "premiere" in str(exc.value)


def test_flags_and_storyboard_together_are_an_error(tmp_path):
    board = tmp_path / "sb.json"
    board.write_text(json.dumps({"slides": [{"image": "a.png"}]}))
    args = parse_args([str(board), "--images", "x/*.png"])
    with pytest.raises(ValueError) as exc:
        storyboard_from_args(args)
    assert "mutually exclusive" in str(exc.value).lower()


def test_neither_storyboard_nor_images_is_an_error():
    args = parse_args([])
    with pytest.raises(ValueError):
        storyboard_from_args(args)


def test_flags_build_an_equivalent_storyboard(tmp_path):
    for name in ["a.png", "b.png"]:
        (tmp_path / name).touch()
    args = parse_args(["--images", str(tmp_path / "*.png"), "--preset", "reel",
                       "--seconds", "2.5", "--fit", "contain", "--output", "o/v.mp4"])
    board = storyboard_from_args(args)
    assert board.preset.name == "reel"
    assert board.fit == "contain"
    assert board.output == Path("o/v.mp4")
    assert [s.seconds for s in board.slides] == [2.5, 2.5]
    assert [s.image.name for s in board.slides] == ["a.png", "b.png"]


def test_run_reports_the_chosen_backend_and_reason(tmp_path, capsys):
    image = tmp_path / "a.png"
    image.touch()
    out = tmp_path / "v.mp4"
    with patch("plugins.video.src.video_render.ffmpeg_backend.render",
               return_value=tmp_path / "silent.mp4"), \
         patch("plugins.video.src.video_render.mux_audio", return_value=out), \
         patch("plugins.video.src.video_render.crop_warnings", return_value=[]):
        run(["--images", str(image), "--output", str(out)])
    printed = capsys.readouterr().out
    assert "Backend: ffmpeg" in printed


def test_run_prints_crop_warnings(tmp_path, capsys):
    image = tmp_path / "a.png"
    image.touch()
    with patch("plugins.video.src.video_render.ffmpeg_backend.render",
               return_value=tmp_path / "silent.mp4"), \
         patch("plugins.video.src.video_render.mux_audio", return_value=tmp_path / "v.mp4"), \
         patch("plugins.video.src.video_render.crop_warnings",
               return_value=["a.png: 1024x1536 cropped to 1080x1920 discards 33% of the image"]):
        run(["--images", str(image), "--preset", "reel"])
    assert "discards 33%" in capsys.readouterr().out


def test_run_fails_before_rendering_when_an_image_is_missing(tmp_path):
    with patch("plugins.video.src.video_render.ffmpeg_backend.render") as render_mock:
        with pytest.raises(ValueError):
            run(["--images", str(tmp_path / "nope.png")])
    render_mock.assert_not_called()


def test_run_dispatches_to_the_browser_backend_when_captioned(tmp_path):
    board = tmp_path / "sb.json"
    image = tmp_path / "a.png"
    image.touch()
    board.write_text(json.dumps({
        "slides": [{"image": str(image), "caption": "Hook"}],
        "output": str(tmp_path / "v.mp4"),
    }))
    with patch("plugins.video.src.video_render.browser_backend.render",
               return_value=tmp_path / "silent.mp4") as browser, \
         patch("plugins.video.src.video_render.mux_audio", return_value=tmp_path / "v.mp4"), \
         patch("plugins.video.src.video_render.crop_warnings", return_value=[]):
        run([str(board)])
    browser.assert_called_once()


@pytest.mark.integration
def test_end_to_end_render_produces_a_correct_mp4(tmp_path):
    """Real ffmpeg. The only test proving the whole pipeline works."""
    import subprocess
    from plugins.video.src.encode import run_ffmpeg

    images = []
    for i, colour in enumerate(["red", "blue"]):
        path = tmp_path / f"{i}.png"
        run_ffmpeg(["-f", "lavfi", "-i", f"color=c={colour}:size=320x240",
                    "-frames:v", "1", str(path)])
        images.append(path)

    out = tmp_path / "video.mp4"
    board = tmp_path / "sb.json"
    board.write_text(json.dumps({
        "preset": "square",
        "fps": 10,
        "output": str(out),
        "slides": [{"image": str(p), "seconds": 1.0, "transition": "cut"} for p in images],
    }))

    run([str(board)])

    assert out.exists()
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,nb_frames,r_frame_rate",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    width, height, frame_rate, frames, duration = (
        probe[0], probe[1], probe[2], probe[3], probe[4],
    )
    assert (int(width), int(height)) == (1080, 1080)
    assert frame_rate == "10/1"
    assert int(frames) == 20          # 2 slides x 1.0s x 10fps, cut transition
    assert float(duration) == pytest.approx(2.0, abs=0.15)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_video_render.py -v -m "not integration"`
Expected: FAIL — `ModuleNotFoundError: No module named 'plugins.video.src.video_render'`

- [ ] **Step 3: Write the implementation**

`plugins/video/src/video_render.py`:

```python
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
    validate_images,
)

BACKENDS = {"ffmpeg": ffmpeg_backend, "browser": browser_backend}


def select_backend(sb: Storyboard) -> tuple[str, str]:
    if sb.backend is not None:
        if sb.backend not in BACKENDS:
            raise ValueError(
                f"Unknown backend {sb.backend!r}. Allowed: {', '.join(sorted(BACKENDS))}"
            )
        return sb.backend, f"explicit --backend {sb.backend}"
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
    parser.add_argument("--audio", help="Audio track to mux")
    parser.add_argument("--output", help="Output path (default output/video.mp4)")
    parser.add_argument("--preset", default=None,
                        help="reel | story | square | landscape")
    parser.add_argument("--fit", default=None, help="cover | contain")
    parser.add_argument("--backend", default=None, help="ffmpeg | browser")
    parser.add_argument("--seconds", type=float, default=None,
                        help="Uniform per-slide duration")
    parser.add_argument("--fps", type=int, default=None)
    return parser.parse_args(argv)


def storyboard_from_args(args: argparse.Namespace) -> Storyboard:
    if args.storyboard and args.images:
        raise ValueError(
            "A storyboard path and --images are mutually exclusive. Pass one or the other."
        )
    if args.storyboard:
        return load_storyboard(Path(args.storyboard))
    if not args.images:
        raise ValueError("Pass a storyboard path or --images.")

    slides = [{"image": str(p)} for p in collect_images(args.images)]
    if args.seconds is not None:
        for slide in slides:
            slide["seconds"] = args.seconds

    data: dict = {"slides": slides, "preset": args.preset or DEFAULT_PRESET}
    if args.audio:
        data["audio"] = args.audio
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
    resolve_durations(sb)

    for warning in crop_warnings(sb):
        print(f"Warning: {warning}")

    name, reason = select_backend(sb)
    print(f"Backend: {name} ({reason})")

    with tempfile.TemporaryDirectory() as tmp:
        silent = BACKENDS[name].render(sb, Path(tmp))
        sb.output.parent.mkdir(parents=True, exist_ok=True)
        output = mux_audio(silent, sb.audio, sb.output)

    print(f"Rendered → {output}")
    return output


if __name__ == "__main__":
    try:
        run(sys.argv[1:])
    except (ValueError, RuntimeError) as exc:
        sys.exit(f"Error: {exc}")
```

- [ ] **Step 4: Run the unit tests**

Run: `pytest tests/test_video_render.py -v -m "not integration"`
Expected: PASS (13 tests)

- [ ] **Step 5: Run the end-to-end smoke test**

Run: `pytest tests/test_video_render.py -v -m integration`
Expected: PASS — a real 1080x1080 / 10fps / 20-frame / 2.0s MP4 is produced and probed.

- [ ] **Step 6: Run the whole suite to confirm nothing regressed**

Run: `pytest tests/ -v`
Expected: PASS — all new tests plus the four existing media test files.

- [ ] **Step 7: Commit**

```bash
git add plugins/video/src/video_render.py tests/test_video_render.py
git commit -m "feat(video): add CLI, backend selection and orchestration"
```

---

### Task 9: Skill definition and marketplace registration

**Files:**
- Create: `plugins/video/skills/video-render/SKILL.md`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `README.md`

**Interfaces:**
- Consumes: the `run()` CLI from Task 8.
- Produces: the `/video:video-render` skill.

- [ ] **Step 1: Write the skill definition**

`plugins/video/skills/video-render/SKILL.md`:

````markdown
---
name: video-render
description: Render images plus optional audio into an MP4 using local ffmpeg and Playwright. Writes output/video.mp4. Feeds instagram:reel and instagram:story-video.
argument-hint: <path-to-storyboard.json | --images GLOB>
allowed-tools: Bash(python3 *)
---

# video-render

Render a set of images, with optional captions and an audio track, into a finished MP4.
Uses only local tooling — ffmpeg and Playwright. No external AI service.

## Steps

1. Determine the inputs. If the user supplied a storyboard JSON path, use it directly.
   Otherwise collect: image glob or directory, optional audio file, and target preset
   (`reel`/`story` = 1080x1920, `square` = 1080x1080, `landscape` = 1920x1080).

2. Run the renderer:

   ```bash
   python3 plugins/video/src/video_render.py <argument>
   ```

   Quick form:

   ```bash
   python3 plugins/video/src/video_render.py \
     --images "assets/*.png" --audio output/episode.mp3 --preset reel
   ```

3. Report the backend line the script prints (`Backend: ffmpeg (...)` or
   `Backend: browser (...)`) and any `Warning:` lines — crop warnings mean part of an
   image is being cut off and the user may want `--fit contain`.

4. Confirm `output/video.mp4` was written. If the script errors, report the full error message.

## Storyboard format

```json
{
  "preset": "reel",
  "audio": "output/episode.mp3",
  "output": "output/video.mp4",
  "fit": "cover",
  "slides": [
    { "image": "assets/1.png", "caption": "The hook", "seconds": 4,
      "motion": "zoom-in", "transition": "fade", "transition_seconds": 0.5 }
  ]
}
```

`motion`: `zoom-in`, `zoom-out`, `pan-left`, `pan-right`, `none`.
`transition`: `fade` or `cut` — applies *into* the slide it is declared on, ignored on the first slide.

Omit `seconds` on every slide with `audio` set and the audio duration is distributed
evenly across the slides. Mixing explicit and omitted `seconds` with audio is an error.

## Backends

Chosen automatically unless `--backend` is passed: any slide with a caption uses the
browser backend (HTML/CSS, full typography); otherwise ffmpeg (faster, pan/zoom only).

## Feeding the publish skills

`output/video.mp4` is directly consumable:

```bash
python3 ~/InstagramAI/scripts/publish_reel.py --video output/video.mp4 --caption "..."
```
````

- [ ] **Step 2: Register the plugin in the marketplace**

In `.claude-plugin/marketplace.json`, add a third entry to the `plugins` array, after the `instagram` entry:

```json
    {
      "name": "video",
      "description": "Skills for rendering images and audio into finished MP4 videos with local ffmpeg and Playwright.",
      "source": "./plugins/video"
    }
```

- [ ] **Step 3: Document the plugin in the README**

Add a section to `README.md` describing the `video` plugin: what it does, the two backends and how they are selected, the storyboard format, and the `output/video.mp4` handoff to `instagram:reel` / `instagram:story-video`. Match the depth and heading style already used for the `media` and `instagram` plugins.

- [ ] **Step 4: Validate the manifests**

Run: `bash scripts/validate-plugins.sh`
Expected: `✔ Validation passed` for `instagram`, `media`, and `video`.

- [ ] **Step 5: Verify the marketplace JSON parses**

Run: `python3 -c "import json; d=json.load(open('.claude-plugin/marketplace.json')); print([p['name'] for p in d['plugins']])"`
Expected: `['media', 'instagram', 'video']`

- [ ] **Step 6: Run the full suite one final time**

Run: `pytest tests/ -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add plugins/video/skills .claude-plugin/marketplace.json README.md
git commit -m "feat(video): add video-render skill and register the plugin"
```

---

## Self-Review Notes

Checked against `docs/superpowers/specs/2026-08-29-video-render-design.md`:

| Spec section | Covered by |
|---|---|
| Plugin structure, manifest, no new deps | Task 1 |
| Presets table | Task 1 |
| Input contract, storyboard schema, field rules | Task 3 |
| Flag shorthand, `--images` directory extensions | Tasks 3, 8 |
| Transition direction (into slide N) | Tasks 3, 6, 7 |
| Duration rules 1–3, mixing error, overlap maths | Task 4 |
| Aspect handling, 15% crop warning | Task 4 |
| Backend contract, silent CFR MP4 | Tasks 6, 7 |
| Auto-selection + logging | Task 8 |
| ffmpeg backend, upscale-before-zoompan | Task 6 |
| browser backend, WAAPI seek, no `animations="disabled"` | Task 7 |
| Error handling: missing images, binaries, ffmpeg stderr, try/finally | Tasks 2, 3, 7, 8 |
| Testing: all named tests | Tasks 1–8 |
| Skill definition | Task 9 |
| Files Changed table | Tasks 1–9 |

Two deviations from the spec's Files Changed table, both additive:

- **`pytest.ini`** is added in Task 1 to register the `integration` marker. The repo has no pytest config today, and using an unregistered marker emits a warning on every run.
- **`plugins/video/__init__.py`** is added in Task 1. The spec listed `src/__init__.py` and `src/backends/__init__.py` but not the plugin-level marker, which is required for `plugins.video.src.*` imports to resolve — `plugins/media/__init__.py` exists for the same reason.

Task 6 splits `tests/test_ffmpeg_backend.py` and Task 7 splits `tests/test_browser_backend.py` out of the spec's single `tests/test_video_render.py`, keeping each test file focused on one module. `tests/test_video_render.py` retains backend selection, CLI, and the end-to-end smoke test.
