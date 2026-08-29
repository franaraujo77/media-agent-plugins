"""Audio-track controls: volume, trim/start offset, fades, loop, and mixing a
music bed under the primary track."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from plugins.video.src.encode import mux_audio
from plugins.video.src.storyboard import (
    AudioTrack,
    DEFAULT_SECONDS,
    build_storyboard,
    load_storyboard,
    resolve_durations,
    total_duration,
    validate_audio,
)


def write_sb(tmp_path, data):
    p = tmp_path / "sb.json"
    p.write_text(json.dumps(data))
    return p


def sb_with(slides, **kw):
    return build_storyboard({"slides": slides, **kw})


# --- parsing ---------------------------------------------------------------


def test_audio_as_a_string_builds_a_track_with_defaults(tmp_path):
    sb = load_storyboard(write_sb(tmp_path, {
        "audio": "output/episode.mp3", "slides": [{"image": "a.png"}],
    }))
    assert sb.audio.file == Path("output/episode.mp3")
    assert sb.audio.volume == 1.0
    assert sb.audio.start == 0.0
    assert sb.audio.duration is None
    assert sb.audio.fade_in == 0.0
    assert sb.audio.fade_out == 0.0
    assert sb.audio.loop is False
    assert sb.music is None


def test_audio_as_an_object_keeps_every_field(tmp_path):
    sb = load_storyboard(write_sb(tmp_path, {
        "audio": {"file": "e.mp3", "volume": 0.8, "start": 3.0, "duration": 20.0,
                  "fade_in": 1.0, "fade_out": 1.5, "loop": True},
        "slides": [{"image": "a.png"}],
    }))
    track = sb.audio
    assert track.file == Path("e.mp3")
    assert track.volume == 0.8
    assert track.start == 3.0
    assert track.duration == 20.0
    assert track.fade_in == 1.0
    assert track.fade_out == 1.5
    assert track.loop is True


def test_music_slot_is_parsed_like_the_audio_slot(tmp_path):
    sb = load_storyboard(write_sb(tmp_path, {
        "music": {"file": "bed.mp3", "volume": 0.15, "loop": True},
        "slides": [{"image": "a.png"}],
    }))
    assert sb.music.file == Path("bed.mp3")
    assert sb.music.volume == 0.15
    assert sb.music.loop is True


def test_track_without_file_is_an_error(tmp_path):
    with pytest.raises(ValueError) as exc:
        load_storyboard(write_sb(tmp_path, {"audio": {"volume": 0.5},
                                            "slides": [{"image": "a.png"}]}))
    assert "file" in str(exc.value).lower()


def test_unknown_track_field_names_the_field_and_the_slot(tmp_path):
    with pytest.raises(ValueError) as exc:
        load_storyboard(write_sb(tmp_path, {"music": {"file": "b.mp3", "fadein": 1},
                                            "slides": [{"image": "a.png"}]}))
    message = str(exc.value)
    assert "fadein" in message and "music" in message


@pytest.mark.parametrize("field,value", [
    ("volume", -0.5),
    ("start", -1.0),
    ("duration", 0.0),
    ("fade_in", -1.0),
    ("fade_out", -2.0),
])
def test_out_of_range_track_numbers_are_rejected(tmp_path, field, value):
    with pytest.raises(ValueError) as exc:
        load_storyboard(write_sb(tmp_path, {"audio": {"file": "e.mp3", field: value},
                                            "slides": [{"image": "a.png"}]}))
    assert field in str(exc.value)


def test_validate_audio_reports_both_missing_files_at_once(tmp_path):
    sb = sb_with([{"image": "a.png"}],
                 audio=str(tmp_path / "gone-voice.mp3"),
                 music=str(tmp_path / "gone-bed.mp3"))
    with pytest.raises(ValueError) as exc:
        validate_audio(sb)
    message = str(exc.value)
    assert "gone-voice.mp3" in message and "gone-bed.mp3" in message


# --- duration math ---------------------------------------------------------


def test_start_offset_shortens_the_duration_budget():
    sb = sb_with([{"image": "a.png"}, {"image": "b.png"}],
                 audio={"file": "e.mp3", "start": 10.0})
    with patch("plugins.video.src.storyboard.probe_duration", return_value=40.0):
        resolved = resolve_durations(sb)
    assert total_duration(resolved) == pytest.approx(30.0)


def test_explicit_duration_wins_over_the_probed_length():
    sb = sb_with([{"image": "a.png"}, {"image": "b.png"}],
                 audio={"file": "e.mp3", "start": 5.0, "duration": 12.0})
    with patch("plugins.video.src.storyboard.probe_duration", return_value=100.0):
        resolved = resolve_durations(sb)
    assert total_duration(resolved) == pytest.approx(12.0)


def test_music_never_drives_slide_durations():
    """A bed is trimmed or looped to fit; only the primary track sets the length."""
    sb = sb_with([{"image": "a.png"}], music={"file": "bed.mp3", "loop": True})
    with patch("plugins.video.src.storyboard.probe_duration", return_value=180.0) as probe:
        resolved = resolve_durations(sb)
    assert [s.seconds for s in resolved.slides] == [DEFAULT_SECONDS]
    probe.assert_not_called()


# --- ffmpeg argv -----------------------------------------------------------


def build_argv(tmp_path, audio=None, music=None, video_seconds=None):
    with patch("plugins.video.src.encode.run_ffmpeg") as mock:
        mux_audio(tmp_path / "silent.mp4", audio, tmp_path / "out.mp4",
                  music=music, video_seconds=video_seconds)
    return mock.call_args[0][0]


def filter_of(argv):
    return argv[argv.index("-filter_complex") + 1]


def test_plain_track_needs_no_filter_graph(tmp_path):
    argv = build_argv(tmp_path, audio=AudioTrack(file=Path("e.mp3")))
    assert "-filter_complex" not in argv
    assert "-map" in argv and "1:a" in argv
    assert "-shortest" in argv


def test_volume_and_fades_become_a_filter_chain(tmp_path):
    argv = build_argv(
        tmp_path,
        audio=AudioTrack(file=Path("e.mp3"), volume=0.5, fade_in=1.0, fade_out=2.0),
        video_seconds=30.0,
    )
    chain = filter_of(argv)
    assert "volume=0.5" in chain
    assert "afade=t=in:st=0:d=1.0" in chain
    assert "afade=t=out:st=28.0:d=2.0" in chain


def test_fade_out_is_measured_from_the_tracks_own_length_when_trimmed(tmp_path):
    argv = build_argv(
        tmp_path,
        audio=AudioTrack(file=Path("e.mp3"), duration=10.0, fade_out=2.0),
        video_seconds=30.0,
    )
    assert "afade=t=out:st=8.0:d=2.0" in filter_of(argv)


def test_fade_out_without_any_known_length_is_an_actionable_error(tmp_path):
    with patch("plugins.video.src.encode.run_ffmpeg"):
        with pytest.raises(ValueError) as exc:
            mux_audio(tmp_path / "silent.mp4",
                      AudioTrack(file=Path("e.mp3"), fade_out=2.0),
                      tmp_path / "out.mp4")
    assert "fade_out" in str(exc.value)


def test_start_and_duration_trim_the_input(tmp_path):
    argv = build_argv(tmp_path,
                      audio=AudioTrack(file=Path("e.mp3"), start=12.5, duration=30.0))
    i = argv.index("e.mp3")
    assert argv[i - 5:i] == ["-ss", "12.5", "-t", "30.0", "-i"]


def test_loop_repeats_the_input_stream(tmp_path):
    argv = build_argv(tmp_path, audio=AudioTrack(file=Path("bed.mp3"), loop=True),
                      video_seconds=30.0)
    assert "-stream_loop" in argv
    assert argv[argv.index("-stream_loop") + 1] == "-1"


def test_two_tracks_are_mixed_without_renormalising_the_gains(tmp_path):
    argv = build_argv(
        tmp_path,
        audio=AudioTrack(file=Path("voice.mp3")),
        music=AudioTrack(file=Path("bed.mp3"), volume=0.15, loop=True),
        video_seconds=30.0,
    )
    chain = filter_of(argv)
    assert "amix=inputs=2" in chain
    assert "normalize=0" in chain
    assert argv.count("-i") == 3
    assert "volume=0.15" in chain


def test_music_alone_is_muxed_without_a_primary_track(tmp_path):
    argv = build_argv(tmp_path, music=AudioTrack(file=Path("bed.mp3"), volume=0.3),
                      video_seconds=30.0)
    assert argv.count("-i") == 2
    assert "volume=0.3" in filter_of(argv)
    assert "amix" not in filter_of(argv)


def test_a_short_bed_is_padded_rather_than_truncating_the_video(tmp_path):
    """A 3s bed under a 7s slideshow must not cut the video down to 3s."""
    argv = build_argv(tmp_path, music=AudioTrack(file=Path("bed.mp3")),
                      video_seconds=7.0)
    assert "apad" in filter_of(argv)


def test_the_bed_never_extends_the_primary_track(tmp_path):
    """Mixing ends on the primary track, so a long or looping bed cannot stretch it."""
    argv = build_argv(tmp_path, audio=AudioTrack(file=Path("voice.mp3")),
                      music=AudioTrack(file=Path("bed.mp3"), loop=True),
                      video_seconds=30.0)
    assert "duration=first" in filter_of(argv)
    assert "apad" not in filter_of(argv)


def test_video_stream_is_never_re_encoded(tmp_path):
    argv = build_argv(tmp_path, audio=AudioTrack(file=Path("voice.mp3")),
                      music=AudioTrack(file=Path("bed.mp3")), video_seconds=30.0)
    assert argv[argv.index("-c:v") + 1] == "copy"
    assert "aac" in argv
