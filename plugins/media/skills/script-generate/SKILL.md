---
name: script-generate
description: Generate a natural podcast script from fetched news items using Claude. Reads output/news-items.json, writes output/script.txt. Run after news-fetch and before tts-generate.
argument-hint: <path-to-config.json>
allowed-tools: Bash(python3 *)
---

# script-generate

Generate a podcast script for the show defined in the config file provided as the argument.
Requires `output/news-items.json` to exist (run news-fetch first).

## Steps

1. Run the script generation:

   ```bash
   python3 plugins/media/src/script_generate.py <argument>
   ```

2. Report the word count and confirm `output/script.txt` was written.
   If the script errors, report the full error message.
