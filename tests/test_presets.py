import pytest
from plugins.video.src.presets import resolve_preset, DEFAULT_FPS, DEFAULT_PRESET


def test_reel_is_vertical_1080x1920():
    p = resolve_preset("reel")
    assert (p.width, p.height) == (1080, 1920)


def test_story_matches_reel():
    assert resolve_preset("story").width == resolve_preset("reel").width
    assert resolve_preset("story").height == resolve_preset("reel").height


def test_square_and_landscape():
    assert (resolve_preset("square").width, resolve_preset("square").height) == (1080, 1080)
    assert (resolve_preset("landscape").width, resolve_preset("landscape").height) == (1920, 1080)


def test_default_fps_is_30():
    assert resolve_preset("reel").fps == DEFAULT_FPS == 30


def test_fps_override():
    assert resolve_preset("reel", fps=60).fps == 60


def test_default_preset_is_landscape():
    assert DEFAULT_PRESET == "landscape"


def test_unknown_preset_raises_naming_the_value():
    with pytest.raises(ValueError) as exc:
        resolve_preset("tiktok")
    assert "tiktok" in str(exc.value)


def test_preset_is_immutable():
    p = resolve_preset("reel")
    with pytest.raises(Exception):
        p.width = 999
