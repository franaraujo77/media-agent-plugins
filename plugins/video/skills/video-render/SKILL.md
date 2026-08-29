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

2. Run the renderer. A storyboard path and `--images` are mutually exclusive — pass one or
   the other:

   ```bash
   python3 plugins/video/src/video_render.py <argument>
   ```

   Quick form (no storyboard file):

   ```bash
   python3 plugins/video/src/video_render.py \
     --images "assets/*.png" --audio output/episode.mp3 --preset reel
   ```

   The quick form also accepts `--output <path>` (default `output/video.mp4`),
   `--fit cover|contain`, `--backend ffmpeg|browser`, `--seconds <float>` (uniform per-slide
   duration), `--fps <int>`, `--music <file>` (a bed mixed under `--audio`), and
   `--music-volume <float>`. These flags apply only to the `--images` quick form — passing
   any of them together with a storyboard path is an **error**, not a silent override. Set
   `output`, `fit`, `backend`, `audio`, `music`, `seconds`, and `fps` inside the JSON instead.
   The remaining audio controls (trim, fades, loop) are storyboard-only — see **Audio tracks**.

3. Report the backend line the script prints (`Backend: ffmpeg (...)` or
   `Backend: browser (...)`), then watch for two different kinds of `Warning:` line and
   don't conflate them:
   - `Warning: <file>: ... discards N% of the image` — a crop warning (only under `fit:
     cover`). Part of the image is being cut off; suggest `--fit contain` if that matters.
   - `Warning: video is Xs but audio is Ys (...)` — a duration-drift warning, printed when
     every slide has an explicit `seconds` and the total drifts from the audio by more than
     0.5s. `--fit` is irrelevant here; the fix is to adjust the slides' `seconds` (or drop
     them so duration is derived from the audio instead).

4. Confirm `output/video.mp4` was written. If the script errors, report the full error message.

## Storyboard format

```json
{
  "preset": "reel",
  "audio": "output/episode.mp3",
  "music": { "file": "assets/bed.mp3", "volume": 0.15, "loop": true, "fade_out": 2.0 },
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
evenly across the slides. Mixing explicit and omitted `seconds` is an error only when
`audio` is present; with no audio, an omitted `seconds` just takes the 4.0s default and
mixing is fine.

## Audio tracks

There are two audio slots, and the difference between them is which one controls time:

- **`audio`** — the primary track (narration, an episode MP3). It **sets the video's
  length**: the slide-duration rules below are computed from it.
- **`music`** — a bed mixed *under* `audio`. It **never** changes the length. Shorter than
  the video, it is padded with silence (or set `loop`); longer, it is cut off.

Either slot takes a bare path or an object. `"audio": "e.mp3"` and
`"audio": {"file": "e.mp3"}` are the same thing.

| Field | Default | Meaning |
|---|---|---|
| `file` | — | required; path to the audio file |
| `volume` | `1.0` | linear gain. `0.15` is a typical bed under narration; `0.5` is −6 dB |
| `start` | `0.0` | seconds to skip into the source before it starts playing |
| `duration` | to the end | seconds to play, measured from `start` |
| `fade_in` | `0.0` | seconds of fade up from silence |
| `fade_out` | `0.0` | seconds of fade down at the end |
| `loop` | `false` | repeat the file until the video ends |

Gains are **not** renormalised when both slots are set — `volume` is what you hear, so a
bed at `1.0` under narration will be as loud as the narration. Start around `0.15`.

`start` and `duration` also shrink the duration budget: with `{"file": "e.mp3", "start":
10}` on a 40s file, the video is built to the remaining 30s.

A `fade_out` needs a known length. It is measured from the track's `duration` if set,
otherwise from the video's length — so `fade_out` on a `music` bed with neither is an error.

## Backends

Chosen automatically unless `--backend` is passed: any slide with a caption uses the
browser backend (HTML/CSS, full typography); otherwise ffmpeg (faster, pan/zoom only).

**Temp-disk cost of the browser backend.** It writes one full-resolution PNG per frame
into a temporary directory before encoding, so the peak scratch space is roughly
`duration x fps x PNG size`. At 1080x1920/30fps a 3-minute video is 5,400 PNGs — on the
order of 8-25 GB of `/tmp` — and running out surfaces as an `ENOSPC` failure. For long
captioned renders, check free space first, point `TMPDIR` at a roomier volume, or lower
`--fps`. The ffmpeg backend streams and needs no such scratch space.

## Feeding the publish skills

`output/video.mp4` is directly consumable:

```bash
python3 ~/InstagramAI/scripts/publish_reel.py --video output/video.mp4 --caption "..."
```
