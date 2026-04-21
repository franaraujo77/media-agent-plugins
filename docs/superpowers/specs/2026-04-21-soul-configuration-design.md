# Design: Soul configuration for writer and speaker

**Date:** 2026-04-21
**Status:** Approved

## Problem

The podcast pipeline currently uses a fixed system prompt and no delivery guidance for TTS. All shows sound and read identically regardless of their intended personality. There is no way to configure the writing style or spoken delivery character of a show.

## Solution

Add an optional `soul` field to podcast configs that defines a **writer soul** (persona + style knobs shaping how the script is written) and a **speaker soul** (delivery instructions embedded in the script text to guide TTS rendering). Soul can be defined inline per-show or as a reusable file shared across shows.

## Soul schema

The `soul` field in a podcast config accepts two forms:

**Inline:**
```json
"soul": {
  "writer": {
    "persona": "A cynical senior engineer who's seen every AI hype cycle and calls out the BS immediately.",
    "tone": "skeptical",
    "formality": "casual",
    "humor": "dry"
  },
  "speaker": {
    "delivery": "Use ellipses for natural pauses. Use em dashes for rhythm breaks. Capitalize words you want stressed. Avoid exclamation marks — confidence, not hype."
  }
}
```

**Reference (path to a soul file):**
```json
"soul": "plugins/media/souls/cynical-engineer.json"
```

Soul files in `plugins/media/souls/` use the same schema as the inline object.

**Valid values:**
- `tone`: `skeptical` | `optimistic` | `neutral` | `measured` | `excited`
- `formality`: `casual` | `professional` | `mixed`
- `humor`: `none` | `dry` | `light` | `heavy`
- `persona`: free-form string
- `delivery`: free-form string with TTS cue instructions

Absent `soul` field → current default behavior (no change, backward compatible).

## Integration into script_generate.py

A `resolve_soul(config)` function handles the three cases:
1. `soul` is a string → read JSON from that file path
2. `soul` is an object → use directly
3. `soul` is absent → return `None`

**Writer soul → system prompt.** When a soul is present, the current generic system prompt constant is replaced by one built from the persona and style knobs:

> "You are [persona]. Your tone is [tone]. Your writing style is [formality]. Your humor is [humor]. Write scripts that reflect this personality consistently."

When no soul is present, the existing system prompt is used unchanged.

**Speaker soul → user prompt.** The delivery instructions are appended to the structure section of the user prompt:

> "Delivery style: [delivery]. Apply these cues throughout the script so the text reads naturally when converted to audio."

No changes to `tts_generate.py` — delivery hints shape the written text, not TTS API calls.

## Integration into SKILL.md native path

The native generation path in `script-generate/SKILL.md` is updated to also read the `soul` field from the config and apply the same persona + delivery logic when Claude generates the script natively (no API key path).

## What changes

| File | Change |
|---|---|
| `plugins/media/src/script_generate.py` | Add `resolve_soul()`, update `build_system_prompt()` and `build_user_prompt()` to accept soul |
| `plugins/media/skills/script-generate/SKILL.md` | Update native path to apply soul from config |
| `plugins/media/configs/prod-grade-ai-podcast.json` | Add inline `soul` to demonstrate the feature |
| `plugins/media/souls/` | New directory for reusable soul files (initially empty) |
| `plugins/media/plugin.json` | Bump version to `1.2.0` |
| `docs/usage.md` (new) | Full usage guide covering soul configuration: schema reference, inline vs file, valid values, examples |
| `README.md` | Add link to `docs/usage.md` under a "Documentation" section |

## What does NOT change

- `tts_generate.py`
- `spotify_publish.py`
- `news_fetch.py`
- `podcast-daily` skill
- `ai-ml-podcast.json` (no soul → default behavior)

## Success criteria

- A show with a `soul` defined produces a script written in the configured persona and style
- Delivery cues from the speaker soul appear naturally in the script text
- A show without a `soul` field behaves exactly as before
- Soul files in `plugins/media/souls/` can be referenced by path from any config
- `docs/usage.md` covers the full soul schema with examples
- `README.md` links to `docs/usage.md`
