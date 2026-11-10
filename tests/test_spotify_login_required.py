"""The email-verification prompt stops the publish with a credential code. No browser is opened."""
import json
from unittest.mock import patch

import pytest

from plugins.media.src import spotify_publish as sp


class FakePage:
    """Stands in for a Playwright page."""

    def __init__(self, url="https://accounts.spotify.com/login", present=()):
        self.url = url
        self.present = set(present)
        self.waited = []

    def query_selector(self, selector):
        return object() if selector in self.present else None

    def wait_for_function(self, expression, timeout=None):
        self.waited.append(timeout)


def _config_files(tmp_path, monkeypatch):
    config = {
        "podcast": {"name": "AI Daily", "description": "x",
                    "episode_title_template": "AI Daily — {date}", "language": "en"},
        "spotify": {"show_id": "abc123", "credentials_env": "SPOTIFY_EMAIL,SPOTIFY_PASSWORD"},
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))
    (tmp_path / "output").mkdir()
    (tmp_path / "output" / "news-items.json").write_text(
        json.dumps([{"title": "A", "source": "S", "url": "https://a.com", "summary": ""}]))
    (tmp_path / "output" / "episode.mp3").write_bytes(b"x")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SPOTIFY_EMAIL", "e@example.com")
    monkeypatch.setenv("SPOTIFY_PASSWORD", "hunter2-secret")
    return config_file


def test_verification_prompt_raises_login_required_without_long_wait():
    page = FakePage(present={sp.VERIFICATION_SELECTOR})
    with pytest.raises(sp.SpotifyLoginRequired):
        sp.wait_for_login_step(page)
    # never the old 5-minute wait for a human to type an emailed code
    assert all(t is not None and t <= 60000 for t in page.waited)


def test_password_form_continues_login():
    page = FakePage(present={"#password"})
    assert sp.wait_for_login_step(page) == "password"


def test_redirect_to_wizard_means_logged_in():
    page = FakePage(url="https://creators.spotify.com/pod/show/abc123/episode/wizard")
    assert sp.wait_for_login_step(page) == "wizard"


def test_run_exits_3_with_final_code_line(tmp_path, monkeypatch, capsys):
    config_file = _config_files(tmp_path, monkeypatch)
    with patch.object(sp, "publish", side_effect=sp.SpotifyLoginRequired("verification")):
        with pytest.raises(SystemExit) as exc:
            sp.run(str(config_file))
    assert exc.value.code == 3
    assert capsys.readouterr().out.strip().splitlines()[-1] == "code=spotify_login_required"


def test_run_does_not_print_secrets(tmp_path, monkeypatch, capsys):
    config_file = _config_files(tmp_path, monkeypatch)
    with patch.object(sp, "publish", side_effect=sp.SpotifyLoginRequired("verification")):
        with pytest.raises(SystemExit):
            sp.run(str(config_file))
    captured = capsys.readouterr()
    assert "hunter2-secret" not in captured.out + captured.err
