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
