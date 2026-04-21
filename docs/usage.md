# Usage Guide

## Configuration

Each podcast is driven by a JSON config file. Pass the config path as the argument to any skill.

### Minimal config

```json
{
  "podcast": {
    "name": "My Podcast",
    "description": "A short description of what the show covers.",
    "episode_title_template": "My Podcast — {date}",
    "language": "en"
  },
  "sources": [
    { "type": "rss", "url": "https://example.com/feed.xml", "max_items": 5 },
    { "type": "scrape", "url": "https://example.com/news", "label": "Example News", "max_items": 5 }
  ],
  "tts": {
    "voice": "alloy",
    "model": "tts-1-hd"
  },
  "spotify": {
    "show_id": "YOUR_SHOW_ID",
    "credentials_env": "SPOTIFY_EMAIL,SPOTIFY_PASSWORD"
  }
}
```

## Soul configuration

`soul` is an optional field that controls how the script is written and how it should be spoken. Omitting it uses default behavior.

### Inline soul

Define the soul directly in the config:

```json
"soul": {
  "writer": {
    "persona": "A no-nonsense senior AI engineer who cuts through hype.",
    "tone": "skeptical",
    "formality": "casual",
    "humor": "dry"
  },
  "speaker": {
    "delivery": "Use ellipses for natural pauses. Capitalize words you want stressed. No exclamation marks."
  }
}
```

### Reusable soul file

Point to a shared soul file to reuse the same personality across multiple shows:

```json
"soul": "plugins/media/souls/cynical-engineer.json"
```

The soul file uses the same schema as the inline `soul` object.

### Writer soul fields

| Field | Type | Description | Valid values |
|---|---|---|---|
| `persona` | string | Free-form description of the host's personality | Any text |
| `tone` | string | Overall emotional register | `skeptical` `optimistic` `neutral` `measured` `excited` |
| `formality` | string | Language register | `casual` `professional` `mixed` |
| `humor` | string | Amount and style of humor | `none` `dry` `light` `heavy` |

### Speaker soul fields

| Field | Type | Description |
|---|---|---|
| `delivery` | string | Instructions for embedding TTS-friendly delivery cues in the script text (ellipses for pauses, em dashes for rhythm, capitalization for stress, etc.) |

### How it works

- **Writer soul** replaces the script-generation system prompt with one built from your persona and style knobs.
- **Speaker soul** appends delivery instructions to the user prompt, telling Claude to embed text-level cues (not SSML) that influence how OpenAI TTS renders the audio.
- Shows without a `soul` field behave exactly as before.

## Required environment variables

| Variable | Used by | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | `script-generate` | Claude API key. Optional — plan users generate natively via Claude Code. |
| `OPENAI_API_KEY` | `tts-generate` | OpenAI API key for TTS audio generation |
| `SPOTIFY_EMAIL` | `spotify-publish` | Spotify for Creators login email |
| `SPOTIFY_PASSWORD` | `spotify-publish` | Spotify for Creators login password |

Set these in `~/.claude/settings.json` under `env`:

```json
{
  "env": {
    "OPENAI_API_KEY": "sk-...",
    "SPOTIFY_EMAIL": "you@example.com",
    "SPOTIFY_PASSWORD": "yourpassword"
  }
}
```

## Running skills

```
/media:news-fetch plugins/media/configs/my-podcast.json
/media:script-generate plugins/media/configs/my-podcast.json
/media:tts-generate plugins/media/configs/my-podcast.json
/media:spotify-publish plugins/media/configs/my-podcast.json

# Or the full pipeline in one command:
/media:podcast-daily plugins/media/configs/my-podcast.json
```
