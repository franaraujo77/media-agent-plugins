import subprocess
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from plugins.video.src.encode import (
    require_binary,
    run_ffmpeg,
    probe_duration,
    probe_image_size,
    frames_to_video,
    mux_audio,
)


def test_require_binary_passes_when_present():
    with patch("plugins.video.src.encode.shutil.which", return_value="/usr/bin/ffmpeg"):
        require_binary("ffmpeg")  # must not raise


def test_require_binary_gives_actionable_message_for_ffmpeg():
    with patch("plugins.video.src.encode.shutil.which", return_value=None):
        with pytest.raises(RuntimeError) as exc:
            require_binary("ffmpeg")
    assert "brew install ffmpeg" in str(exc.value)


def test_run_ffmpeg_surfaces_full_stderr_on_failure():
    failure = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="Invalid argument xyz")
    with patch("plugins.video.src.encode.shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("plugins.video.src.encode.subprocess.run", return_value=failure):
        with pytest.raises(RuntimeError) as exc:
            run_ffmpeg(["-i", "missing.png", "out.mp4"])
    assert "Invalid argument xyz" in str(exc.value)


def test_run_ffmpeg_prepends_overwrite_and_quiet_flags():
    ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    with patch("plugins.video.src.encode.shutil.which", return_value="/usr/bin/ffmpeg"), \
         patch("plugins.video.src.encode.subprocess.run", return_value=ok) as mock_run:
        run_ffmpeg(["-i", "a.png", "out.mp4"])
    called = mock_run.call_args[0][0]
    assert called[:4] == ["ffmpeg", "-y", "-loglevel", "error"]


def test_probe_duration_parses_seconds():
    ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="182.5\n", stderr="")
    with patch("plugins.video.src.encode.shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("plugins.video.src.encode.subprocess.run", return_value=ok):
        assert probe_duration(Path("episode.mp3")) == pytest.approx(182.5)


def test_probe_image_size_parses_dimensions():
    ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="1024,1536\n", stderr="")
    with patch("plugins.video.src.encode.shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("plugins.video.src.encode.subprocess.run", return_value=ok):
        assert probe_image_size(Path("a.png")) == (1024, 1536)


def test_probe_image_size_raises_on_unreadable_file():
    bad = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="Invalid data")
    with patch("plugins.video.src.encode.shutil.which", return_value="/usr/bin/ffprobe"), \
         patch("plugins.video.src.encode.subprocess.run", return_value=bad):
        with pytest.raises(RuntimeError):
            probe_image_size(Path("broken.png"))


def test_frames_to_video_uses_framerate_and_yuv420p(tmp_path):
    with patch("plugins.video.src.encode.run_ffmpeg") as mock:
        frames_to_video(tmp_path / "frames", 30, tmp_path / "silent.mp4")
    args = mock.call_args[0][0]
    assert "-framerate" in args
    assert args[args.index("-framerate") + 1] == "30"
    assert "yuv420p" in args
    assert "f%05d.png" in " ".join(args)


def test_mux_audio_maps_both_streams_and_uses_shortest(tmp_path):
    with patch("plugins.video.src.encode.run_ffmpeg") as mock:
        mux_audio(tmp_path / "silent.mp4", tmp_path / "e.mp3", tmp_path / "out.mp4")
    args = mock.call_args[0][0]
    assert "-shortest" in args
    assert "aac" in args
    assert args.count("-i") == 2


def test_mux_audio_without_audio_copies_stream(tmp_path):
    with patch("plugins.video.src.encode.run_ffmpeg") as mock:
        mux_audio(tmp_path / "silent.mp4", None, tmp_path / "out.mp4")
    args = mock.call_args[0][0]
    assert args.count("-i") == 1
    assert "copy" in args


def test_mux_audio_returns_the_output_path(tmp_path):
    out = tmp_path / "out.mp4"
    with patch("plugins.video.src.encode.run_ffmpeg"):
        assert mux_audio(tmp_path / "silent.mp4", None, out) == out


def test_frames_to_video_creates_parent_directory(tmp_path):
    out = tmp_path / "nested" / "dir" / "silent.mp4"
    with patch("plugins.video.src.encode.run_ffmpeg"):
        frames_to_video(tmp_path / "frames", 30, out)
    assert out.parent.is_dir()
