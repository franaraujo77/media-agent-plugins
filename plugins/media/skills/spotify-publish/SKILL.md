---
name: spotify-publish
description: Publish a podcast episode to Spotify for Creators via browser automation. Reads output/episode.mp3 and output/news-items.json. Run after tts-generate.
argument-hint: <path-to-config.json>
allowed-tools: Bash(python3 *)
---

# spotify-publish

Publish today's episode to Spotify for Creators using credentials from environment variables.
Requires `output/episode.mp3` and `output/news-items.json` to exist.

## Prerequisites

Ensure these environment variables are set:
- `SPOTIFY_EMAIL` — Spotify for Creators login email
- `SPOTIFY_PASSWORD` — Spotify for Creators password
- `show_id` must be filled in the config file (from `https://creators.spotify.com/pod/show/<show_id>/`)

## Steps

1. Run the publish script with the config path argument:

   ```bash
   python3 plugins/media/src/spotify_publish.py <argument>
   ```

2. Report the published episode URL on success. If the script errors, report the full error message.
   If selectors fail (page structure changed), note which step failed and describe what was visible on the page.
