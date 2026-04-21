---
name: podcast-run
description: Run the full podcast pipeline end-to-end — fetch news, generate script, create audio, publish to Spotify. Pass a config file as the argument. Calls all four media skills in sequence.
argument-hint: <path-to-config.json>
allowed-tools: Bash(python3 *), Bash(rm *)
---

# podcast-run

Run the complete pipeline for the podcast defined in the config file provided as the argument.

## Steps

Run each command in sequence. Stop and report the full error message if any step fails — do not continue to the next step.

1. Fetch news:

   ```bash
   python3 plugins/media/src/news_fetch.py <argument>
   ```

2. Generate script:

   ```bash
   python3 plugins/media/src/script_generate.py <argument>
   ```

3. Generate audio:

   ```bash
   python3 plugins/media/src/tts_generate.py <argument>
   ```

4. Publish to Spotify:

   ```bash
   python3 plugins/media/src/spotify_publish.py <argument>
   ```

5. Clean up temp files:

   ```bash
   rm -f output/news-items.json output/script.txt output/episode.mp3
   ```

6. Report the published episode URL from step 4's output.
