# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A Claude Code marketplace plugin (`franaraujo77-marketplace/media`) that automates end-to-end podcast production: fetch news → generate script → convert to audio → publish to Spotify. Skills are invoked as `/media:<skill-name>` within Claude Code.

## Commands

**Install dependencies:**
```bash
pip install -r plugins/media/requirements.txt
playwright install chromium
```

**Run tests:**
```bash
pytest tests/ -v                          # all tests
pytest tests/test_news_fetch.py -v        # single file
pytest tests/ -k "test_fetch_rss" -v      # single test
```

**Run a skill manually:**
```bash
python3 plugins/media/src/news_fetch.py plugins/media/configs/ai-ml-podcast.json
python3 plugins/media/src/script_generate.py plugins/media/configs/ai-ml-podcast.json
python3 plugins/media/src/tts_generate.py plugins/media/configs/ai-ml-podcast.json
python3 plugins/media/src/spotify_publish.py plugins/media/configs/ai-ml-podcast.json
```

**Required environment variables:**
- `ANTHROPIC_API_KEY` — Claude API (script-generate)
- `OPENAI_API_KEY` — OpenAI TTS (tts-generate)
- `SPOTIFY_EMAIL`, `SPOTIFY_PASSWORD` — Spotify login (spotify-publish)

## Architecture

### Plugin Structure

Each skill has two parts:
- `plugins/media/skills/<name>/SKILL.md` — instructions Claude uses to invoke the skill
- `plugins/media/src/<name>.py` — Python implementation

Skills communicate through files in `output/` (gitignored):
- `output/news-items.json` — produced by news-fetch, consumed by script-generate
- `output/script.txt` — produced by script-generate, consumed by tts-generate
- `output/episode.mp3` — produced by tts-generate, consumed by spotify-publish

### Skills

| Skill | Purpose |
|---|---|
| `news-fetch` | Parse RSS feeds + Playwright scraping, deduplicate by URL; optional `lookback_days` filter |
| `script-generate` | Call Claude Sonnet 4.6 with prompt caching (ephemeral) to produce 450–4000 word script |
| `tts-generate` | Call OpenAI TTS; splits scripts >4096 chars into chunks and stitches audio |
| `spotify-publish` | Playwright browser automation against Spotify for Creators |
| `podcast-daily` | Orchestrator — runs all four skills sequentially |

### Plugin Manifests

- `marketplace.json` — registry entry pointing to this repo
- `plugins/media/plugin.json` — skill list, metadata, author

### Configuration

Podcast behavior is driven by a JSON config (see `plugins/media/configs/ai-ml-podcast.json`). The config defines news sources (RSS or scrape), TTS voice/model, Spotify show ID, and episode title template with `{date}` substitution.

## Key Patterns

**Prompt caching**: `script_generate.py` uses `cache_control: {type: "ephemeral"}` on the system prompt to reduce Claude API costs on repeated runs.

**Browser automation**: `spotify_publish.py` uses Playwright with ARIA role/label selectors (more stable than CSS). Always wraps browser in try/finally to ensure cleanup on error.

**Error isolation**: Each source fetch in `news_fetch.py` is wrapped in try/except so a single failing source doesn't abort the pipeline.

**Test mocking**: Tests use `unittest.mock` / `pytest-mock` to mock all external APIs (Anthropic, OpenAI, Playwright). `conftest.py` adds the repo root to `sys.path`.
