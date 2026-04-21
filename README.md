# media-agent-plugins

A Claude Code plugin that produces and publishes AI-generated podcast episodes from configurable news sources.

## Skills

| Skill | Command | Purpose |
|---|---|---|
| `news-fetch` | `/media:news-fetch` | Fetch and deduplicate news from RSS feeds and web scraping |
| `script-generate` | `/media:script-generate` | Generate a podcast script from news items using Claude |
| `tts-generate` | `/media:tts-generate` | Convert script to audio using OpenAI TTS |
| `spotify-publish` | `/media:spotify-publish` | Upload and publish episode to Spotify for Creators |
| `podcast-daily` | `/media:podcast-daily` | Run the full pipeline end-to-end |

## Quick Install

```bash
claude plugin marketplace add franaraujo77/media-agent-plugins
claude plugin install media@franaraujo77-marketplace
```

## Docs

- [Installation guide](docs/superpowers/specs/2026-04-20-media-plugin-design.md#installation)
- [Usage](docs/superpowers/specs/2026-04-20-media-plugin-design.md#usage)
