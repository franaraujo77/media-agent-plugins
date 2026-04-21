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
/media:podcast-run plugins/media/configs/my-podcast.json
```

## Scheduling the pipeline

Use the `/schedule` skill to create a recurring remote trigger that runs the full pipeline automatically on a cron schedule. The trigger runs a fresh Claude Code remote session in Anthropic's cloud — it is not tied to your local machine.

```
/schedule
```

When prompted, choose **Create** and provide:

- **Prompt** — the instruction the remote agent will follow, e.g.:

  ```
  Run /media:podcast-run plugins/media/configs/my-podcast.json
  Stop immediately and report the full error if any step fails.
  ```

- **Schedule** — cron expression in UTC. Common examples (times shown for America/Sao_Paulo → UTC):

  | Frequency | Local (Sao Paulo) | Cron (UTC) |
  |---|---|---|
  | Daily at 7am | 7:00 BRT (UTC-3) | `0 10 * * *` |
  | Weekdays at 7am | 7:00 BRT (UTC-3) | `0 10 * * 1-5` |
  | Weekly on Monday 7am | 7:00 BRT (UTC-3) | `0 10 * * 1` |

  Minimum interval is 1 hour.

- **Repo** — `https://github.com/franaraujo77/media-agent-plugins`

### Environment variables for scheduled runs

The remote agent does not have access to your local machine. Environment variables must be available in the remote session. Set them in your Claude Code settings at [claude.ai/code/settings](https://claude.ai/code/settings) under the **Environment** section:

| Variable | Required for |
|---|---|
| `OPENAI_API_KEY` | `tts-generate` |
| `SPOTIFY_EMAIL` | `spotify-publish` |
| `SPOTIFY_PASSWORD` | `spotify-publish` |

`ANTHROPIC_API_KEY` is **not required** — `script-generate` generates the script natively using the remote session's Claude context.

### Managing scheduled triggers

```
/schedule          # list, update, or run triggers
```

To delete a trigger, visit [claude.ai/code/scheduled](https://claude.ai/code/scheduled).
