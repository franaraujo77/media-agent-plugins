import json
import pytest
from pathlib import Path
from plugins.video.src.storyboard import (
    load_storyboard,
    collect_images,
    validate_images,
    Slide,
    DEFAULT_SECONDS,
    DEFAULT_TRANSITION_SECONDS,
    IMAGE_EXTENSIONS,
)


def write_sb(tmp_path, data):
    p = tmp_path / "sb.json"
    p.write_text(json.dumps(data))
    return p


def test_loads_minimal_storyboard_with_defaults(tmp_path):
    sb = load_storyboard(write_sb(tmp_path, {"slides": [{"image": "a.png"}]}))
    assert sb.preset.name == "landscape"
    assert sb.fit == "cover"
    assert sb.backend is None
    assert sb.output == Path("output/video.mp4")
    assert sb.audio is None
    slide = sb.slides[0]
    assert slide.caption is None
    assert slide.seconds is None
    assert slide.motion == "zoom-in"
    assert slide.transition == "fade"
    assert slide.transition_seconds == DEFAULT_TRANSITION_SECONDS


def test_explicit_fields_are_kept(tmp_path):
    sb = load_storyboard(write_sb(tmp_path, {
        "preset": "reel",
        "audio": "output/episode.mp3",
        "output": "out/x.mp4",
        "fit": "contain",
        "backend": "browser",
        "slides": [{"image": "a.png", "caption": "Hook", "seconds": 3.5,
                    "motion": "pan-left", "transition": "cut", "transition_seconds": 0.25}],
    }))
    assert sb.preset.name == "reel"
    assert sb.audio == Path("output/episode.mp3")
    assert sb.output == Path("out/x.mp4")
    assert sb.fit == "contain"
    assert sb.backend == "browser"
    assert sb.slides[0].caption == "Hook"
    assert sb.slides[0].seconds == 3.5
    assert sb.slides[0].motion == "pan-left"
    assert sb.slides[0].transition == "cut"


def test_fps_key_overrides_preset_fps(tmp_path):
    sb = load_storyboard(write_sb(tmp_path, {"fps": 60, "slides": [{"image": "a.png"}]}))
    assert sb.preset.fps == 60


def test_empty_slides_is_an_error(tmp_path):
    with pytest.raises(ValueError) as exc:
        load_storyboard(write_sb(tmp_path, {"slides": []}))
    assert "slides" in str(exc.value).lower()


def test_slide_without_image_is_an_error(tmp_path):
    with pytest.raises(ValueError) as exc:
        load_storyboard(write_sb(tmp_path, {"slides": [{"caption": "no image"}]}))
    assert "image" in str(exc.value).lower()


@pytest.mark.parametrize("field,value", [
    ("motion", "spin"),
    ("transition", "wipe"),
])
def test_unknown_slide_enum_names_the_value(tmp_path, field, value):
    with pytest.raises(ValueError) as exc:
        load_storyboard(write_sb(tmp_path, {"slides": [{"image": "a.png", field: value}]}))
    assert value in str(exc.value)


def test_unknown_fit_names_the_value(tmp_path):
    with pytest.raises(ValueError) as exc:
        load_storyboard(write_sb(tmp_path, {"fit": "stretch", "slides": [{"image": "a.png"}]}))
    assert "stretch" in str(exc.value)


def test_collect_images_from_glob_is_sorted(tmp_path):
    for name in ["c.png", "a.png", "b.png"]:
        (tmp_path / name).touch()
    found = collect_images(str(tmp_path / "*.png"))
    assert [p.name for p in found] == ["a.png", "b.png", "c.png"]


def test_collect_images_from_directory_filters_extensions(tmp_path):
    for name in ["a.png", "b.JPG", "c.webp", "notes.txt", "clip.mp4"]:
        (tmp_path / name).touch()
    found = collect_images(str(tmp_path))
    assert [p.name for p in found] == ["a.png", "b.JPG", "c.webp"]


def test_collect_images_empty_result_is_an_error(tmp_path):
    with pytest.raises(ValueError):
        collect_images(str(tmp_path / "*.png"))


def test_image_extensions_cover_expected_formats():
    assert IMAGE_EXTENSIONS == {".png", ".jpg", ".jpeg", ".webp"}


def test_validate_images_reports_every_missing_file_at_once(tmp_path):
    present = tmp_path / "here.png"
    present.touch()
    slides = [
        Slide(image=tmp_path / "gone1.png", caption=None, seconds=None,
              motion="zoom-in", transition="fade", transition_seconds=0.5),
        Slide(image=present, caption=None, seconds=None,
              motion="zoom-in", transition="fade", transition_seconds=0.5),
        Slide(image=tmp_path / "gone2.png", caption=None, seconds=None,
              motion="zoom-in", transition="fade", transition_seconds=0.5),
    ]
    with pytest.raises(ValueError) as exc:
        validate_images(slides)
    message = str(exc.value)
    assert "gone1.png" in message and "gone2.png" in message
