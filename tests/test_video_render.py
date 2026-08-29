import json
import pytest
from pathlib import Path
from unittest.mock import patch
from plugins.video.src.storyboard import build_storyboard, resolve_durations
from plugins.video.src.video_render import select_backend, parse_args, storyboard_from_args, run


def sb(slides, **kw):
    return resolve_durations(build_storyboard({"slides": slides, **kw}))


def test_captions_select_the_browser_backend():
    name, reason = select_backend(sb([{"image": "a.png", "caption": "Hook"}]))
    assert name == "browser"
    assert "caption" in reason.lower()


def test_no_captions_select_the_ffmpeg_backend():
    name, reason = select_backend(sb([{"image": "a.png"}, {"image": "b.png"}]))
    assert name == "ffmpeg"
    assert "caption" in reason.lower()


def test_one_caption_among_many_still_selects_browser():
    name, _ = select_backend(sb([{"image": "a.png"}, {"image": "b.png", "caption": "Hi"}]))
    assert name == "browser"


def test_empty_caption_does_not_select_browser():
    name, _ = select_backend(sb([{"image": "a.png", "caption": ""}]))
    assert name == "ffmpeg"


def test_explicit_backend_overrides_auto_selection():
    name, reason = select_backend(sb([{"image": "a.png", "caption": "Hook"}], backend="ffmpeg"))
    assert name == "ffmpeg"
    assert "explicit" in reason.lower()


def test_unknown_explicit_backend_is_an_error():
    with pytest.raises(ValueError) as exc:
        select_backend(sb([{"image": "a.png"}], backend="premiere"))
    assert "premiere" in str(exc.value)


def test_flags_and_storyboard_together_are_an_error(tmp_path):
    board = tmp_path / "sb.json"
    board.write_text(json.dumps({"slides": [{"image": "a.png"}]}))
    args = parse_args([str(board), "--images", "x/*.png"])
    with pytest.raises(ValueError) as exc:
        storyboard_from_args(args)
    assert "mutually exclusive" in str(exc.value).lower()


def test_neither_storyboard_nor_images_is_an_error():
    args = parse_args([])
    with pytest.raises(ValueError):
        storyboard_from_args(args)


def test_flags_build_an_equivalent_storyboard(tmp_path):
    for name in ["a.png", "b.png"]:
        (tmp_path / name).touch()
    args = parse_args(["--images", str(tmp_path / "*.png"), "--preset", "reel",
                       "--seconds", "2.5", "--fit", "contain", "--output", "o/v.mp4"])
    board = storyboard_from_args(args)
    assert board.preset.name == "reel"
    assert board.fit == "contain"
    assert board.output == Path("o/v.mp4")
    assert [s.seconds for s in board.slides] == [2.5, 2.5]
    assert [s.image.name for s in board.slides] == ["a.png", "b.png"]


def test_run_reports_the_chosen_backend_and_reason(tmp_path, capsys):
    image = tmp_path / "a.png"
    image.touch()
    out = tmp_path / "v.mp4"
    with patch("plugins.video.src.video_render.ffmpeg_backend.render",
               return_value=tmp_path / "silent.mp4"), \
         patch("plugins.video.src.video_render.mux_audio", return_value=out), \
         patch("plugins.video.src.video_render.crop_warnings", return_value=[]):
        run(["--images", str(image), "--output", str(out)])
    printed = capsys.readouterr().out
    assert "Backend: ffmpeg" in printed


def test_run_prints_crop_warnings(tmp_path, capsys):
    image = tmp_path / "a.png"
    image.touch()
    with patch("plugins.video.src.video_render.ffmpeg_backend.render",
               return_value=tmp_path / "silent.mp4"), \
         patch("plugins.video.src.video_render.mux_audio", return_value=tmp_path / "v.mp4"), \
         patch("plugins.video.src.video_render.crop_warnings",
               return_value=["a.png: 1024x1536 cropped to 1080x1920 discards 33% of the image"]):
        run(["--images", str(image), "--preset", "reel", "--output", str(tmp_path / "v.mp4")])
    assert "discards 33%" in capsys.readouterr().out


def test_run_fails_before_rendering_when_an_image_is_missing(tmp_path):
    with patch("plugins.video.src.video_render.ffmpeg_backend.render") as render_mock:
        with pytest.raises(ValueError):
            run(["--images", str(tmp_path / "nope.png")])
    render_mock.assert_not_called()


def test_run_dispatches_to_the_browser_backend_when_captioned(tmp_path):
    board = tmp_path / "sb.json"
    image = tmp_path / "a.png"
    image.touch()
    board.write_text(json.dumps({
        "slides": [{"image": str(image), "caption": "Hook"}],
        "output": str(tmp_path / "v.mp4"),
    }))
    with patch("plugins.video.src.video_render.browser_backend.render",
               return_value=tmp_path / "silent.mp4") as browser, \
         patch("plugins.video.src.video_render.mux_audio", return_value=tmp_path / "v.mp4"), \
         patch("plugins.video.src.video_render.crop_warnings", return_value=[]):
        run([str(board)])
    browser.assert_called_once()


@pytest.mark.integration
def test_end_to_end_render_produces_a_correct_mp4(tmp_path):
    """Real ffmpeg. The only test proving the whole pipeline works."""
    import subprocess
    from plugins.video.src.encode import run_ffmpeg

    images = []
    for i, colour in enumerate(["red", "blue"]):
        path = tmp_path / f"{i}.png"
        run_ffmpeg(["-f", "lavfi", "-i", f"color=c={colour}:size=320x240",
                    "-frames:v", "1", str(path)])
        images.append(path)

    out = tmp_path / "video.mp4"
    board = tmp_path / "sb.json"
    board.write_text(json.dumps({
        "preset": "square",
        "fps": 10,
        "output": str(out),
        "slides": [{"image": str(p), "seconds": 1.0, "transition": "cut"} for p in images],
    }))

    run([str(board)])

    assert out.exists()
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,nb_frames,r_frame_rate",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    width, height, frame_rate, frames, duration = (
        probe[0], probe[1], probe[2], probe[3], probe[4],
    )
    assert (int(width), int(height)) == (1080, 1080)
    assert frame_rate == "10/1"
    assert int(frames) == 20          # 2 slides x 1.0s x 10fps, cut transition
    assert float(duration) == pytest.approx(2.0, abs=0.15)
