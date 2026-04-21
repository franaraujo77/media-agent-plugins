# Soul Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional `soul` configuration to podcast configs that shapes how scripts are written (writer persona + style) and spoken (TTS delivery cues embedded in the script text).

**Architecture:** Soul is resolved from config (inline object or path to JSON file) before script generation. Writer soul replaces the system prompt; speaker soul appends delivery instructions to the user prompt. The SKILL.md native path mirrors the same logic. No changes to TTS, publish, or news-fetch.

**Tech Stack:** Python 3.14, `anthropic` SDK, `pytest` + `unittest.mock`, JSON config files.

---

### Task 1: Add `resolve_soul()` to script_generate.py

**Files:**
- Modify: `plugins/media/src/script_generate.py`
- Test: `tests/test_script_generate.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_script_generate.py`:

```python
import json
from pathlib import Path
from plugins.media.src.script_generate import resolve_soul


def test_resolve_soul_returns_none_when_absent():
    config = {"podcast": {"name": "Test"}}
    assert resolve_soul(config) is None


def test_resolve_soul_returns_inline_dict():
    soul = {"writer": {"persona": "a host"}}
    config = {"soul": soul}
    assert resolve_soul(config) == soul


def test_resolve_soul_loads_from_file(tmp_path):
    soul = {"writer": {"persona": "from file"}}
    soul_file = tmp_path / "soul.json"
    soul_file.write_text(json.dumps(soul))
    config = {"soul": str(soul_file)}
    assert resolve_soul(config) == soul
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_script_generate.py::test_resolve_soul_returns_none_when_absent tests/test_script_generate.py::test_resolve_soul_returns_inline_dict tests/test_script_generate.py::test_resolve_soul_loads_from_file -v
```

Expected: `ImportError` or `AttributeError` — `resolve_soul` not defined yet.

- [ ] **Step 3: Implement `resolve_soul()` in script_generate.py**

Add after the imports, before `SYSTEM_PROMPT`:

```python
def resolve_soul(config: dict) -> dict | None:
    soul = config.get("soul")
    if soul is None:
        return None
    if isinstance(soul, str):
        return json.loads(Path(soul).read_text())
    return soul
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_script_generate.py::test_resolve_soul_returns_none_when_absent tests/test_script_generate.py::test_resolve_soul_returns_inline_dict tests/test_script_generate.py::test_resolve_soul_loads_from_file -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/media/src/script_generate.py tests/test_script_generate.py
git commit -m "feat: add resolve_soul() to script_generate"
```

---

### Task 2: Add `build_system_prompt()` function

**Files:**
- Modify: `plugins/media/src/script_generate.py`
- Test: `tests/test_script_generate.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_script_generate.py`:

```python
from plugins.media.src.script_generate import build_system_prompt


def test_build_system_prompt_default_when_no_soul():
    prompt = build_system_prompt(None)
    assert "professional podcast host" in prompt


def test_build_system_prompt_uses_persona():
    soul = {"writer": {"persona": "a cynical engineer", "tone": "skeptical", "formality": "casual", "humor": "dry"}}
    prompt = build_system_prompt(soul)
    assert "a cynical engineer" in prompt


def test_build_system_prompt_uses_tone():
    soul = {"writer": {"persona": "a host", "tone": "skeptical", "formality": "casual", "humor": "dry"}}
    prompt = build_system_prompt(soul)
    assert "skeptical" in prompt


def test_build_system_prompt_uses_formality_and_humor():
    soul = {"writer": {"persona": "a host", "tone": "neutral", "formality": "professional", "humor": "light"}}
    prompt = build_system_prompt(soul)
    assert "professional" in prompt
    assert "light" in prompt
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_script_generate.py::test_build_system_prompt_default_when_no_soul tests/test_script_generate.py::test_build_system_prompt_uses_persona tests/test_script_generate.py::test_build_system_prompt_uses_tone tests/test_script_generate.py::test_build_system_prompt_uses_formality_and_humor -v
```

Expected: `ImportError` — `build_system_prompt` not defined yet.

- [ ] **Step 3: Add `build_system_prompt()` to script_generate.py**

Replace the `SYSTEM_PROMPT` constant with this function (keep the constant as the default string used inside):

```python
SYSTEM_PROMPT = (
    "You are a professional podcast host writing scripts for a daily news podcast. "
    "Your style is conversational, engaging, and concise. "
    "You summarize complex topics in plain language suitable for general audiences."
)


def build_system_prompt(soul: dict | None) -> str:
    if soul is None:
        return SYSTEM_PROMPT
    writer = soul.get("writer", {})
    persona = writer.get("persona", "a professional podcast host")
    tone = writer.get("tone", "neutral")
    formality = writer.get("formality", "mixed")
    humor = writer.get("humor", "none")
    return (
        f"You are {persona}. "
        f"Your tone is {tone}. "
        f"Your writing style is {formality}. "
        f"Your humor is {humor}. "
        "Write scripts that reflect this personality consistently."
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_script_generate.py::test_build_system_prompt_default_when_no_soul tests/test_script_generate.py::test_build_system_prompt_uses_persona tests/test_script_generate.py::test_build_system_prompt_uses_tone tests/test_script_generate.py::test_build_system_prompt_uses_formality_and_humor -v
```

Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/media/src/script_generate.py tests/test_script_generate.py
git commit -m "feat: add build_system_prompt() with soul support"
```

---

### Task 3: Update `build_user_prompt()` to accept soul

**Files:**
- Modify: `plugins/media/src/script_generate.py`
- Test: `tests/test_script_generate.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_script_generate.py`:

```python
def test_build_user_prompt_includes_delivery_when_soul_has_speaker():
    soul = {"speaker": {"delivery": "Pause after key points."}}
    prompt = build_user_prompt("Show", "desc", "April 21, 2026", NEWS_ITEMS, soul)
    assert "Pause after key points." in prompt


def test_build_user_prompt_no_delivery_section_when_no_soul():
    prompt = build_user_prompt("Show", "desc", "April 21, 2026", NEWS_ITEMS, None)
    assert "Delivery style" not in prompt


def test_build_user_prompt_no_delivery_section_when_soul_has_no_speaker():
    soul = {"writer": {"persona": "a host"}}
    prompt = build_user_prompt("Show", "desc", "April 21, 2026", NEWS_ITEMS, soul)
    assert "Delivery style" not in prompt
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_script_generate.py::test_build_user_prompt_includes_delivery_when_soul_has_speaker tests/test_script_generate.py::test_build_user_prompt_no_delivery_section_when_no_soul tests/test_script_generate.py::test_build_user_prompt_no_delivery_section_when_soul_has_no_speaker -v
```

Expected: `TypeError` — `build_user_prompt` doesn't accept a `soul` argument yet.

- [ ] **Step 3: Update `build_user_prompt()` signature and body**

Replace the existing `build_user_prompt` function:

```python
def build_user_prompt(
    podcast_name: str, description: str, today: str, news_items: list[dict], soul: dict | None = None
) -> str:
    news_text = "\n\n".join(
        f"**{item['title']}** ({item['source']})\n{item['summary']}"
        for item in news_items
    )
    delivery = ""
    if soul and soul.get("speaker", {}).get("delivery"):
        delivery = (
            f"\nDelivery style: {soul['speaker']['delivery']} "
            "Apply these cues throughout the script so the text reads naturally when converted to audio."
        )
    return f"""Write a podcast script for "{podcast_name}" — {description}.

Today's date: {today}

News items:
{news_text}

Structure:
- Brief intro (2-3 sentences, welcome listeners, mention the date)
- One segment per news item (2-3 sentences each, conversational tone, no URLs)
- Brief closing (1-2 sentences)

Target: 450-750 words. Write only the spoken script — no labels, no stage directions.{delivery}"""
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_script_generate.py -v
```

Expected: all tests PASS (including pre-existing ones).

- [ ] **Step 5: Commit**

```bash
git add plugins/media/src/script_generate.py tests/test_script_generate.py
git commit -m "feat: add soul delivery hints to build_user_prompt()"
```

---

### Task 4: Wire soul through `generate_script()` and `run()`

**Files:**
- Modify: `plugins/media/src/script_generate.py`
- Test: `tests/test_script_generate.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_script_generate.py`:

```python
def test_generate_script_uses_soul_system_prompt():
    soul = {"writer": {"persona": "a test host", "tone": "neutral", "formality": "casual", "humor": "none"}}
    mock_content = MagicMock()
    mock_content.text = "Script."
    mock_response = MagicMock()
    mock_response.content = [mock_content]

    with patch("plugins.media.src.script_generate.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_cls.return_value = mock_client
        generate_script("Show", "desc", "April 21, 2026", NEWS_ITEMS, soul)

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "a test host" in call_kwargs["system"][0]["text"]


def test_generate_script_uses_default_prompt_when_no_soul():
    mock_content = MagicMock()
    mock_content.text = "Script."
    mock_response = MagicMock()
    mock_response.content = [mock_content]

    with patch("plugins.media.src.script_generate.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_cls.return_value = mock_client
        generate_script("Show", "desc", "April 21, 2026", NEWS_ITEMS)

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "professional podcast host" in call_kwargs["system"][0]["text"]


def test_run_passes_soul_from_config(tmp_path, monkeypatch):
    soul = {"writer": {"persona": "a host", "tone": "neutral", "formality": "casual", "humor": "none"}}
    config = {
        "podcast": {"name": "AI Daily", "description": "AI news"},
        "soul": soul,
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "news-items.json").write_text(json.dumps(NEWS_ITEMS))
    monkeypatch.chdir(tmp_path)

    mock_content = MagicMock()
    mock_content.text = "Script."
    mock_response = MagicMock()
    mock_response.content = [mock_content]

    with patch("plugins.media.src.script_generate.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_cls.return_value = mock_client
        run(str(config_file))

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "a host" in call_kwargs["system"][0]["text"]
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_script_generate.py::test_generate_script_uses_soul_system_prompt tests/test_script_generate.py::test_generate_script_uses_default_prompt_when_no_soul tests/test_script_generate.py::test_run_passes_soul_from_config -v
```

Expected: FAIL — `generate_script` doesn't accept `soul` yet, `run` doesn't call `resolve_soul`.

- [ ] **Step 3: Update `generate_script()` and `run()`**

Replace `generate_script`:

```python
def generate_script(
    podcast_name: str, description: str, today: str, news_items: list[dict], soul: dict | None = None
) -> str:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": build_system_prompt(soul),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": build_user_prompt(podcast_name, description, today, news_items, soul),
            }
        ],
    )
    return response.content[0].text
```

Replace `run`:

```python
def run(config_path: str) -> None:
    news_path = Path("output/news-items.json")
    if not news_path.exists():
        sys.exit("Error: output/news-items.json not found. Run news-fetch first.")

    config = json.loads(Path(config_path).read_text())
    podcast = config["podcast"]
    news_items = json.loads(news_path.read_text())
    today = date.today().strftime("%B %d, %Y")
    soul = resolve_soul(config)

    script = generate_script(podcast["name"], podcast["description"], today, news_items, soul)

    Path("output").mkdir(exist_ok=True)
    Path("output/script.txt").write_text(script)
    print(f"Generated script ({len(script.split())} words) → output/script.txt")
```

- [ ] **Step 4: Run the full test suite**

```bash
pytest tests/test_script_generate.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add plugins/media/src/script_generate.py tests/test_script_generate.py
git commit -m "feat: wire soul through generate_script() and run()"
```

---

### Task 5: Update SKILL.md native path to apply soul

**Files:**
- Modify: `plugins/media/skills/script-generate/SKILL.md`

- [ ] **Step 1: Replace the native path section**

Replace the entire content of `plugins/media/skills/script-generate/SKILL.md` with:

```markdown
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
```

- [ ] **Step 2: Commit**

```bash
git add plugins/media/skills/script-generate/SKILL.md
git commit -m "feat: update script-generate native path to apply soul"
```

---

### Task 6: Add soul to prod-grade-ai-podcast.json + create souls/ directory

**Files:**
- Modify: `plugins/media/configs/prod-grade-ai-podcast.json`
- Create: `plugins/media/souls/.gitkeep`

- [ ] **Step 1: Add inline soul to prod-grade-ai-podcast.json**

Replace the content of `plugins/media/configs/prod-grade-ai-podcast.json` with:

```json
{
  "podcast": {
    "name": "Prod Grade AI",
    "description": "Stop the hype, check the benchmarks. Prod Grade AI is the news briefing for the engineers who have to actually build, ship, and scale the models the world is talking about. \nWe skip the VC fluff and dive into the market shifts that impact the tech stack: LLMOps, the war for GPU inference speeds, the reality of \"Agentic\" workflows, and why \"Open Source\" isn't as open as you think. If it isn't production-ready, it's just noise. We provide the signal.",
    "episode_title_template": "Prod Grade AI — {date}",
    "language": "en"
  },
  "soul": {
    "writer": {
      "persona": "A no-nonsense senior AI engineer who cuts through hype and focuses on what actually matters in production. You have shipped real AI systems and have zero patience for vague benchmarks or VC buzzwords.",
      "tone": "skeptical",
      "formality": "casual",
      "humor": "dry"
    },
    "speaker": {
      "delivery": "Use ellipses for natural pauses after punchy statements. Use em dashes for rhythm breaks mid-sentence. Capitalize individual words you want stressed — like ACTUALLY or REAL or SHIPPED. Keep sentences short and punchy. No exclamation marks."
    }
  },
  "sources": [
    { "type": "scrape", "url": "https://www.testingcatalog.com/", "label": "Reporting AI updates. A future news media, driven by virtual assistants", "max_items": 5 },
    { "type": "scrape", "url": "https://www.therundown.ai/", "label": "Get the latest AI news, understand why it matters, and learn how to apply it in your work. Join 2,000,000+ readers from companies like Apple, OpenAI, NASA.", "max_items": 5 },
    { "type": "scrape", "url": "https://developers.googleblog.com/search/?technology_categories=AI&content_type_categories=Announcements%2CBusiness+and+Leadership%2CCase+Studies%2CCode+Health%2CBest+Practices%2CIndustry+Trends%2CProblem-Solving%2CPerformance%2CSolutions", "label": "Google Developers Blog", "max_items": 5 },
    { "type": "scrape", "url": "https://claude.com/blog", "label": "Claude Code Blog", "max_items": 5 },
    { "type": "scrape", "url": "https://developers.openai.com/blog", "label": "OpenAi Blog", "max_items": 5 }
  ],
  "tts": {
    "voice": "cedar",
    "model": "gpt-4o-mini-tts"
  },
  "spotify": {
    "show_id": "1kJHbO3qrK2GW1PGATqwpK",
    "credentials_env": "SPOTIFY_EMAIL,SPOTIFY_PASSWORD"
  }
}
```

- [ ] **Step 2: Create the souls directory**

```bash
mkdir -p plugins/media/souls && touch plugins/media/souls/.gitkeep
```

- [ ] **Step 3: Run the full test suite to confirm nothing broke**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 4: Commit**

```bash
git add plugins/media/configs/prod-grade-ai-podcast.json plugins/media/souls/.gitkeep
git commit -m "feat: add soul to prod-grade-ai-podcast config and create souls/ directory"
```

---

### Task 7: Write docs/usage.md

**Files:**
- Create: `docs/usage.md`

- [ ] **Step 1: Create docs/usage.md**

Create `docs/usage.md` with this content:

```markdown
# Usage Guide

## Configuration

Each podcast is driven by a JSON config file. Pass the config path as the argument to any skill.

### Minimal config

```json
{
  "podcast": {
    "name": "My Podcast",
    "description": "A short description of what the show covers.",
    "episode_title_template": "My Podcast — {date}",
    "language": "en"
  },
  "sources": [
    { "type": "rss", "url": "https://example.com/feed.xml", "max_items": 5 },
    { "type": "scrape", "url": "https://example.com/news", "label": "Example News", "max_items": 5 }
  ],
  "tts": {
    "voice": "alloy",
    "model": "tts-1-hd"
  },
  "spotify": {
    "show_id": "YOUR_SHOW_ID",
    "credentials_env": "SPOTIFY_EMAIL,SPOTIFY_PASSWORD"
  }
}
```

## Soul configuration

`soul` is an optional field that controls how the script is written and how it should be spoken. Omitting it uses default behavior.

### Inline soul

Define the soul directly in the config:

```json
"soul": {
  "writer": {
    "persona": "A no-nonsense senior AI engineer who cuts through hype.",
    "tone": "skeptical",
    "formality": "casual",
    "humor": "dry"
  },
  "speaker": {
    "delivery": "Use ellipses for natural pauses. Capitalize words you want stressed. No exclamation marks."
  }
}
```

### Reusable soul file

Point to a shared soul file to reuse the same personality across multiple shows:

```json
"soul": "plugins/media/souls/cynical-engineer.json"
```

The soul file uses the same schema as the inline `soul` object.

### Writer soul fields

| Field | Type | Description | Valid values |
|---|---|---|---|
| `persona` | string | Free-form description of the host's personality | Any text |
| `tone` | string | Overall emotional register | `skeptical` `optimistic` `neutral` `measured` `excited` |
| `formality` | string | Language register | `casual` `professional` `mixed` |
| `humor` | string | Amount and style of humor | `none` `dry` `light` `heavy` |

### Speaker soul fields

| Field | Type | Description |
|---|---|---|
| `delivery` | string | Instructions for embedding TTS-friendly delivery cues in the script text (ellipses for pauses, em dashes for rhythm, capitalization for stress, etc.) |

### How it works

- **Writer soul** replaces the script-generation system prompt with one built from your persona and style knobs.
- **Speaker soul** appends delivery instructions to the user prompt, telling Claude to embed text-level cues (not SSML) that influence how OpenAI TTS renders the audio.
- Shows without a `soul` field behave exactly as before.

## Required environment variables

| Variable | Used by | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | `script-generate` | Claude API key. Optional — plan users generate natively via Claude Code. |
| `OPENAI_API_KEY` | `tts-generate` | OpenAI API key for TTS audio generation |
| `SPOTIFY_EMAIL` | `spotify-publish` | Spotify for Creators login email |
| `SPOTIFY_PASSWORD` | `spotify-publish` | Spotify for Creators login password |

Set these in `~/.claude/settings.json` under `env`:

```json
{
  "env": {
    "OPENAI_API_KEY": "sk-...",
    "SPOTIFY_EMAIL": "you@example.com",
    "SPOTIFY_PASSWORD": "yourpassword"
  }
}
```

## Running skills

```bash
/media:news-fetch plugins/media/configs/my-podcast.json
/media:script-generate plugins/media/configs/my-podcast.json
/media:tts-generate plugins/media/configs/my-podcast.json
/media:spotify-publish plugins/media/configs/my-podcast.json

# Or the full pipeline in one command:
/media:podcast-daily plugins/media/configs/my-podcast.json
```
```

- [ ] **Step 2: Commit**

```bash
git add docs/usage.md
git commit -m "docs: add usage guide with soul configuration reference"
```

---

### Task 8: Update README.md to link to docs/usage.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the Docs section in README.md**

Replace the existing `## Docs` section:

```markdown
## Docs

- [Installation guide](docs/superpowers/specs/2026-04-20-media-plugin-design.md#installation)
- [Usage](docs/superpowers/specs/2026-04-20-media-plugin-design.md#usage)
```

With:

```markdown
## Docs

- [Usage guide](docs/usage.md) — configuration reference, soul setup, environment variables
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README to link to usage guide"
```

---

### Task 9: Bump plugin version to 1.2.0 and push

**Files:**
- Modify: `plugins/media/plugin.json`

- [ ] **Step 1: Bump version**

In `plugins/media/plugin.json`, change `"version": "1.1.0"` to `"version": "1.2.0"`.

- [ ] **Step 2: Run full test suite one final time**

```bash
pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 3: Commit and push**

```bash
git add plugins/media/plugin.json
git commit -m "chore: bump plugin version to 1.2.0"
git push
```
