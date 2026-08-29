import pytest
from pathlib import Path
from unittest.mock import patch
from plugins.video.src.storyboard import build_storyboard, resolve_durations
from plugins.video.src.backends.ffmpeg_backend import build_filtergraph, build_args, render


def sb(slides, **kw):
    return resolve_durations(build_storyboard({"slides": slides, **kw}))


def test_upscales_before_zoompan_to_avoid_jitter():
    graph, _ = build_filtergraph(sb([{"image": "a.png"}]))
    assert "scale=8000:-1,zoompan=" in graph


def test_one_labelled_chain_per_slide():
    graph, _ = build_filtergraph(sb([{"image": "a.png"}, {"image": "b.png"}]))
    assert "[v0]" in graph and "[v1]" in graph


def test_single_slide_final_label_is_v0():
    _, final = build_filtergraph(sb([{"image": "a.png"}]))
    assert final == "v0"


def test_fade_transition_uses_xfade_with_offset():
    graph, final = build_filtergraph(sb([
        {"image": "a.png", "seconds": 4},
        {"image": "b.png", "seconds": 4, "transition": "fade", "transition_seconds": 1.0},
    ]))
    assert "xfade=transition=fade:duration=1.0" in graph
    assert "offset=3.000" in graph  # 4.0 - 1.0
    assert final == "x1"


def test_cut_transition_uses_concat_not_xfade():
    graph, _ = build_filtergraph(sb([
        {"image": "a.png", "seconds": 4},
        {"image": "b.png", "seconds": 4, "transition": "cut"},
    ]))
    assert "concat=n=2:v=1:a=0" in graph
    assert "xfade" not in graph


def test_cover_fit_crops_to_preset():
    graph, _ = build_filtergraph(sb([{"image": "a.png"}], preset="reel"))
    assert "force_original_aspect_ratio=increase" in graph
    assert "crop=1080:1920" in graph


def test_contain_fit_pads_to_preset():
    graph, _ = build_filtergraph(sb([{"image": "a.png"}], preset="reel", fit="contain"))
    assert "force_original_aspect_ratio=decrease" in graph
    assert "pad=1080:1920" in graph


def test_zoom_out_starts_zoomed_in():
    """Assert on the distinguishing substring: zoom-in's clamp expression also
    contains 1.18, so a bare "1.18" check passes even with the motions swapped."""
    graph, _ = build_filtergraph(sb([{"image": "a.png", "motion": "zoom-out"}]))
    assert "if(eq(on,0),1.18" in graph


def test_zoom_in_does_not_start_zoomed_in():
    graph, _ = build_filtergraph(sb([{"image": "a.png", "motion": "zoom-in"}]))
    assert "if(eq(on,0),1.18" not in graph
    assert "min(zoom+" in graph


def test_pan_travel_is_derived_from_the_zoom_headroom():
    """A fixed fraction of iw asks for more travel than the zoom provides, so
    zoompan clamps x and the pan freezes part-way through the slide."""
    graph, _ = build_filtergraph(sb([{"image": "a.png", "motion": "pan-right"}]))
    assert "(iw-iw/zoom)" in graph
    assert "iw*0.03" not in graph


def test_pan_left_and_pan_right_travel_in_opposite_directions():
    right, _ = build_filtergraph(sb([{"image": "a.png", "motion": "pan-right"}]))
    left, _ = build_filtergraph(sb([{"image": "a.png", "motion": "pan-left"}]))
    assert right != left


def test_every_slide_chain_normalises_the_timebase():
    """concat emits 1/1000000 and zoompan 1/fps; xfade refuses mismatched input
    timebases, so a cut followed by a fade crashes without this."""
    graph, _ = build_filtergraph(sb([{"image": "a.png"}, {"image": "b.png"}]))
    assert graph.count("settb=1/1000000") == 2


def test_motion_none_holds_a_constant_zoom():
    graph, _ = build_filtergraph(sb([{"image": "a.png", "motion": "none"}]))
    assert "zoompan=z='1'" in graph


def test_build_args_supplies_one_loop_input_per_slide():
    args = build_args(sb([{"image": "a.png"}, {"image": "b.png"}]), Path("out.mp4"))
    assert args.count("-loop") == 2
    assert "a.png" in args and "b.png" in args


def test_build_args_uses_one_input_frame_per_slide():
    """zoompan's d= sets the duration. If the input emits many frames (e.g. -t as an
    input option without -framerate 1), each is multiplied by d and the video runs long."""
    args = build_args(sb([{"image": "a.png", "seconds": 4}]), Path("out.mp4"))
    assert args[:6] == ["-loop", "1", "-framerate", "1", "-t", "1"]


def test_build_args_maps_the_final_label():
    args = build_args(sb([{"image": "a.png"}]), Path("out.mp4"))
    assert "-map" in args
    assert "[v0]" in args


def test_render_writes_silent_mp4_into_workdir(tmp_path):
    with patch("plugins.video.src.backends.ffmpeg_backend.run_ffmpeg") as mock:
        out = render(sb([{"image": "a.png"}]), tmp_path)
    assert out.parent == tmp_path
    assert out.suffix == ".mp4"
    # audio must never be referenced by this backend
    assert "-c:a" not in mock.call_args[0][0]


@pytest.mark.integration
def test_real_pan_keeps_moving_to_the_last_frame(tmp_path):
    """Catches a clamped pan: zoompan silently pins x once the requested travel
    exceeds the headroom the zoom provides, and the last frames become identical."""
    import subprocess
    from plugins.video.src.encode import run_ffmpeg

    image = tmp_path / "src.png"
    run_ffmpeg(["-f", "lavfi", "-i", "testsrc=size=640x480:duration=1",
                "-frames:v", "1", str(image)])

    board = sb([{"image": str(image), "seconds": 2.0, "motion": "pan-right"}],
               preset="square", fps=10)
    silent = render(board, tmp_path / "work")

    frames_dir = tmp_path / "out"
    frames_dir.mkdir()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent),
                    str(frames_dir / "%03d.png")], check=True)
    frames = sorted(frames_dir.glob("*.png"))
    assert len(frames) >= 3
    assert frames[-1].read_bytes() != frames[-2].read_bytes(), \
        "Last two frames identical — the pan froze (zoompan clamped x)"
