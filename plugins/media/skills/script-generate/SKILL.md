---
name: script-generate
description: Generate a natural podcast script from fetched news items using Claude. Reads output/news-items.json, writes output/script.txt. Run after news-fetch and before tts-generate.
argument-hint: <path-to-config.json>
allowed-tools: Bash(python3 *), Read, Write
---

# script-generate

Generate a podcast script for the show defined in the config file provided as the argument.
Requires `output/news-items.json` to exist (run news-fetch first).

## Steps

1. Check whether `ANTHROPIC_API_KEY` is set:

   ```bash
   echo "${ANTHROPIC_API_KEY:+set}"
   ```

2. **If the API key is set** — run the script generation via Python:

   ```bash
   python3 plugins/media/src/script_generate.py <argument>
   ```

   Report the word count and confirm `output/script.txt` was written.
   If the script errors, report the full error message.

3. **If the API key is NOT set** — generate the script natively:

   - Read `output/news-items.json`
   - Read `<argument>` (the config file) to get `podcast.name`, `podcast.description`, and optionally `soul`

   **Resolve the soul:**
   - If `soul` is absent in the config → use the default system prompt below
   - If `soul` is a string → read the JSON file at that path to get the soul object
   - If `soul` is an object → use it directly

   **Build the system prompt:**
   - If no soul: "You are a professional podcast host writing scripts for a daily news podcast. Your style is conversational, engaging, and concise. You summarize complex topics in plain language suitable for general audiences."
   - If soul present: "You are <soul.writer.persona>. Your tone is <soul.writer.tone>. Your writing style is <soul.writer.formality>. Your humor is <soul.writer.humor>. Write scripts that reflect this personality consistently."

   **Build the user prompt:**

   Write a podcast script for "<podcast.name>" — <podcast.description>.

   Today's date: <today's date, e.g. April 21, 2026>

   News items:
   <for each item: **title** (source)\nsummary>

   Structure:
   - Brief intro (2-3 sentences, welcome listeners, mention the date)
   - One segment per news item (2-3 sentences each, conversational tone, no URLs)
   - Brief closing (1-2 sentences)

   Target: 450-750 words. Write only the spoken script — no labels, no stage directions.

   If soul has `speaker.delivery`: append → "Delivery style: <soul.speaker.delivery> Apply these cues throughout the script so the text reads naturally when converted to audio."

   - Generate the podcast script using the system and user prompts above
   - Write the generated script to `output/script.txt` using the Write tool
   - Report the word count and confirm `output/script.txt` was written
