# Weekly Episodes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `lookback_days` config field that filters news to recent stories, expand the script word target, and replace TTS hard-truncation with chunk/stitch so long scripts produce complete audio.

**Architecture:** Config-driven: `lookback_days` in the JSON config activates date filtering in `news_fetch.py`. Script prompt change is a one-liner. TTS gains a `split_into_chunks` helper; `generate_audio` uses it to produce and stitch multiple MP3 chunks for long scripts.

**Tech Stack:** Python 3.11+, `python-dateutil` (new), `openai`, `anthropic`, `feedparser`, `playwright`, `pytest`, `pytest-mock`

---

### Task 1: Add `filter_by_lookback` to news fetch

**Files:**
- Modify: `plugins/media/requirements.txt`
- Modify: `plugins/media/src/news_fetch.py`
- Modify: `tests/test_news_fetch.py`

- [ ] **Step 1: Write failing tests for `filter_by_lookback`**

Add to `tests/test_news_fetch.py`:

```python
from datetime import datetime, timedelta, timezone
from plugins.media.src.news_fetch import filter_by_lookback


def _item(title: str, published: str) -> dict:
    return {"title": title, "url": f"https://example.com/{title}", "published": published, "source": "X", "summary": ""}


def test_filter_keeps_items_within_window():
    now = datetime.now(timezone.utc)
    items = [
        _item("recent", now.isoformat()),
        _item("old", (now - timedelta(days=8)).isoformat()),
    ]
    kept, dropped = filter_by_lookback(items, 7)
    assert [i["title"] for i in kept] == ["recent"]
    assert dropped == 1


def test_filter_keeps_items_with_unparseable_date():
    items = [_item("x", "not-a-date")]
    kept, dropped = filter_by_lookback(items, 7)
    assert len(kept) == 1
    assert dropped == 0


def test_filter_drops_item_just_outside_window():
    now = datetime.now(timezone.utc)
    items = [_item("edge", (now - timedelta(days=7, hours=1)).isoformat())]
    kept, dropped = filter_by_lookback(items, 7)
    assert len(kept) == 0
    assert dropped == 1


def test_filter_handles_naive_datetime():
    # Naive datetimes (no timezone) should be treated as UTC
    now_naive = datetime.utcnow()
    items = [_item("naive", now_naive.isoformat())]
    kept, dropped = filter_by_lookback(items, 7)
    assert len(kept) == 1
    assert dropped == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_news_fetch.py::test_filter_keeps_items_within_window tests/test_news_fetch.py::test_filter_keeps_items_with_unparseable_date tests/test_news_fetch.py::test_filter_drops_item_just_outside_window tests/test_news_fetch.py::test_filter_handles_naive_datetime -v
```

Expected: ImportError or NameError — `filter_by_lookback` does not exist yet.

- [ ] **Step 3: Add `python-dateutil` to requirements**

In `plugins/media/requirements.txt`, add after the last line:

```
python-dateutil>=2.9.0
```

- [ ] **Step 4: Install the new dependency**

```bash
pip install python-dateutil
```

Expected: Successfully installed (or "already satisfied" — it is often a transitive dep).

- [ ] **Step 5: Implement `filter_by_lookback` in `news_fetch.py`**

Add after the `deduplicate` function (before `run`):

```python
def filter_by_lookback(items: list[dict], lookback_days: int) -> tuple[list[dict], int]:
    from dateutil import parser as dateutil_parser
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    kept = []
    dropped = 0
    for item in items:
        try:
            published = dateutil_parser.parse(item["published"])
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published >= cutoff:
                kept.append(item)
            else:
                dropped += 1
        except Exception:
            kept.append(item)
    return kept, dropped
```

Also update the imports at the top of `news_fetch.py` — add `timedelta` and `timezone` to the datetime import:

```python
from datetime import datetime, timedelta, timezone
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_news_fetch.py::test_filter_keeps_items_within_window tests/test_news_fetch.py::test_filter_keeps_items_with_unparseable_date tests/test_news_fetch.py::test_filter_drops_item_just_outside_window tests/test_news_fetch.py::test_filter_handles_naive_datetime -v
```

Expected: 4 PASSED.

- [ ] **Step 7: Write a failing integration test for `run()` with `lookback_days`**

Add to `tests/test_news_fetch.py`:

```python
def test_run_filters_by_lookback_days(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    import json
    from unittest.mock import patch
    from plugins.media.src.news_fetch import run

    now = datetime.now(timezone.utc)
    config = {
        "sources": [{"type": "rss", "url": "https://example.com/rss", "label": "Test", "max_items": 5}],
        "lookback_days": 3,
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    fresh_entry = {
        "title": "Fresh", "summary": "s", "link": "https://example.com/fresh",
        "published": now.isoformat(),
    }
    stale_entry = {
        "title": "Stale", "summary": "s", "link": "https://example.com/stale",
        "published": (now - timedelta(days=5)).isoformat(),
    }

    mock_feed = MagicMock()
    mock_feed.entries = [fresh_entry, stale_entry]

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.chdir(tmp_path)

    with patch("plugins.media.src.news_fetch.feedparser") as mock_fp:
        mock_fp.parse.return_value = mock_feed
        run(str(config_file))

    items = json.loads((output_dir / "news-items.json").read_text())
    assert len(items) == 1
    assert items[0]["title"] == "Fresh"
```

- [ ] **Step 8: Run test to verify it fails**

```bash
pytest tests/test_news_fetch.py::test_run_filters_by_lookback_days -v
```

Expected: FAIL — `run()` does not call `filter_by_lookback` yet.

- [ ] **Step 9: Integrate `filter_by_lookback` into `run()`**

In `news_fetch.py`, update the `run` function. Replace:

```python
    unique = deduplicate(all_items)
    output = Path("output/news-items.json")
```

With:

```python
    unique = deduplicate(all_items)
    lookback_days = config.get("lookback_days")
    if lookback_days:
        unique, dropped = filter_by_lookback(unique, lookback_days)
        print(f"Filtered {dropped} items older than {lookback_days} days ({len(unique)} kept)")
    output = Path("output/news-items.json")
```

- [ ] **Step 10: Run all news fetch tests**

```bash
pytest tests/test_news_fetch.py -v
```

Expected: all PASSED.

- [ ] **Step 11: Commit**

```bash
git add plugins/media/requirements.txt plugins/media/src/news_fetch.py tests/test_news_fetch.py
git commit -m "feat: add lookback_days date filter to news fetch"
```

---

### Task 2: Add `lookback_days` to prod config

**Files:**
- Modify: `plugins/media/configs/prod-grade-ai-podcast.json`

- [ ] **Step 1: Add `lookback_days` to the config**

In `plugins/media/configs/prod-grade-ai-podcast.json`, add `"lookback_days": 7` after the `"soul"` line:

```json
  "soul": "plugins/media/souls/influence.md",
  "lookback_days": 7,
```

- [ ] **Step 2: Commit**

```bash
git add plugins/media/configs/prod-grade-ai-podcast.json
git commit -m "chore: set lookback_days to 7 for prod-grade-ai podcast"
```

---

### Task 3: Expand script word target to 450–4000 words

**Files:**
- Modify: `plugins/media/src/script_generate.py`
- Modify: `tests/test_script_generate.py`

- [ ] **Step 1: Write a failing test for the new word target**

Open `tests/test_script_generate.py`. Find the test that checks `build_user_prompt` output (or add a new one). Add:

```python
from plugins.media.src.script_generate import build_user_prompt

def test_build_user_prompt_targets_450_to_4000_words():
    prompt = build_user_prompt("My Podcast", "A description.", "April 21, 2026", [], soul=None)
    assert "450-4000 words" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_script_generate.py::test_build_user_prompt_targets_450_to_4000_words -v
```

Expected: FAIL — prompt still says "450-750 words".

- [ ] **Step 3: Update the word target in `script_generate.py`**

In `plugins/media/src/script_generate.py`, in `build_user_prompt`, replace:

```python
Target: 450-750 words. Write only the spoken script — no labels, no stage directions.{delivery}"""
```

With:

```python
Target: 450-4000 words. Write only the spoken script — no labels, no stage directions.{delivery}"""
```

- [ ] **Step 4: Run all script generate tests**

```bash
pytest tests/test_script_generate.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add plugins/media/src/script_generate.py tests/test_script_generate.py
git commit -m "feat: expand script target to 450-4000 words for weekly episodes"
```

---

### Task 4: Replace TTS truncation with chunk/stitch

**Files:**
- Modify: `plugins/media/src/tts_generate.py`
- Modify: `tests/test_tts_generate.py`

- [ ] **Step 1: Write failing tests for `split_into_chunks`**

Add to `tests/test_tts_generate.py`:

```python
from plugins.media.src.tts_generate import split_into_chunks


def test_split_short_text_returns_single_chunk():
    assert split_into_chunks("Hello world.", max_chars=4096) == ["Hello world."]


def test_split_at_sentence_boundary():
    # 110 chars total: first sentence is 60 chars including ". ", second is 50
    first = "A" * 58 + ". "   # 60 chars
    second = "B" * 49 + "."    # 50 chars
    text = first + second       # 110 chars total
    chunks = split_into_chunks(text, max_chars=70)
    assert len(chunks) == 2
    assert chunks[0].endswith(".")
    assert chunks[1].startswith("B")


def test_split_falls_back_to_hard_cut_when_no_boundary():
    text = "a" * 200
    chunks = split_into_chunks(text, max_chars=100)
    assert len(chunks) == 2
    assert len(chunks[0]) == 100
    assert chunks[1] == "a" * 100


def test_split_text_exactly_at_limit_returns_single_chunk():
    text = "a" * 100
    assert split_into_chunks(text, max_chars=100) == [text]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tts_generate.py::test_split_short_text_returns_single_chunk tests/test_tts_generate.py::test_split_at_sentence_boundary tests/test_tts_generate.py::test_split_falls_back_to_hard_cut_when_no_boundary tests/test_tts_generate.py::test_split_text_exactly_at_limit_returns_single_chunk -v
```

Expected: ImportError — `split_into_chunks` does not exist yet.

- [ ] **Step 3: Implement `split_into_chunks` in `tts_generate.py`**

Add `import re` and `import shutil` to the imports at the top of `tts_generate.py`.

Add this function before `generate_audio`:

```python
def split_into_chunks(text: str, max_chars: int = MAX_TTS_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_chars:
            chunks.append(text)
            break
        segment = text[:max_chars]
        last_boundary = None
        for m in re.finditer(r'\. (?=[A-Z])', segment):
            last_boundary = m.start() + 1  # position just after the period
        if last_boundary:
            chunks.append(text[:last_boundary].strip())
            text = text[last_boundary:].strip()
        else:
            chunks.append(segment)
            text = text[max_chars:]
    return [c for c in chunks if c]
```

- [ ] **Step 4: Run split tests to verify they pass**

```bash
pytest tests/test_tts_generate.py::test_split_short_text_returns_single_chunk tests/test_tts_generate.py::test_split_at_sentence_boundary tests/test_tts_generate.py::test_split_falls_back_to_hard_cut_when_no_boundary tests/test_tts_generate.py::test_split_text_exactly_at_limit_returns_single_chunk -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Write failing test for multi-chunk `generate_audio`**

Add to `tests/test_tts_generate.py`:

```python
def test_generate_audio_stitches_multiple_chunks(tmp_path):
    # Two sentences separated by ". " — force split by setting max_chars low
    script = "First sentence. Second sentence."
    output_path = tmp_path / "episode.mp3"

    with patch("plugins.media.src.tts_generate.OpenAI") as mock_cls, \
         patch("plugins.media.src.tts_generate.split_into_chunks", return_value=["First sentence.", "Second sentence."]) as mock_split:
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = MagicMock()
        mock_cls.return_value = mock_client

        generate_audio(script, "alloy", "tts-1-hd", output_path)

    assert mock_client.audio.speech.create.call_count == 2
```

- [ ] **Step 6: Run test to verify it fails**

```bash
pytest tests/test_tts_generate.py::test_generate_audio_stitches_multiple_chunks -v
```

Expected: FAIL — `generate_audio` still truncates instead of splitting.

- [ ] **Step 7: Rewrite `generate_audio` in `tts_generate.py`**

Replace the entire `generate_audio` function with:

```python
def generate_audio(script: str, voice: str, model: str, output_path: Path) -> None:
    client = OpenAI()
    chunks = split_into_chunks(script)
    if len(chunks) == 1:
        response = client.audio.speech.create(model=model, voice=voice, input=chunks[0])
        response.stream_to_file(str(output_path))
        return
    chunks_dir = output_path.parent / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    chunk_paths = []
    try:
        for i, chunk in enumerate(chunks):
            chunk_path = chunks_dir / f"chunk_{i:03d}.mp3"
            response = client.audio.speech.create(model=model, voice=voice, input=chunk)
            response.stream_to_file(str(chunk_path))
            chunk_paths.append(chunk_path)
        with open(output_path, "wb") as outfile:
            for path in chunk_paths:
                outfile.write(path.read_bytes())
    finally:
        shutil.rmtree(chunks_dir, ignore_errors=True)
```

- [ ] **Step 8: Update the old truncation test**

In `tests/test_tts_generate.py`, replace `test_generate_audio_truncates_script_over_limit` with:

```python
def test_generate_audio_splits_long_script_into_chunks(tmp_path):
    # Script long enough to require splitting
    long_script = ("Hello world. " * 400).strip()  # ~5200 chars
    output_path = tmp_path / "episode.mp3"

    with patch("plugins.media.src.tts_generate.OpenAI") as mock_cls:
        mock_client = MagicMock()
        # stream_to_file must actually write bytes so stitching works
        def fake_stream(path):
            Path(path).write_bytes(b"mp3data")
        mock_client.audio.speech.create.return_value.stream_to_file.side_effect = fake_stream
        mock_cls.return_value = mock_client

        generate_audio(long_script, "alloy", "tts-1-hd", output_path)

    assert mock_client.audio.speech.create.call_count > 1
    assert output_path.exists()
    # Each call's input must be within the API limit
    for call in mock_client.audio.speech.create.call_args_list:
        assert len(call.kwargs["input"]) <= MAX_TTS_CHARS
```

- [ ] **Step 9: Run all TTS tests**

```bash
pytest tests/test_tts_generate.py -v
```

Expected: all PASSED. (`test_run_reads_config_and_writes_audio` still passes because it uses a short script that produces one chunk.)

- [ ] **Step 10: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all PASSED.

- [ ] **Step 11: Commit**

```bash
git add plugins/media/src/tts_generate.py tests/test_tts_generate.py
git commit -m "feat: replace TTS truncation with chunk/stitch for long scripts"
```
