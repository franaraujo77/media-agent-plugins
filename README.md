# media-agent-plugins

A Claude Code plugin that produces and publishes AI-generated podcast episodes from configurable news sources.

## Skills

| Skill | Command | Purpose |
|---|---|---|
| `news-fetch` | `/media:news-fetch` | Fetch and deduplicate news from RSS feeds and web scraping |
| `script-generate` | `/media:script-generate` | Generate a podcast script from news items using Claude |
| `tts-generate` | `/media:tts-generate` | Convert script to audio using OpenAI TTS |
| `spotify-publish` | `/media:spotify-publish` | Upload and publish episode to Spotify for Creators |
| `podcast-run` | `/media:podcast-run` | Run the full pipeline end-to-end |

## Video

The `video` plugin renders images plus an optional audio track into a finished MP4,
using only local tooling — ffmpeg and Playwright. No external AI service is involved.

| Skill | Command | Purpose |
|---|---|---|
| `video-render` | `/video:video-render` | Render images + optional audio into `output/video.mp4` |

**Backends.** Two rendering backends are picked automatically, or forced with `--backend`:

- **ffmpeg** (default when no slide has a caption) — zoompan Ken Burns motion and
  xfade/concat transitions. Fast, no text rendering.
- **browser** (default when any slide has a caption) — an HTML/CSS scene seeked frame
  by frame through the Web Animations API and captured with Playwright. Slower, but
  supports full typography for captions.

The script prints which backend it chose and why, e.g. `Backend: ffmpeg (no slide has a caption)`.

**Storyboard format.** A storyboard is a JSON file describing the target preset, an
optional audio track, and a list of slides:

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

- `preset`: `reel`/`story` (1080x1920), `square` (1080x1080), or `landscape` (1920x1080, default).
- `motion`: `zoom-in`, `zoom-out`, `pan-left`, `pan-right`, or `none`.
- `transition`: `fade` or `cut` — the transition *into* that slide from the previous one;
  ignored on the first slide.
- `fit`: `cover` (crop to fill) or `contain` (pad to fit). Under `cover`, cropping away
  more than 15% of an image prints a `Warning:` line.
- With `audio` set, omit `seconds` on every slide to distribute the audio duration evenly
  across them, or set `seconds` on every slide (mixing the two is an error when audio is present).

Without a storyboard file, pass images and options directly:

```bash
python3 plugins/video/src/video_render.py --images "assets/*.png" --audio output/episode.mp3 --preset reel
```

**Feeding Instagram.** `output/video.mp4` is the direct input to `instagram:reel` and
`instagram:story-video` — pass it as `--video` to either publishing script.

## Quick Install

```bash
claude plugin marketplace add franaraujo77/media-agent-plugins
claude plugin install media@franaraujo77-media-agent-plugins
```

## Docs

- [Usage guide](docs/usage.md) — configuration reference, soul setup, environment variables

## License

[MIT](LICENSE)
