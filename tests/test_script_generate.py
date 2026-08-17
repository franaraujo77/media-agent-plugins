import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from plugins.media.src.script_generate import (
    build_user_prompt,
    generate_script,
    run,
    resolve_soul,
    build_system_prompt,
    load_api_key,
    NO_API_KEY_EXIT,
)


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
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
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


def test_load_api_key_prefers_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=from-file")
    assert load_api_key(env_file) == "from-env"


def test_load_api_key_falls_back_to_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=from-file")
    assert load_api_key(env_file) == "from-file"


def test_load_api_key_ignores_comments_and_other_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# ANTHROPIC_API_KEY=commented-out\n"
        "OPENAI_API_KEY=other\n"
        "\n"
        "export ANTHROPIC_API_KEY=\"quoted-value\"\n"
    )
    assert load_api_key(env_file) == "quoted-value"


def test_load_api_key_returns_none_when_env_file_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert load_api_key(tmp_path / "nonexistent.env") is None


def test_load_api_key_ignores_blank_environment_value(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=from-file")
    assert load_api_key(env_file) == "from-file"


def test_run_exits_with_no_api_key_code_when_key_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("plugins.media.src.script_generate.ENV_FILE", tmp_path / "absent.env")

    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"podcast": {"name": "AI Daily", "description": "AI news"}}))
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "news-items.json").write_text(json.dumps(NEWS_ITEMS))
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as exc:
        run(str(config_file))

    assert exc.value.code == NO_API_KEY_EXIT


def test_run_passes_loaded_key_to_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "key-123")

    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({"podcast": {"name": "AI Daily", "description": "AI news"}}))
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

    assert mock_cls.call_args.kwargs["api_key"] == "key-123"


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


def test_resolve_soul_loads_markdown_as_system_prompt(tmp_path):
    soul_file = tmp_path / "soul.md"
    soul_file.write_text("# Soul\n\nA no-nonsense engineer.")
    config = {"soul": str(soul_file)}
    assert resolve_soul(config) == {"_system_prompt": "# Soul\n\nA no-nonsense engineer."}


def test_resolve_soul_loads_markdown_regardless_of_suffix_case(tmp_path):
    soul_file = tmp_path / "SOUL.MD"
    soul_file.write_text("Upper case suffix.")
    config = {"soul": str(soul_file)}
    assert resolve_soul(config) == {"_system_prompt": "Upper case suffix."}


def test_resolve_soul_loads_markdown_with_long_suffix(tmp_path):
    soul_file = tmp_path / "soul.markdown"
    soul_file.write_text("Long suffix.")
    config = {"soul": str(soul_file)}
    assert resolve_soul(config) == {"_system_prompt": "Long suffix."}


def test_resolve_soul_exits_on_invalid_json(tmp_path):
    soul_file = tmp_path / "soul.json"
    soul_file.write_text("{not json")
    config = {"soul": str(soul_file)}
    with pytest.raises(SystemExit):
        resolve_soul(config)


def test_resolve_soul_exits_on_missing_file(tmp_path):
    config = {"soul": str(tmp_path / "nonexistent.json")}
    with pytest.raises(SystemExit):
        resolve_soul(config)


def test_build_system_prompt_default_when_no_soul():
    prompt = build_system_prompt(None)
    assert "professional podcast host" in prompt


def test_build_system_prompt_passes_markdown_soul_through_verbatim():
    soul = {"_system_prompt": "# Soul\n\nA no-nonsense engineer."}
    assert build_system_prompt(soul) == "# Soul\n\nA no-nonsense engineer."


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
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
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


def test_build_user_prompt_targets_450_to_4000_words():
    prompt = build_user_prompt("My Podcast", "A description.", "April 21, 2026", [], soul=None)
    assert "450-4000 words" in prompt
    assert "450-750 words" not in prompt
