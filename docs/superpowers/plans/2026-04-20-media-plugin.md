# Media Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish the `media` Claude Code plugin — five skills that fetch news, generate a podcast script via Claude, convert it to audio via OpenAI TTS, and publish the episode to Spotify for Creators via Playwright.

**Architecture:** Each skill is a SKILL.md instruction file paired with a Python implementation script. Skills communicate via files in `output/`. A JSON config file per podcast drives all five skills, making it trivial to add a new show without touching code.

**Tech Stack:** Python 3.11+, feedparser, Playwright (Chromium), Anthropic SDK (claude-sonnet-4-6), OpenAI SDK (tts-1-hd), pytest

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `.gitignore` | Ignore `output/` and Python artifacts |
| Create | `marketplace.json` | Plugin registry for the repo |
| Create | `plugins/__init__.py` | Makes `plugins` a Python package (for test imports) |
| Create | `plugins/media/__init__.py` | Makes `plugins.media` a Python package |
| Create | `plugins/media/src/__init__.py` | Makes `plugins.media.src` a Python package |
| Create | `plugins/media/plugin.json` | Plugin manifest |
| Create | `plugins/media/requirements.txt` | Python dependencies |
| Create | `plugins/media/configs/ai-ml-podcast.json` | Example config |
| Create | `tests/__init__.py` | Makes `tests` a Python package |
| Create | `conftest.py` | Adds repo root to `sys.path` for test imports |
| Create | `plugins/media/src/news_fetch.py` | Fetch + deduplicate news from RSS/scrape |
| Create | `plugins/media/skills/news-fetch/SKILL.md` | Skill instruction |
| Create | `tests/test_news_fetch.py` | Unit tests for news_fetch |
| Create | `plugins/media/src/script_generate.py` | Generate podcast script via Claude API |
| Create | `plugins/media/skills/script-generate/SKILL.md` | Skill instruction |
| Create | `tests/test_script_generate.py` | Unit tests for script_generate |
| Create | `plugins/media/src/tts_generate.py` | Convert script to audio via OpenAI TTS |
| Create | `plugins/media/skills/tts-generate/SKILL.md` | Skill instruction |
| Create | `tests/test_tts_generate.py` | Unit tests for tts_generate |
| Create | `plugins/media/src/spotify_publish.py` | Publish episode to Spotify for Creators |
| Create | `plugins/media/skills/spotify-publish/SKILL.md` | Skill instruction |
| Create | `tests/test_spotify_publish.py` | Unit tests for spotify_publish |
| Create | `plugins/media/skills/podcast-daily/SKILL.md` | Orchestrator skill |

---

## Task 1: Repo Scaffold

**Files:**
- Create: `.gitignore`
- Create: `marketplace.json`
- Create: `plugins/__init__.py`
- Create: `plugins/media/__init__.py`
- Create: `plugins/media/src/__init__.py`
- Create: `plugins/media/plugin.json`
- Create: `plugins/media/requirements.txt`
- Create: `plugins/media/configs/ai-ml-podcast.json`
- Create: `tests/__init__.py`
- Create: `conftest.py`

- [ ] **Step 1: Create `.gitignore`**

```
output/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
.env
```

- [ ] **Step 2: Create `marketplace.json`**

```json
{
  "name": "francisaraujo-marketplace",
  "plugins": [
    {
      "name": "media",
      "description": "Skills for producing and publishing AI-generated podcast episodes.",
      "source": {
        "type": "github",
        "repo": "francisaraujo/ai-agent-plugins",
        "ref": "main"
      }
    }
  ]
}
```

- [ ] **Step 3: Create `plugins/media/plugin.json`**

```json
{
  "name": "media",
  "version": "1.0.0",
  "description": "Produce and publish AI-generated podcast episodes from configurable news sources.",
  "skills": [
    "./skills/news-fetch",
    "./skills/script-generate",
    "./skills/tts-generate",
    "./skills/spotify-publish",
    "./skills/podcast-daily"
  ]
}
```

- [ ] **Step 4: Create `plugins/media/requirements.txt`**

```
feedparser==6.0.11
openai>=1.0.0
anthropic>=0.40.0
playwright>=1.40.0
pytest>=8.0.0
pytest-mock>=3.12.0
```

- [ ] **Step 5: Create `plugins/media/configs/ai-ml-podcast.json`**

```json
{
  "podcast": {
    "name": "AI/ML Daily",
    "description": "Daily digest of the latest AI and ML news",
    "episode_title_template": "AI/ML Daily — {date}",
    "language": "en"
  },
  "sources": [
    { "type": "rss", "url": "https://arxiv.org/rss/cs.AI", "label": "ArXiv AI", "max_items": 5 },
    { "type": "rss", "url": "https://www.deepmind.com/blog/rss.xml", "label": "DeepMind Blog", "max_items": 3 },
    { "type": "scrape", "url": "https://huggingface.co/blog", "label": "HuggingFace Blog", "max_items": 3 }
  ],
  "tts": {
    "voice": "alloy",
    "model": "tts-1-hd"
  },
  "spotify": {
    "show_id": "<your-show-id>",
    "credentials_env": "SPOTIFY_EMAIL,SPOTIFY_PASSWORD"
  }
}
```

- [ ] **Step 6: Create empty `__init__.py` files**

Create empty files at:
- `plugins/__init__.py`
- `plugins/media/__init__.py`
- `plugins/media/src/__init__.py`
- `tests/__init__.py`

- [ ] **Step 7: Create `conftest.py`**

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
```

- [ ] **Step 8: Install dependencies**

```bash
pip install -r plugins/media/requirements.txt
playwright install chromium
```

Expected: all packages installed without errors.

- [ ] **Step 9: Commit**

```bash
git add .gitignore marketplace.json plugins/ tests/__init__.py conftest.py
git commit -m "feat: scaffold media plugin repo structure"
```

---

## Task 2: news-fetch

**Files:**
- Create: `plugins/media/src/news_fetch.py`
- Create: `plugins/media/skills/news-fetch/SKILL.md`
- Create: `tests/test_news_fetch.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_news_fetch.py`:

```python
import json
import pytest
from unittest.mock import MagicMock, patch
from plugins.media.src.news_fetch import fetch_rss, deduplicate, run


def _mock_feed(entries_data: list[dict]):
    """Build a mock feedparser feed from a list of entry dicts."""
    mock_feed = MagicMock()
    mock_feed.entries = [dict(e) for e in entries_data]
    return mock_feed


def test_fetch_rss_returns_structured_items():
    feed = _mock_feed([
        {"title": "Test Article", "summary": "A summary.", "link": "https://example.com/1", "published": "2026-04-20"},
    ])
    with patch("plugins.media.src.news_fetch.feedparser") as mock_fp:
        mock_fp.parse.return_value = feed
        items = fetch_rss("https://example.com/rss", "Test Source", 5)

    assert len(items) == 1
    assert items[0]["title"] == "Test Article"
    assert items[0]["summary"] == "A summary."
    assert items[0]["url"] == "https://example.com/1"
    assert items[0]["source"] == "Test Source"
    assert items[0]["published"] == "2026-04-20"


def test_fetch_rss_respects_max_items():
    entries = [
        {"title": f"Article {i}", "summary": "", "link": f"https://example.com/{i}", "published": "2026-04-20"}
        for i in range(10)
    ]
    feed = _mock_feed(entries)
    with patch("plugins.media.src.news_fetch.feedparser") as mock_fp:
        mock_fp.parse.return_value = feed
        items = fetch_rss("https://example.com/rss", "Source", 3)

    assert len(items) == 3


def test_fetch_rss_falls_back_when_published_missing():
    feed = _mock_feed([{"title": "No Date", "summary": "", "link": "https://example.com/1"}])
    with patch("plugins.media.src.news_fetch.feedparser") as mock_fp:
        mock_fp.parse.return_value = feed
        items = fetch_rss("https://example.com/rss", "Source", 5)

    assert items[0]["published"] != ""


def test_deduplicate_removes_duplicate_urls():
    items = [
        {"url": "https://a.com", "title": "A"},
        {"url": "https://b.com", "title": "B"},
        {"url": "https://a.com", "title": "A again"},
    ]
    result = deduplicate(items)
    assert len(result) == 2
    assert result[0]["url"] == "https://a.com"
    assert result[1]["url"] == "https://b.com"


def test_deduplicate_preserves_order():
    items = [
        {"url": "https://c.com", "title": "C"},
        {"url": "https://a.com", "title": "A"},
        {"url": "https://b.com", "title": "B"},
    ]
    result = deduplicate(items)
    assert [i["url"] for i in result] == ["https://c.com", "https://a.com", "https://b.com"]


def test_run_writes_output_file(tmp_path, monkeypatch):
    config = {
        "sources": [
            {"type": "rss", "url": "https://example.com/rss", "label": "Test", "max_items": 2}
        ]
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))
    monkeypatch.chdir(tmp_path)

    feed = _mock_feed([
        {"title": "Article", "summary": "Summary", "link": "https://example.com/1", "published": "2026-04-20"},
    ])
    with patch("plugins.media.src.news_fetch.feedparser") as mock_fp:
        mock_fp.parse.return_value = feed
        run(str(config_file))

    output = json.loads((tmp_path / "output" / "news-items.json").read_text())
    assert len(output) == 1
    assert output[0]["title"] == "Article"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_news_fetch.py -v
```

Expected: `ModuleNotFoundError: No module named 'plugins.media.src.news_fetch'`

- [ ] **Step 3: Implement `plugins/media/src/news_fetch.py`**

```python
import feedparser
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin


def fetch_rss(url: str, label: str, max_items: int) -> list[dict]:
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_items]:
        items.append({
            "title": entry.get("title", ""),
            "summary": entry.get("summary", ""),
            "url": entry.get("link", ""),
            "source": label,
            "published": entry.get("published", datetime.now().isoformat()),
        })
    return items


def fetch_scrape(url: str, label: str, max_items: int) -> list[dict]:
    from playwright.sync_api import sync_playwright

    items = []
    seen: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        anchors = page.query_selector_all("article a, h2 a, h3 a, .post-title a")
        for anchor in anchors:
            href = anchor.get_attribute("href") or ""
            title = anchor.inner_text().strip()
            if not href or not title or href in seen:
                continue
            if not href.startswith("http"):
                href = urljoin(url, href)
            items.append({
                "title": title,
                "summary": "",
                "url": href,
                "source": label,
                "published": datetime.now().isoformat(),
            })
            seen.add(href)
            if len(items) >= max_items:
                break
        browser.close()
    return items


def deduplicate(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result = []
    for item in items:
        if item["url"] not in seen:
            result.append(item)
            seen.add(item["url"])
    return result


def run(config_path: str) -> None:
    config = json.loads(Path(config_path).read_text())
    all_items: list[dict] = []
    for source in config["sources"]:
        max_items = source.get("max_items", 5)
        if source["type"] == "rss":
            all_items.extend(fetch_rss(source["url"], source["label"], max_items))
        elif source["type"] == "scrape":
            all_items.extend(fetch_scrape(source["url"], source["label"], max_items))
        else:
            print(f"Unknown source type: {source['type']}", file=sys.stderr)

    unique = deduplicate(all_items)
    output = Path("output/news-items.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(unique, indent=2))
    print(f"Fetched {len(unique)} news items → output/news-items.json")


if __name__ == "__main__":
    run(sys.argv[1])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_news_fetch.py -v
```

Expected: 6 tests pass, 0 failures.

- [ ] **Step 5: Create `plugins/media/skills/news-fetch/SKILL.md`**

```markdown
---
name: news-fetch
description: Fetch and deduplicate news items from RSS feeds and web pages for a configured podcast. Writes output/news-items.json. Run before script-generate.
argument-hint: <path-to-config.json>
allowed-tools: Bash(python3 *)
---

# news-fetch

Fetch today's news items for the podcast defined in the config file provided as the argument.

## Steps

1. Run the news fetch script with the config path argument:

   ```bash
   python3 plugins/media/src/news_fetch.py <argument>
   ```

2. Report how many items were fetched and confirm `output/news-items.json` was written.
   If the script errors, report the full error message.
```

- [ ] **Step 6: Commit**

```bash
git add plugins/media/src/news_fetch.py plugins/media/skills/news-fetch/ tests/test_news_fetch.py
git commit -m "feat: add news-fetch skill with RSS and scrape support"
```

---

## Task 3: script-generate

**Files:**
- Create: `plugins/media/src/script_generate.py`
- Create: `plugins/media/skills/script-generate/SKILL.md`
- Create: `tests/test_script_generate.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_script_generate.py`:

```python
import json
import pytest
from unittest.mock import MagicMock, patch
from plugins.media.src.script_generate import build_user_prompt, generate_script, run


NEWS_ITEMS = [
    {"title": "AI Breakthrough", "source": "ArXiv", "summary": "Researchers achieve AGI.", "url": "https://arxiv.org/1"},
    {"title": "New LLM Released", "source": "HuggingFace", "summary": "A new model drops.", "url": "https://hf.co/blog/1"},
]


def test_build_user_prompt_includes_podcast_name():
    prompt = build_user_prompt("AI Daily", "AI news show", "April 20, 2026", NEWS_ITEMS)
    assert "AI Daily" in prompt


def test_build_user_prompt_includes_all_news_titles():
    prompt = build_user_prompt("AI Daily", "AI news show", "April 20, 2026", NEWS_ITEMS)
    assert "AI Breakthrough" in prompt
    assert "New LLM Released" in prompt


def test_build_user_prompt_includes_date():
    prompt = build_user_prompt("AI Daily", "AI news show", "April 20, 2026", NEWS_ITEMS)
    assert "April 20, 2026" in prompt


def test_generate_script_calls_claude_and_returns_text():
    mock_content = MagicMock()
    mock_content.text = "Welcome to AI Daily. Today is April 20, 2026."
    mock_response = MagicMock()
    mock_response.content = [mock_content]

    with patch("plugins.media.src.script_generate.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_cls.return_value = mock_client

        result = generate_script("AI Daily", "AI news", "April 20, 2026", NEWS_ITEMS)

    assert result == "Welcome to AI Daily. Today is April 20, 2026."
    mock_client.messages.create.assert_called_once()


def test_generate_script_uses_sonnet_model():
    mock_content = MagicMock()
    mock_content.text = "Script."
    mock_response = MagicMock()
    mock_response.content = [mock_content]

    with patch("plugins.media.src.script_generate.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_cls.return_value = mock_client

        generate_script("AI Daily", "AI news", "April 20, 2026", NEWS_ITEMS)

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-6"


def test_run_writes_script_file(tmp_path, monkeypatch):
    config = {
        "podcast": {
            "name": "AI Daily",
            "description": "AI news",
            "episode_title_template": "AI Daily — {date}",
            "language": "en",
        }
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "news-items.json").write_text(json.dumps(NEWS_ITEMS))
    monkeypatch.chdir(tmp_path)

    mock_content = MagicMock()
    mock_content.text = "Hello podcast world."
    mock_response = MagicMock()
    mock_response.content = [mock_content]

    with patch("plugins.media.src.script_generate.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_cls.return_value = mock_client
        run(str(config_file))

    assert (tmp_path / "output" / "script.txt").read_text() == "Hello podcast world."
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_script_generate.py -v
```

Expected: `ModuleNotFoundError: No module named 'plugins.media.src.script_generate'`

- [ ] **Step 3: Implement `plugins/media/src/script_generate.py`**

```python
import anthropic
import json
import sys
from datetime import date
from pathlib import Path

SYSTEM_PROMPT = (
    "You are a professional podcast host writing scripts for a daily news podcast. "
    "Your style is conversational, engaging, and concise. "
    "You summarize complex topics in plain language suitable for general audiences."
)


def build_user_prompt(
    podcast_name: str, description: str, today: str, news_items: list[dict]
) -> str:
    news_text = "\n\n".join(
        f"**{item['title']}** ({item['source']})\n{item['summary']}"
        for item in news_items
    )
    return f"""Write a podcast script for "{podcast_name}" — {description}.

Today's date: {today}

News items:
{news_text}

Structure:
- Brief intro (2-3 sentences, welcome listeners, mention the date)
- One segment per news item (2-3 sentences each, conversational tone, no URLs)
- Brief closing (1-2 sentences)

Target: 450-750 words. Write only the spoken script — no labels, no stage directions."""


def generate_script(
    podcast_name: str, description: str, today: str, news_items: list[dict]
) -> str:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": build_user_prompt(podcast_name, description, today, news_items),
            }
        ],
    )
    return response.content[0].text


def run(config_path: str) -> None:
    config = json.loads(Path(config_path).read_text())
    podcast = config["podcast"]
    news_items = json.loads(Path("output/news-items.json").read_text())
    today = date.today().strftime("%B %d, %Y")

    script = generate_script(podcast["name"], podcast["description"], today, news_items)

    Path("output/script.txt").write_text(script)
    print(f"Generated script ({len(script.split())} words) → output/script.txt")


if __name__ == "__main__":
    run(sys.argv[1])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_script_generate.py -v
```

Expected: 6 tests pass, 0 failures.

- [ ] **Step 5: Create `plugins/media/skills/script-generate/SKILL.md`**

```markdown
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
```

- [ ] **Step 6: Commit**

```bash
git add plugins/media/src/script_generate.py plugins/media/skills/script-generate/ tests/test_script_generate.py
git commit -m "feat: add script-generate skill using Claude API with prompt caching"
```

---

## Task 4: tts-generate

**Files:**
- Create: `plugins/media/src/tts_generate.py`
- Create: `plugins/media/skills/tts-generate/SKILL.md`
- Create: `tests/test_tts_generate.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tts_generate.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from plugins.media.src.tts_generate import generate_audio, run, MAX_TTS_CHARS


def test_generate_audio_calls_openai_with_correct_params(tmp_path):
    output_path = tmp_path / "episode.mp3"
    mock_response = MagicMock()

    with patch("plugins.media.src.tts_generate.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response
        mock_cls.return_value = mock_client

        generate_audio("Hello world.", "alloy", "tts-1-hd", output_path)

    mock_client.audio.speech.create.assert_called_once_with(
        model="tts-1-hd",
        voice="alloy",
        input="Hello world.",
    )
    mock_response.stream_to_file.assert_called_once_with(str(output_path))


def test_generate_audio_truncates_script_over_limit(tmp_path):
    long_script = "x" * (MAX_TTS_CHARS + 500)
    output_path = tmp_path / "episode.mp3"

    with patch("plugins.media.src.tts_generate.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = MagicMock()
        mock_cls.return_value = mock_client

        generate_audio(long_script, "alloy", "tts-1-hd", output_path)

    called_input = mock_client.audio.speech.create.call_args.kwargs["input"]
    assert len(called_input) == MAX_TTS_CHARS


def test_generate_audio_does_not_truncate_short_script(tmp_path):
    script = "Short script."
    output_path = tmp_path / "episode.mp3"

    with patch("plugins.media.src.tts_generate.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = MagicMock()
        mock_cls.return_value = mock_client

        generate_audio(script, "nova", "tts-1", output_path)

    called_input = mock_client.audio.speech.create.call_args.kwargs["input"]
    assert called_input == "Short script."


def test_run_reads_config_and_writes_audio(tmp_path, monkeypatch):
    config = {"tts": {"voice": "nova", "model": "tts-1"}}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "script.txt").write_text("Hello podcast.")
    monkeypatch.chdir(tmp_path)

    with patch("plugins.media.src.tts_generate.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = MagicMock()
        mock_cls.return_value = mock_client
        run(str(config_file))

    mock_client.audio.speech.create.assert_called_once_with(
        model="tts-1",
        voice="nova",
        input="Hello podcast.",
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_tts_generate.py -v
```

Expected: `ModuleNotFoundError: No module named 'plugins.media.src.tts_generate'`

- [ ] **Step 3: Implement `plugins/media/src/tts_generate.py`**

```python
import json
import sys
from pathlib import Path
from openai import OpenAI

MAX_TTS_CHARS = 4096


def generate_audio(script: str, voice: str, model: str, output_path: Path) -> None:
    if len(script) > MAX_TTS_CHARS:
        script = script[:MAX_TTS_CHARS]
    client = OpenAI()
    response = client.audio.speech.create(
        model=model,
        voice=voice,
        input=script,
    )
    response.stream_to_file(str(output_path))


def run(config_path: str) -> None:
    config = json.loads(Path(config_path).read_text())
    tts = config["tts"]
    script = Path("output/script.txt").read_text()
    output_path = Path("output/episode.mp3")
    generate_audio(script, tts["voice"], tts["model"], output_path)
    print("Generated audio → output/episode.mp3")


if __name__ == "__main__":
    run(sys.argv[1])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_tts_generate.py -v
```

Expected: 4 tests pass, 0 failures.

- [ ] **Step 5: Create `plugins/media/skills/tts-generate/SKILL.md`**

```markdown
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
```

- [ ] **Step 6: Commit**

```bash
git add plugins/media/src/tts_generate.py plugins/media/skills/tts-generate/ tests/test_tts_generate.py
git commit -m "feat: add tts-generate skill using OpenAI TTS with 4096-char guard"
```

---

## Task 5: spotify-publish

**Files:**
- Create: `plugins/media/src/spotify_publish.py`
- Create: `plugins/media/skills/spotify-publish/SKILL.md`
- Create: `tests/test_spotify_publish.py`

> **Note on Playwright selectors:** The selectors used in `publish()` are based on Spotify for Creators' current page structure using ARIA roles and labels, which is more stable than CSS selectors. After implementing, run the script once in headed mode (`headless=False`) to verify they match the live page and update as needed (see Step 6).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_spotify_publish.py`:

```python
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from plugins.media.src.spotify_publish import (
    render_episode_title,
    build_description,
    load_credentials,
    run,
)


def test_render_episode_title_replaces_date():
    result = render_episode_title("AI/ML Daily — {date}", "2026-04-20")
    assert result == "AI/ML Daily — 2026-04-20"


def test_render_episode_title_no_placeholder_unchanged():
    result = render_episode_title("Static Title", "2026-04-20")
    assert result == "Static Title"


def test_build_description_formats_items():
    items = [
        {"title": "Article 1", "source": "ArXiv", "url": "https://a.com", "summary": ""},
        {"title": "Article 2", "source": "HuggingFace", "url": "https://b.com", "summary": ""},
    ]
    result = build_description(items)
    assert result == "- Article 1 (ArXiv)\n- Article 2 (HuggingFace)"


def test_build_description_empty_list():
    assert build_description([]) == ""


def test_load_credentials_reads_env_vars(monkeypatch):
    monkeypatch.setenv("SPOTIFY_EMAIL", "test@example.com")
    monkeypatch.setenv("SPOTIFY_PASSWORD", "secret123")
    email, password = load_credentials("SPOTIFY_EMAIL,SPOTIFY_PASSWORD")
    assert email == "test@example.com"
    assert password == "secret123"


def test_load_credentials_strips_whitespace(monkeypatch):
    monkeypatch.setenv("MY_EMAIL", "user@example.com")
    monkeypatch.setenv("MY_PASS", "pass")
    email, password = load_credentials("MY_EMAIL , MY_PASS")
    assert email == "user@example.com"
    assert password == "pass"


def test_run_calls_publish_with_rendered_title(tmp_path, monkeypatch):
    config = {
        "podcast": {
            "name": "AI Daily",
            "description": "AI news",
            "episode_title_template": "AI Daily — {date}",
            "language": "en",
        },
        "spotify": {
            "show_id": "abc123",
            "credentials_env": "SPOTIFY_EMAIL,SPOTIFY_PASSWORD",
        },
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    news_items = [{"title": "Article", "source": "ArXiv", "url": "https://a.com", "summary": ""}]
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "news-items.json").write_text(json.dumps(news_items))
    (output_dir / "episode.mp3").write_bytes(b"fake-audio")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SPOTIFY_EMAIL", "test@example.com")
    monkeypatch.setenv("SPOTIFY_PASSWORD", "secret")

    with patch("plugins.media.src.spotify_publish.publish") as mock_publish:
        mock_publish.return_value = "https://creators.spotify.com/pod/show/abc123/episodes/ep1"
        run(str(config_file))

    call_kwargs = mock_publish.call_args
    assert call_kwargs.kwargs["show_id"] == "abc123"
    assert call_kwargs.kwargs["email"] == "test@example.com"
    assert "AI Daily" in call_kwargs.kwargs["episode_title"]
    assert "- Article (ArXiv)" in call_kwargs.kwargs["description"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_spotify_publish.py -v
```

Expected: `ModuleNotFoundError: No module named 'plugins.media.src.spotify_publish'`

- [ ] **Step 3: Implement `plugins/media/src/spotify_publish.py`**

```python
import json
import os
import sys
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright


def render_episode_title(template: str, date_str: str) -> str:
    return template.replace("{date}", date_str)


def build_description(news_items: list[dict]) -> str:
    return "\n".join(f"- {item['title']} ({item['source']})" for item in news_items)


def load_credentials(credentials_env: str) -> tuple[str, str]:
    parts = [v.strip() for v in credentials_env.split(",")]
    return os.environ[parts[0]], os.environ[parts[1]]


def publish(
    email: str,
    password: str,
    show_id: str,
    episode_title: str,
    description: str,
    audio_path: Path,
) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("https://creators.spotify.com/pod/login")
        page.get_by_label("Email address").fill(email)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Log In").click()
        page.wait_for_url("**/dashboard**", timeout=15000)

        page.goto(f"https://creators.spotify.com/pod/show/{show_id}/episodes/new")

        with page.expect_file_chooser() as fc_info:
            page.get_by_text("Select a file").click()
        fc_info.value.set_files(str(audio_path.resolve()))
        page.get_by_text("Upload complete").wait_for(timeout=120000)

        page.get_by_placeholder("Episode title").fill(episode_title)
        page.get_by_placeholder("What's this episode about?").fill(description)

        page.get_by_role("button", name="Publish Now").click()
        page.wait_for_url("**/episodes/**", timeout=30000)

        episode_url = page.url
        browser.close()
    return episode_url


def run(config_path: str) -> None:
    config = json.loads(Path(config_path).read_text())
    podcast = config["podcast"]
    spotify = config["spotify"]

    email, password = load_credentials(spotify["credentials_env"])
    today = date.today().strftime("%Y-%m-%d")
    episode_title = render_episode_title(podcast["episode_title_template"], today)

    news_items = json.loads(Path("output/news-items.json").read_text())
    description = build_description(news_items)
    audio_path = Path("output/episode.mp3")

    episode_url = publish(
        email=email,
        password=password,
        show_id=spotify["show_id"],
        episode_title=episode_title,
        description=description,
        audio_path=audio_path,
    )
    print(f"Published: {episode_title} → {episode_url}")


if __name__ == "__main__":
    run(sys.argv[1])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_spotify_publish.py -v
```

Expected: 7 tests pass, 0 failures.

- [ ] **Step 5: Create `plugins/media/skills/spotify-publish/SKILL.md`**

```markdown
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
```

- [ ] **Step 6: Verify Playwright selectors against the live Spotify for Creators page**

Temporarily set `headless=False` in `publish()` (line `p.chromium.launch(headless=True)` → `headless=False`), then run:

```bash
export SPOTIFY_EMAIL=your@email.com
export SPOTIFY_PASSWORD=yourpassword
python3 -c "
from plugins.media.src.spotify_publish import publish
from pathlib import Path
publish('$SPOTIFY_EMAIL', '$SPOTIFY_PASSWORD', '<your-show-id>', 'Test Episode', 'Test desc', Path('output/episode.mp3'))
"
```

Watch the browser and update any selector in `publish()` that doesn't match the live page. Common adjustments:
- Login button label: try `"Sign In"` or `"Continue"` if `"Log In"` doesn't work
- File upload trigger: inspect the upload area for the correct text or role
- Title/description fields: inspect placeholders or labels on the episode form

Revert `headless=False` → `headless=True` after verification.

- [ ] **Step 7: Commit**

```bash
git add plugins/media/src/spotify_publish.py plugins/media/skills/spotify-publish/ tests/test_spotify_publish.py
git commit -m "feat: add spotify-publish skill using Playwright browser automation"
```

---

## Task 6: podcast-daily Orchestrator

**Files:**
- Create: `plugins/media/skills/podcast-daily/SKILL.md`

No Python implementation needed — the orchestrator calls the existing scripts directly.

- [ ] **Step 1: Create `plugins/media/skills/podcast-daily/SKILL.md`**

```markdown
---
name: podcast-daily
description: Run the full podcast pipeline end-to-end — fetch news, generate script, create audio, publish to Spotify. Pass a config file as the argument. Calls all four media skills in sequence.
argument-hint: <path-to-config.json>
allowed-tools: Bash(python3 *), Bash(rm *)
---

# podcast-daily

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
```

- [ ] **Step 2: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass (17 tests across 4 test files), 0 failures.

- [ ] **Step 3: Commit**

```bash
git add plugins/media/skills/podcast-daily/
git commit -m "feat: add podcast-daily orchestrator skill"
```

---

## Task 7: Final Verification

- [ ] **Step 1: Validate plugin structure**

```bash
claude plugin validate plugins/media
```

Expected: no schema errors reported.

- [ ] **Step 2: Smoke-test news-fetch against live sources**

```bash
python3 plugins/media/src/news_fetch.py plugins/media/configs/ai-ml-podcast.json
cat output/news-items.json | python3 -m json.tool | head -40
```

Expected: JSON array of news items with title, summary, url, source, published fields.

- [ ] **Step 3: Commit and push**

```bash
git push -u origin main
```

- [ ] **Step 4: Add marketplace and install plugin**

```bash
claude plugin marketplace add francisaraujo/ai-agent-plugins
claude plugin install media@francisaraujo-marketplace
```

- [ ] **Step 5: Schedule daily run**

In a Claude Code session:

```
/schedule daily at 7am — run /media:podcast-daily plugins/media/configs/ai-ml-podcast.json
```
