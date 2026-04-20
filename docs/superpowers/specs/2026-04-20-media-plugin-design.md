# Media Plugin — Design Spec

**Date:** 2026-04-20
**Status:** Approved

---

## Overview

The `media` plugin is a collection of reusable Claude Code skills for producing and publishing AI-generated podcast episodes. Given a configuration file, it fetches news from configurable sources, generates a spoken script via Claude, converts it to audio via OpenAI TTS, and publishes it as a podcast episode to Spotify for Creators using browser automation.

This plugin is the first installable unit in the `ai-agent-plugins` marketplace repo.

---

## Plugin Description

| Field | Value |
|---|---|
| Plugin name | `media` |
| Version | `1.0.0` |
| Invocation prefix | `/media:` |
| Runtime | Python 3.11+, Playwright |
| External APIs | Anthropic Claude API, OpenAI TTS API |
| Publishing target | Spotify for Creators (browser automation) |

Skills provided:

| Skill | Slash command | Purpose |
|---|---|---|
| `news-fetch` | `/media:news-fetch` | Fetch and deduplicate news from RSS feeds and web scraping |
| `script-generate` | `/media:script-generate` | Generate a podcast script from news items using Claude |
| `tts-generate` | `/media:tts-generate` | Convert script to audio using OpenAI TTS |
| `spotify-publish` | `/media:spotify-publish` | Upload and publish episode to Spotify for Creators |
| `podcast-daily` | `/media:podcast-daily` | Orchestrator: runs the full pipeline end-to-end |

---

## Repo Structure

```
ai-agent-plugins/
├── marketplace.json
├── plugins/
│   └── media/
│       ├── plugin.json
│       ├── skills/
│       │   ├── news-fetch/
│       │   │   └── SKILL.md
│       │   ├── script-generate/
│       │   │   └── SKILL.md
│       │   ├── tts-generate/
│       │   │   └── SKILL.md
│       │   ├── spotify-publish/
│       │   │   └── SKILL.md
│       │   └── podcast-daily/
│       │       └── SKILL.md
│       ├── src/
│       │   ├── news_fetch.py
│       │   ├── script_generate.py
│       │   ├── tts_generate.py
│       │   └── spotify_publish.py
│       └── configs/
│           └── ai-ml-podcast.json
└── output/                        ← gitignored, temp files per run
```

---

## Configuration

Each podcast is driven by a JSON config file in `plugins/media/configs/`. Multiple config files can coexist — one per podcast show.

### Schema

```json
{
  "podcast": {
    "name": "string — display name of the podcast show",
    "description": "string — show description",
    "episode_title_template": "string — supports {date} placeholder",
    "language": "string — ISO 639-1 language code, e.g. 'en'"
  },
  "sources": [
    {
      "type": "rss | scrape",
      "url": "string — feed URL or page URL",
      "label": "string — human-readable source name",
      "max_items": "integer — max items to pull (default: 5)"
    }
  ],
  "tts": {
    "voice": "string — OpenAI TTS voice (alloy | echo | fable | onyx | nova | shimmer)",
    "model": "string — tts-1 | tts-1-hd"
  },
  "spotify": {
    "show_id": "string — Spotify show ID from Spotify for Creators dashboard",
    "credentials_env": "string — comma-separated env var names for email and password"
  }
}
```

### Example: `ai-ml-podcast.json`

```json
{
  "podcast": {
    "name": "AI/ML Daily",
    "description": "Daily digest of the latest AI and ML news",
    "episode_title_template": "AI/ML Daily — {date}",
    "language": "en"
  },
  "sources": [
    { "type": "rss", "url": "https://arxiv.org/rss/cs.AI", "label": "ArXiv AI", "max_items": 5 },
    { "type": "rss", "url": "https://www.deepmind.com/blog/rss.xml", "label": "DeepMind Blog", "max_items": 3 },
    { "type": "scrape", "url": "https://huggingface.co/blog", "label": "HuggingFace Blog", "max_items": 3 }
  ],
  "tts": {
    "voice": "alloy",
    "model": "tts-1-hd"
  },
  "spotify": {
    "show_id": "<your-show-id>",
    "credentials_env": "SPOTIFY_EMAIL,SPOTIFY_PASSWORD"
  }
}
```

---

## Installation

### Prerequisites

- Claude Code CLI installed
- Python 3.11+
- `ANTHROPIC_API_KEY` set in environment
- `OPENAI_API_KEY` set in environment
- Spotify for Creators account with an existing show created

### 1. Add the marketplace

```bash
claude plugin marketplace add francisaraujo/ai-agent-plugins
```

### 2. Install the plugin

```bash
claude plugin install media@francisaraujo-marketplace
```

Or interactively via `/plugin`.

### 3. Install Python dependencies

```bash
pip install playwright feedparser openai anthropic
playwright install chromium
```

### 4. Set environment variables

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export SPOTIFY_EMAIL=your@email.com
export SPOTIFY_PASSWORD=yourpassword
```

### 5. Configure your podcast

Copy and edit the example config:

```bash
cp plugins/media/configs/ai-ml-podcast.json plugins/media/configs/my-podcast.json
```

Fill in your `show_id` from the Spotify for Creators dashboard URL:
`https://creators.spotify.com/pod/show/<show_id>/`

---

## Usage

### Run the full pipeline

```
/media:podcast-daily plugins/media/configs/ai-ml-podcast.json
```

This fetches today's news, generates a script, converts to audio, and publishes the episode.

### Run individual steps

```
/media:news-fetch plugins/media/configs/ai-ml-podcast.json
/media:script-generate plugins/media/configs/ai-ml-podcast.json
/media:tts-generate plugins/media/configs/ai-ml-podcast.json
/media:spotify-publish plugins/media/configs/ai-ml-podcast.json
```

Each step reads from and writes to `output/` in the project root. Steps can be re-run individually to retry a failed step without re-running the whole pipeline.

### Schedule daily publishing

```
/schedule daily at 7am — run /media:podcast-daily plugins/media/configs/ai-ml-podcast.json
```

The scheduled agent runs headlessly. Ensure all environment variables are available in the scheduled environment.

---

## Skill Designs

### `news-fetch`

- Reads the `sources` array from the config file
- For `rss` sources: fetches and parses the feed, extracts title, summary, link, and published date for up to `max_items` recent entries
- For `scrape` sources: uses Playwright (headless Chromium) to load the page and extract article titles and links
- Deduplicates items by URL across all sources
- Writes structured output to `output/news-items.json`

Output format:
```json
[
  {
    "title": "string",
    "summary": "string",
    "url": "string",
    "source": "string",
    "published": "ISO 8601 date string"
  }
]
```

### `script-generate`

- Reads `output/news-items.json` and podcast metadata from config
- Calls Claude API with a prompt instructing it to write a natural podcast script
- Script structure: brief intro → one segment per news item (2-3 sentences each) → closing
- Target length: 3-5 minutes of spoken audio (~450-750 words)
- Writes plain text to `output/script.txt`

### `tts-generate`

- Reads `output/script.txt`
- Calls OpenAI TTS API with voice and model from config
- Writes audio to `output/episode.mp3`

### `spotify-publish`

- Reads `output/episode.mp3` and episode metadata from config
- Renders episode title using `episode_title_template` with today's date
- Uses Playwright to:
  1. Log into Spotify for Creators with credentials from env vars
  2. Navigate to the configured show
  3. Create a new episode, upload the audio file
  4. Fill in title and description (summary of today's news items)
  5. Publish immediately
- Reports the published episode URL on success

### `podcast-daily` (orchestrator)

- Runs `news-fetch` → `script-generate` → `tts-generate` → `spotify-publish` in sequence
- Stops and reports the failure step + error message if any step fails
- On success, cleans up `output/` temp files and reports the published episode URL

---

## Adding a New Podcast

1. Create a new config file in `plugins/media/configs/`
2. Fill in podcast metadata, sources, and Spotify show ID
3. Run `/media:podcast-daily plugins/media/configs/your-new-podcast.json`
4. Schedule it independently with `/schedule`

No code changes required.
