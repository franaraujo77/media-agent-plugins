---
name: tts-generate
description: Convert a podcast script to audio using OpenAI TTS. Reads output/script.txt, writes output/episode.mp3. Run after script-generate and before spotify-publish.
argument-hint: <path-to-config.json>
allowed-tools: Bash(python3 *)
---

# tts-generate

Convert the script in `output/script.txt` to audio using the voice and model from the config file provided as the argument.
Requires `output/script.txt` to exist (run script-generate first).

## Steps

1. Run the TTS conversion:

   ```bash
   python3 plugins/media/src/tts_generate.py <argument>
   ```

2. Confirm `output/episode.mp3` was written. If the script errors, report the full error message.
