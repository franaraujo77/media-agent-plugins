import re
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from plugins.video.src.storyboard import build_storyboard, resolve_durations
from plugins.video.src.backends.browser_backend import build_scene_html, capture_frames, render


def sb(slides, **kw):
    return resolve_durations(build_storyboard({"slides": slides, **kw}))


def test_scene_html_embeds_every_slide_image():
    html = build_scene_html(sb([{"image": "a.png"}, {"image": "b.png"}]))
    assert "a.png" in html and "b.png" in html


def test_scene_html_embeds_captions():
    html = build_scene_html(sb([{"image": "a.png", "caption": "The hook"}]))
    assert "The hook" in html


def test_scene_html_escapes_caption_markup():
    html = build_scene_html(sb([{"image": "a.png", "caption": "<script>bad()</script>"}]))
    assert "<script>bad()</script>" not in html


def test_scene_html_pauses_all_animations():
    html = build_scene_html(sb([{"image": "a.png"}]))
    assert "pause()" in html


def test_scene_html_exposes_a_seek_hook():
    html = build_scene_html(sb([{"image": "a.png"}]))
    assert "__seek" in html
    assert "currentTime" in html


def test_scene_html_sizes_the_stage_to_the_preset():
    html = build_scene_html(sb([{"image": "a.png"}], preset="reel"))
    assert "1080px" in html and "1920px" in html


def test_scene_html_uses_contain_for_contain_fit():
    html = build_scene_html(sb([{"image": "a.png"}], fit="contain"))
    assert "contain" in html


def _mock_playwright(page):
    browser = MagicMock()
    browser.new_page.return_value = page
    chromium = MagicMock()
    chromium.launch.return_value = browser
    ctx = MagicMock()
    ctx.__enter__.return_value = MagicMock(chromium=chromium)
    return ctx, browser


def test_capture_frames_never_disables_animations(tmp_path):
    """Regression guard. animations='disabled' fast-forwards finite animations to
    completion, yielding identical end-state frames: a valid MP4 with zero motion."""
    page = MagicMock()
    ctx, _ = _mock_playwright(page)
    with patch("plugins.video.src.backends.browser_backend.sync_playwright", return_value=ctx):
        capture_frames(sb([{"image": "a.png", "seconds": 0.1}]), tmp_path)
    for call in page.screenshot.call_args_list:
        assert "animations" not in call.kwargs


def test_capture_frames_seeks_a_distinct_time_per_frame(tmp_path):
    page = MagicMock()
    ctx, _ = _mock_playwright(page)
    board = sb([{"image": "a.png", "seconds": 1.0}], fps=10)
    with patch("plugins.video.src.backends.browser_backend.sync_playwright", return_value=ctx):
        capture_frames(board, tmp_path)
    seeks = [c[0][1] for c in page.evaluate.call_args_list]
    assert seeks == sorted(seeks)
    assert len(set(seeks)) == len(seeks) == 10


def test_capture_frames_closes_browser_on_error(tmp_path):
    page = MagicMock()
    page.screenshot.side_effect = RuntimeError("boom")
    ctx, browser = _mock_playwright(page)
    with patch("plugins.video.src.backends.browser_backend.sync_playwright", return_value=ctx):
        with pytest.raises(RuntimeError):
            capture_frames(sb([{"image": "a.png", "seconds": 0.1}]), tmp_path)
    browser.close.assert_called_once()


def test_capture_frames_names_files_for_the_encoder(tmp_path):
    page = MagicMock()
    ctx, _ = _mock_playwright(page)
    with patch("plugins.video.src.backends.browser_backend.sync_playwright", return_value=ctx):
        frames_dir = capture_frames(sb([{"image": "a.png", "seconds": 0.2}], fps=10), tmp_path)
    names = [Path(c.kwargs["path"]).name for c in page.screenshot.call_args_list]
    assert names[0] == "f00000.png"
    assert all(re.fullmatch(r"f\d{5}\.png", n) for n in names)
    assert frames_dir.is_dir()


@pytest.mark.integration
def test_real_capture_produces_frames_that_actually_differ(tmp_path):
    """The only test that catches animations='disabled'. Metadata-based checks
    all pass on a motionless video; comparing frame bytes does not."""
    from plugins.video.src.encode import run_ffmpeg
    image = tmp_path / "src.png"
    run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=640x480:duration=1", "-frames:v", "1", str(image)])

    board = sb([{"image": str(image), "seconds": 1.0, "motion": "zoom-in"}],
               preset="square", fps=4)
    frames_dir = capture_frames(board, tmp_path)
    frames = sorted(frames_dir.glob("*.png"))
    assert len(frames) == 4
    assert frames[0].read_bytes() != frames[-1].read_bytes(), \
        "All frames identical — animations are not being seeked"


def test_render_encodes_captured_frames(tmp_path):
    with patch("plugins.video.src.backends.browser_backend.capture_frames",
               return_value=tmp_path / "frames") as cap, \
         patch("plugins.video.src.backends.browser_backend.frames_to_video") as enc:
        enc.return_value = tmp_path / "silent.mp4"
        out = render(sb([{"image": "a.png"}]), tmp_path)
    cap.assert_called_once()
    enc.assert_called_once()
    assert out == tmp_path / "silent.mp4"


def test_capture_frames_wraps_missing_chromium_with_hint(tmp_path):
    with patch("plugins.video.src.backends.browser_backend.sync_playwright") as mock_sp:
        launch_ctx = MagicMock()
        launch_ctx.__enter__.return_value.chromium.launch.side_effect = RuntimeError(
            "Executable doesn't exist at .../chromium"
        )
        mock_sp.return_value = launch_ctx
        with pytest.raises(RuntimeError) as excinfo:
            capture_frames(sb([{"image": "a.png", "seconds": 0.1}]), tmp_path)
    assert "playwright install chromium" in str(excinfo.value)
