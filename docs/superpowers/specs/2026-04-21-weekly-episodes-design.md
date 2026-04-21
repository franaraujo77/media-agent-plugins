# Weekly Episodes Design

**Date:** 2026-04-21

## Overview

Change the podcast pipeline from daily to weekly episodes. News fetch filters to stories published within a configurable lookback window. Script generation targets a longer word count. TTS handles scripts that exceed the API's per-request character limit by chunking and stitching audio.

## Config

Add `lookback_days` to each podcast config:

```json
"lookback_days": 7
```

Absence of the field means no date filter is applied (backward-compatible). The `ai-ml-podcast.json` config can remain unchanged until weekly cadence is desired.

## News Fetch (`news_fetch.py`)

Add a `filter_by_lookback(items, lookback_days)` function that runs after all sources are collected and before deduplication.

- Parses each item's `published` field using `dateutil.parser.parse` (tolerant of varied RSS date formats).
- Drops items older than `lookback_days` days from now.
- Items that fail date parsing are kept (fail-open).
- Scraped items always have `published = datetime.now()` (set by the scraper), so they always pass the filter — this is an accepted limitation.
- Prints: `"Filtered 4 items older than 7 days (32 kept)"` when a lookback is configured.

**New dependency:** `python-dateutil` added to `requirements.txt`.

## Script Generation (`script_generate.py`)

Change the word target in `build_user_prompt` from `450-750 words` to `450-4000 words`. No other changes.

## TTS (`tts_generate.py`)

Replace the hard truncation at 4096 chars with chunked generation and stitching.

1. **Split** the script into chunks of ≤4096 chars, breaking at sentence boundaries (`. ` before a capital letter) to avoid cutting mid-sentence. If no sentence boundary is found within a chunk, fall back to the 4096-char hard cut.
2. **Generate** one MP3 per chunk via the OpenAI TTS API.
3. **Stitch** by concatenating raw MP3 bytes into `output/episode.mp3`. MP3 frames are self-contained so raw byte concatenation works across players without additional dependencies.
4. **Clean up** temp chunk files from `output/chunks/` after stitching.

No new dependencies required.

## Error Handling

- Unchanged from current behavior: each source fetch is wrapped in try/except; a failing source does not abort the pipeline.
- TTS chunk failures propagate as exceptions (no partial audio output).

## Testing

- `test_news_fetch.py`: add tests for `filter_by_lookback` — items within window kept, items outside dropped, unparseable dates kept, scrape items (with now-dates) always kept.
- `test_tts_generate.py`: add tests for the chunking logic — single chunk passthrough, multi-chunk split at sentence boundary, fallback to hard cut when no boundary found.
- All external APIs (Anthropic, OpenAI, Playwright) remain mocked.

## Files Changed

| File | Change |
|---|---|
| `plugins/media/configs/prod-grade-ai-podcast.json` | Add `lookback_days: 7` |
| `plugins/media/src/news_fetch.py` | Add `filter_by_lookback`, call it in `run` |
| `plugins/media/src/script_generate.py` | Update word target to `450-4000` |
| `plugins/media/src/tts_generate.py` | Replace truncation with chunk/stitch |
| `plugins/media/requirements.txt` | Add `python-dateutil` |
| `tests/test_news_fetch.py` | New tests for `filter_by_lookback` |
| `tests/test_tts_generate.py` | New tests for chunking logic |
