import json
import pytest
from pathlib import Path
from unittest.mock import patch
from plugins.video.src.storyboard import (
    load_storyboard,
    collect_images,
    validate_images,
    build_storyboard,
    resolve_durations,
    total_duration,
    overlap_total,
    crop_warnings,
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
    assert sb.audio.file == Path("output/episode.mp3")
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


def sb_with(slides, **kw):
    return build_storyboard({"slides": slides, **kw})


def test_rule1_no_audio_defaults_missing_seconds():
    sb = resolve_durations(sb_with([{"image": "a.png"}, {"image": "b.png"}]))
    assert [s.seconds for s in sb.slides] == [DEFAULT_SECONDS, DEFAULT_SECONDS]


def test_rule1_no_audio_permits_mixing_explicit_and_omitted():
    sb = resolve_durations(sb_with([{"image": "a.png", "seconds": 2}, {"image": "b.png"}]))
    assert [s.seconds for s in sb.slides] == [2.0, DEFAULT_SECONDS]


def test_overlap_total_ignores_first_slide_and_cuts():
    sb = sb_with([
        {"image": "a.png", "transition": "fade", "transition_seconds": 0.5},
        {"image": "b.png", "transition": "fade", "transition_seconds": 0.5},
        {"image": "c.png", "transition": "cut", "transition_seconds": 0.5},
    ])
    # slide 0's transition is ignored; slide 2 is a cut; only slide 1 counts
    assert overlap_total(sb) == pytest.approx(0.5)


def test_total_duration_subtracts_overlap():
    sb = resolve_durations(sb_with([
        {"image": "a.png", "seconds": 4},
        {"image": "b.png", "seconds": 4, "transition_seconds": 1.0},
    ]))
    assert total_duration(sb) == pytest.approx(7.0)


def test_rule2_explicit_durations_are_honored_with_audio():
    sb = sb_with([{"image": "a.png", "seconds": 3}, {"image": "b.png", "seconds": 3}],
                 audio="e.mp3")
    with patch("plugins.video.src.storyboard.probe_duration", return_value=5.5):
        resolved = resolve_durations(sb)
    assert [s.seconds for s in resolved.slides] == [3.0, 3.0]


def test_rule2_warns_when_audio_and_video_differ_by_more_than_half_a_second(capsys):
    sb = sb_with([{"image": "a.png", "seconds": 3}], audio="e.mp3")
    with patch("plugins.video.src.storyboard.probe_duration", return_value=30.0):
        resolve_durations(sb)
    assert "Warning" in capsys.readouterr().out


def test_rule2_stays_quiet_within_half_a_second(capsys):
    sb = sb_with([{"image": "a.png", "seconds": 3}], audio="e.mp3")
    with patch("plugins.video.src.storyboard.probe_duration", return_value=3.2):
        resolve_durations(sb)
    assert "Warning" not in capsys.readouterr().out


def test_rule3_distributes_audio_evenly():
    sb = sb_with([{"image": "a.png"}, {"image": "b.png"}, {"image": "c.png"}],
                 audio="e.mp3")
    with patch("plugins.video.src.storyboard.probe_duration", return_value=30.0):
        resolved = resolve_durations(sb)
    # overlap: slides 1 and 2 fade at 0.5 each = 1.0; each slide = (30 + 1.0) / 3
    assert [s.seconds for s in resolved.slides] == pytest.approx([31.0 / 3] * 3)
    assert total_duration(resolved) == pytest.approx(30.0)


def test_rule3_result_plays_exactly_as_long_as_the_audio():
    sb = sb_with([{"image": "a.png"}, {"image": "b.png"}], audio="e.mp3")
    with patch("plugins.video.src.storyboard.probe_duration", return_value=182.5):
        resolved = resolve_durations(sb)
    assert total_duration(resolved) == pytest.approx(182.5)


def test_mixing_explicit_and_omitted_with_audio_raises_naming_indices():
    sb = sb_with([{"image": "a.png", "seconds": 2}, {"image": "b.png"}, {"image": "c.png"}],
                 audio="e.mp3")
    with patch("plugins.video.src.storyboard.probe_duration", return_value=10.0):
        with pytest.raises(ValueError) as exc:
            resolve_durations(sb)
    message = str(exc.value)
    assert "1" in message and "2" in message


def test_crop_warning_fires_for_a_codex_portrait_image_into_a_reel():
    """The motivating case: Codex emits 1024x1536 (2:3). Covering a 9:16 target
    scales to height 1920 -> width 1280, cropped to 1080: 200/1280 = 15.6% lost."""
    sb = sb_with([{"image": "a.png"}], preset="reel")  # target 1080x1920 (9:16)
    with patch("plugins.video.src.storyboard.probe_image_size", return_value=(1024, 1536)):
        warnings = crop_warnings(sb)
    assert len(warnings) == 1
    assert "a.png" in warnings[0]
    assert "16%" in warnings[0]


def test_crop_warning_fires_hard_for_a_square_image_into_a_reel():
    """1254x1254 (1:1) into 9:16 discards 43.75% — the loudest realistic case."""
    sb = sb_with([{"image": "a.png"}], preset="reel")
    with patch("plugins.video.src.storyboard.probe_image_size", return_value=(1254, 1254)):
        assert len(crop_warnings(sb)) == 1


def test_crop_warning_silent_just_below_the_threshold():
    """1080x1800 into 9:16: kept = 0.5625/0.6 = 93.75%, so 6.25% lost — quiet."""
    sb = sb_with([{"image": "a.png"}], preset="reel")
    with patch("plugins.video.src.storyboard.probe_image_size", return_value=(1080, 1800)):
        assert crop_warnings(sb) == []


def test_crop_warning_silent_when_aspect_already_matches():
    sb = sb_with([{"image": "a.png"}], preset="reel")
    with patch("plugins.video.src.storyboard.probe_image_size", return_value=(1080, 1920)):
        assert crop_warnings(sb) == []


def test_crop_warning_silent_under_contain_fit():
    sb = sb_with([{"image": "a.png"}], preset="reel", fit="contain")
    with patch("plugins.video.src.storyboard.probe_image_size", return_value=(1024, 1536)):
        assert crop_warnings(sb) == []
