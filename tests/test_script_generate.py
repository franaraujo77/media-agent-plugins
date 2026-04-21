import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from plugins.media.src.script_generate import build_user_prompt, generate_script, run, resolve_soul, build_system_prompt


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


def test_resolve_soul_exits_on_missing_file(tmp_path):
    config = {"soul": str(tmp_path / "nonexistent.json")}
    with pytest.raises(SystemExit):
        resolve_soul(config)


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
