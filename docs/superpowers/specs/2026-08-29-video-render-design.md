# Video Render Design

**Date:** 2026-08-29

## Overview

A new `video` plugin that turns a set of images plus an optional audio track into a finished MP4, using only tooling already installed on this machine (ffmpeg, Playwright/Chromium). No new AI service and no new Python dependency.

This closes a gap in the existing plugins: `instagram/reel` and `instagram/story-video` both *publish* a video, and both begin by asking the user for a video file path. Nothing in the repo *creates* that file. `video-render` produces it, writing to `output/video.mp4` so the publish skills consume it through the same `output/` file-handoff pattern the media pipeline already uses.

Two render backends are supported because they have genuinely different strengths:

- **ffmpeg** — `zoompan` Ken Burns plus `xfade` transitions. Fast, no browser. Cannot draw text or composite layers.
- **browser** — HTML/CSS animated via the Web Animations API, seeked frame-by-frame and captured with Playwright, then encoded by ffmpeg. Full typography, layout, and layered compositing. Roughly 2x the render time.

Both were validated by probe before this design: each produced a 1920x1080 / 30fps / 270-frame / 9.00s constant-frame-rate H.264 file from identical inputs, and the browser path was additionally confirmed to mux to 1080x1920 + AAC.

Scroll-driven animation with Playwright's built-in video recorder was evaluated and **rejected**: frame timing is bound to input events rather than a clock, producing variable-frame-rate output, and the built-in recorder emits low-bitrate WebM that cannot be controlled. Seeking a paused clock replaces it and yields exact CFR.

## Scope

**In scope:** accepting images, animating them, muxing audio, writing an MP4.

**Out of scope**, each deliberately a separate concern:

- Image generation. The skill accepts image paths from any source (Codex, screenshots, stock, the `design-system` skills) and never generates them.
- Scene/beat selection from an episode script.
- Subtitle burn-in from `script.txt`.

## Plugin Structure

A standalone plugin rather than a skill inside `media` or `instagram`: both of those consume it, and nesting it in either would force the other to reach across plugin boundaries.

```
plugins/video/
  .claude-plugin/plugin.json
  requirements.txt
  skills/video-render/SKILL.md
  src/
    __init__.py
    video_render.py          # CLI entry, dispatch, orchestration
    storyboard.py            # parse/normalize/validate -> Storyboard
    presets.py               # named preset -> (width, height, fps)
    encode.py                # frames->mp4, audio mux, ffprobe helpers
    backends/
      __init__.py
      ffmpeg_backend.py
      browser_backend.py
      scene.html
```

`plugins/video/.claude-plugin/plugin.json` follows the existing manifests:

```json
{
  "name": "video",
  "version": "0.1.0",
  "description": "Render images and audio into a finished MP4 using local ffmpeg and Playwright. No external AI service.",
  "author": { "name": "francisaraujo", "email": "francis.araujo@gmail.com" },
  "skills": ["./skills/video-render"]
}
```

`.claude-plugin/marketplace.json` gains a third plugin entry pointing at `./plugins/video`.

**No new dependencies.** `playwright`, `pytest`, and `pytest-mock` are already declared by the media plugin. Image dimensions are probed with `ffprobe` rather than Pillow specifically to avoid adding a dependency; Pillow is present on the current machine but is not declared in `requirements.txt`, so relying on it would be an undeclared dependency. `plugins/video/requirements.txt` restates `playwright>=1.40.0`, `pytest>=8.0.0`, and `pytest-mock>=3.12.0` so the plugin stands alone.

## Input Contract

A JSON storyboard is the primary interface, matching every existing media skill (`<path-to-config.json>`). Flags cover the common one-liner.

```bash
# quick
python3 plugins/video/src/video_render.py --images "assets/*.png" \
  --audio output/episode.mp3 --preset reel

# full control
python3 plugins/video/src/video_render.py storyboard.json
```

Storyboard schema:

```json
{
  "preset": "reel",
  "audio": "output/episode.mp3",
  "output": "output/video.mp4",
  "fit": "cover",
  "backend": "browser",
  "slides": [
    {
      "image": "assets/1.png",
      "caption": "The hook",
      "seconds": 4.0,
      "motion": "zoom-in",
      "transition": "fade",
      "transition_seconds": 0.75
    }
  ]
}
```

Field rules:

| Field | Required | Default |
|---|---|---|
| `preset` | no | `landscape` |
| `fps` | no | `30` |
| `audio` | no | none |
| `output` | no | `output/video.mp4` |
| `fit` | no | `cover` |
| `backend` | no | auto-selected |
| `slides[].image` | **yes** | — |
| `slides[].caption` | no | none |
| `slides[].seconds` | no | see Duration |
| `slides[].motion` | no | `zoom-in` |
| `slides[].transition` | no | `fade` |
| `slides[].transition_seconds` | no | `0.5` |

`motion` accepts `zoom-in`, `zoom-out`, `pan-left`, `pan-right`, `none`. `transition` accepts `fade` or `cut`. `fit` accepts `cover` (crop) or `contain` (pad). A storyboard with an empty `slides` array is an error.

**`transition` on slide N describes the transition *into* slide N from slide N-1.** It is ignored on the first slide, where it has no meaning. This direction is stated explicitly because either reading is plausible and the choice changes where each overlap lands.

Flags mirror storyboard fields: `--images` (glob or directory, sorted lexicographically), `--audio`, `--output`, `--preset`, `--fit`, `--backend`, `--seconds` (uniform per-slide duration), `--fps`. When `--images` names a directory, files matching `.png`, `.jpg`, `.jpeg`, and `.webp` are collected, case-insensitively; anything else in the directory is ignored. Flags and a storyboard path are mutually exclusive; passing both is an error rather than a silent precedence rule.

## Presets

`presets.py` maps a name to `(width, height, fps)`. Default fps is 30 for all presets, overridable via `--fps` or a storyboard `fps` key.

| Preset | Dimensions |
|---|---|
| `reel` | 1080x1920 |
| `story` | 1080x1920 |
| `square` | 1080x1080 |
| `landscape` | 1920x1080 |

`reel` and `story` are intentionally aliases; they are kept distinct because callers think in terms of the destination, and the two could diverge later.

## Duration and Audio

Resolved in `storyboard.py` before any rendering:

1. **No audio.** Total duration is the sum of slide durations. Slides without `seconds` default to 4.0s.
2. **Audio present, all slides have explicit `seconds`.** Durations are honored. The audio is muxed with `-shortest`. If total video and audio duration differ by more than 0.5s, a warning names both figures.
3. **Audio present, `seconds` omitted.** The audio duration (via `ffprobe`) is distributed evenly across slides.

Rule 3 is the primary podcast path: it makes "these six images across a three-minute episode" work without the caller computing per-slide timings.

**Mixing explicit and omitted `seconds` is an error only when audio is present** (rules 2 and 3). With audio, the even-distribution maths is genuinely ambiguous — it cannot be known whether the omitted slides should share the leftover audio or take the 4.0s default — so an explicit failure naming the offending slide indices is better than a surprising interpretation. Without audio (rule 1) there is nothing to distribute, so omitted slides simply take the 4.0s default and mixing is permitted.

Transitions overlap adjacent slides, so total duration is `sum(seconds) - sum(transition_seconds for non-cut transitions between slides)`. Duration resolution accounts for this so audio sync stays correct.

## Backend Contract

```python
def render(storyboard: Storyboard, workdir: Path) -> Path:
    """Return the path to a silent, constant-frame-rate MP4."""
```

Both backends emit a silent CFR MP4 at the preset's dimensions and fps. `encode.py` alone owns audio muxing. Backends therefore never touch audio, and each can be tested and replaced independently.

**Auto-selection:** if any slide has a non-empty `caption`, use `browser`; otherwise use `ffmpeg`. An explicit `--backend` or storyboard `backend` always wins. The chosen backend and the reason are always logged, e.g. `Backend: browser (3 slides have captions)`.

### ffmpeg backend

One `zoompan` clip per slide, joined by `xfade`. The source image is **upscaled before `zoompan`** (`scale=8000:-1`); this is required, not cosmetic — `zoompan` computes integer pan offsets, and without a large source the motion visibly steps. Output is `libx264 -crf 18 -pix_fmt yuv420p`.

Verified in probe: 9s of 1080p30 rendered in 12.7s.

### browser backend

`scene.html` is populated with slide data, then:

1. Every animation is constructed via `element.animate()` and immediately `pause()`d.
2. `window.__seek(t)` sets `currentTime` on every animation.
3. For each frame `i` in `range(fps * duration)`, seek to `i * 1000 / fps` ms and call `page.screenshot()`.
4. `encode.py` encodes the frame sequence at the target fps.

**`page.screenshot()` must not be passed `animations="disabled"`.** That option fast-forwards finite animations to completion, yielding a full sequence of identical end-state frames. This failure is silent: the output is a valid MP4 with correct dimensions, fps, frame count, and duration, containing no motion. It was hit during the probe and is the reason for the frame-difference test below.

The browser is wrapped in try/finally per CLAUDE.md. Chromium is launched with `--force-device-scale-factor=1 --hide-scrollbars`, and the page waits for image decode before the first capture.

Verified in probe: 270 frames captured in 27.2s, encoded in 2.0s.

## Aspect Ratio Handling

Images are fitted to the preset per `fit`: `cover` scales and center-crops, `contain` scales and pads with black.

Under `cover`, when the crop discards more than 20% of the source area, a warning names the file and the discarded percentage. This is a real case rather than a hypothetical: Codex emits 1024x1536 (2:3) and 1254x1254 (1:1) images, and a 2:3 source into a 9:16 `reel` loses meaningful content. The warning surfaces it at render time instead of after publishing.

## Error Handling

All validation runs before any rendering begins.

- **Missing or unreadable images** — every slide image is probed up front, and *all* failures are reported together rather than aborting on the first.
- **Missing binaries** — `ffmpeg`/`ffprobe` absence reports `install with: brew install ffmpeg`; a missing Chromium reports `playwright install chromium`. This matches the actionable style of the instagram skills.
- **ffmpeg failure** — non-zero exit surfaces full stderr, matching how `tts_generate.py` reports errors.
- **Playwright** — always wrapped in try/finally so the browser closes on error.
- **Empty `slides`**, **mixed explicit/omitted `seconds`**, **both flags and storyboard**, and **unknown preset/motion/transition/fit values** are all explicit errors naming the offending value.

Unlike `news_fetch.py`, there is no per-item error isolation: a storyboard is a single artifact, and silently dropping a slide would produce a video that is wrong rather than absent.

## Testing

TDD, following the existing suite's conventions (`conftest.py` puts the repo root on `sys.path`; external services are mocked).

`tests/test_presets.py`
- Each preset resolves to correct dimensions and default fps; unknown preset raises.

`tests/test_storyboard.py`
- Flag shorthand normalizes to the same model as the equivalent storyboard.
- `--images` glob expansion sorts lexicographically.
- Duration rule 1: no audio, durations summed; missing `seconds` defaults to 4.0.
- Duration rule 2: explicit durations honored; >0.5s mismatch warns.
- Duration rule 3: even distribution across probed audio duration.
- Transition overlap is subtracted from total duration.
- Mixed explicit/omitted `seconds` raises when audio is present, and is permitted (defaulting to 4.0s) when it is not.
- `transition` on slide N applies between N-1 and N, and is ignored on slide 0.
- `--images` pointed at a directory collects only image extensions, case-insensitively.
- Errors: empty slides, flags plus storyboard, unknown enum values.
- Missing images are reported together, not one at a time.

`tests/test_video_render.py`
- Backend auto-selection: any caption selects browser; no captions selects ffmpeg; explicit choice overrides both.
- **ffmpeg filtergraph guard** — the generated graph upscales before `zoompan`. Guards the jitter bug.
- **Frame-difference test** — capture two frames at different timestamps and assert the bytes differ. This is the only test that catches the `animations="disabled"` bug, which passes every metadata-based check.
- Cover-crop warning fires above 20% discarded, stays silent below.
- Missing ffmpeg and missing Chromium produce the actionable messages.
- **End-to-end smoke render** — two small generated images, 1s each, no audio, real ffmpeg. Asserts `ffprobe` reports the expected width, height, fps, frame count, and duration. This is a genuine render rather than a mock: it is local, fast, and free, and it is the only test proving the full pipeline works. Marked `@pytest.mark.integration` so it can be deselected.

Playwright is mocked everywhere except the frame-difference test, which needs a real browser to be meaningful.

## Skill Definition

`plugins/video/skills/video-render/SKILL.md` follows the media skills' frontmatter shape:

```yaml
---
name: video-render
description: Render images plus optional audio into an MP4 using local ffmpeg and Playwright. Writes output/video.mp4. Feeds instagram:reel and instagram:story-video.
argument-hint: <path-to-storyboard.json | --images GLOB>
allowed-tools: Bash(python3 *)
---
```

The body collects inputs, runs the renderer, confirms `output/video.mp4` exists, reports the backend chosen and any crop warnings, and reports full errors on failure.

## Files Changed

| File | Change |
|---|---|
| `.claude-plugin/marketplace.json` | Add `video` plugin entry |
| `plugins/video/.claude-plugin/plugin.json` | New manifest |
| `plugins/video/requirements.txt` | New — playwright, pytest, pytest-mock |
| `plugins/video/skills/video-render/SKILL.md` | New skill definition |
| `plugins/video/src/video_render.py` | New — CLI entry, dispatch, orchestration |
| `plugins/video/src/storyboard.py` | New — parse/normalize/validate, duration resolution |
| `plugins/video/src/presets.py` | New — preset table |
| `plugins/video/src/encode.py` | New — frames->mp4, audio mux, ffprobe helpers |
| `plugins/video/src/backends/ffmpeg_backend.py` | New — zoompan + xfade |
| `plugins/video/src/backends/browser_backend.py` | New — WAAPI seek + Playwright capture |
| `plugins/video/src/backends/scene.html` | New — HTML scene template |
| `plugins/video/src/__init__.py`, `src/backends/__init__.py` | New — package markers |
| `tests/test_presets.py` | New |
| `tests/test_storyboard.py` | New |
| `tests/test_video_render.py` | New |
| `README.md` | Document the video plugin |
