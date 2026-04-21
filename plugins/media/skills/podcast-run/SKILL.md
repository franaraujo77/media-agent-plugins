---
name: podcast-run
description: Run the full podcast pipeline end-to-end — fetch news, generate script, create audio, publish to Spotify. Pass a config file as the argument. Calls all four media skills in sequence.
argument-hint: <path-to-config.json>
allowed-tools: Bash(rm *), Skill
---

# podcast-run

Run the complete pipeline for the podcast defined in the config file provided as the argument.

## Steps

Invoke each skill in sequence. Stop and report the full error message if any step fails — do not continue to the next step.

1. Fetch news:

   Use the `Skill` tool with skill `media:news-fetch` and argument `<argument>`.

2. Generate script:

   Use the `Skill` tool with skill `media:script-generate` and argument `<argument>`.

3. Generate audio:

   Use the `Skill` tool with skill `media:tts-generate` and argument `<argument>`.

4. Publish to Spotify:

   Use the `Skill` tool with skill `media:spotify-publish` and argument `<argument>`.

5. Clean up temp files:

   ```bash
   rm -f output/news-items.json output/script.txt output/episode.mp3
   ```

6. Report the published episode URL from step 4's output.
