# Design: script-generate keyless support

**Date:** 2026-04-21
**Status:** Approved

## Problem

`script-generate` requires `ANTHROPIC_API_KEY` to be set because `script_generate.py` calls the Anthropic API directly. Users on a Claude plan (Pro/Team/Enterprise) have no API credits and no API key, so the skill fails for them even though they already have access to Claude via Claude Code.

## Solution

Add a dual-path to `SKILL.md`. The skill detects whether `ANTHROPIC_API_KEY` is available and routes accordingly. Output quality is identical for both paths — same prompt, same model, same format.

## What changes

**Only `plugins/media/skills/script-generate/SKILL.md` is modified.** `script_generate.py` is untouched.

### API-key path (existing, unchanged)

If `ANTHROPIC_API_KEY` is set in the environment, run:

```bash
python3 plugins/media/src/script_generate.py <config>
```

Prompt caching is preserved for API users.

### Native path (new)

If `ANTHROPIC_API_KEY` is not set, Claude Code generates the script in-context:

1. Read `output/news-items.json`
2. Read the config file (passed as argument) to get `podcast.name` and `podcast.description`
3. Generate the script using the exact same prompt structure as `script_generate.py`:
   - **System prompt:** "You are a professional podcast host writing scripts for a daily news podcast. Your style is conversational, engaging, and concise. You summarize complex topics in plain language suitable for general audiences."
   - **User prompt:** Write a script for `<podcast_name>` — `<description>`. Today's date. News items (title, source, summary). Structure: brief intro (2–3 sentences) → one segment per news item (2–3 sentences, no URLs) → brief closing (1–2 sentences). Target: 450–750 words. Spoken script only — no labels, no stage directions.
4. Write the generated script to `output/script.txt` using the Write tool
5. Report word count and confirm the file was written

### SKILL.md frontmatter

`allowed-tools` expands from `Bash(python3 *)` to also include `Read` and `Write` for the native path.

## What does NOT change

- `script_generate.py` — untouched
- `podcast-daily` orchestrator — calls `script-generate` skill, which handles the routing internally
- Output format — identical for both paths
- `ai-ml-podcast.json` and `prod-grade-ai-podcast.json` configs — no changes

## Success criteria

- Plan users (no `ANTHROPIC_API_KEY`) can run `script-generate` and get a valid `output/script.txt`
- API users (with `ANTHROPIC_API_KEY`) continue to use the Python script path unchanged
- Both paths produce a 450–750 word spoken podcast script in the same format
