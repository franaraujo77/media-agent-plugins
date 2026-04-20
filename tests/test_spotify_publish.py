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
