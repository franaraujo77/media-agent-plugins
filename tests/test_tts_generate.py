import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from plugins.media.src.tts_generate import generate_audio, run, MAX_TTS_CHARS, split_into_chunks


def test_split_short_text_returns_single_chunk():
    assert split_into_chunks("Hello world.", max_chars=4096) == ["Hello world."]


def test_split_at_sentence_boundary():
    # 110 chars total: first sentence is 60 chars including ". ", second is 50
    first = "A" * 58 + ". "   # 60 chars
    second = "B" * 49 + "."    # 50 chars
    text = first + second       # 110 chars total
    chunks = split_into_chunks(text, max_chars=70)
    assert len(chunks) == 2
    assert chunks[0].endswith(".")
    assert chunks[1].startswith("B")


def test_split_falls_back_to_hard_cut_when_no_boundary():
    text = "a" * 200
    chunks = split_into_chunks(text, max_chars=100)
    assert len(chunks) == 2
    assert len(chunks[0]) == 100
    assert chunks[1] == "a" * 100


def test_split_text_exactly_at_limit_returns_single_chunk():
    text = "a" * 100
    assert split_into_chunks(text, max_chars=100) == [text]


def test_generate_audio_calls_openai_with_correct_params(tmp_path):
    output_path = tmp_path / "episode.mp3"
    mock_response = MagicMock()

    with patch("plugins.media.src.tts_generate.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response
        mock_cls.return_value = mock_client

        generate_audio("Hello world.", "alloy", "tts-1-hd", output_path)

    mock_client.audio.speech.create.assert_called_once_with(
        model="tts-1-hd",
        voice="alloy",
        input="Hello world.",
    )
    mock_response.stream_to_file.assert_called_once_with(str(output_path))


def test_generate_audio_stitches_multiple_chunks(tmp_path):
    # Two sentences separated by ". " — force split by setting max_chars low
    script = "First sentence. Second sentence."
    output_path = tmp_path / "episode.mp3"

    with patch("plugins.media.src.tts_generate.OpenAI") as mock_cls, \
         patch("plugins.media.src.tts_generate.split_into_chunks", return_value=["First sentence.", "Second sentence."]) as mock_split:
        mock_client = MagicMock()
        def fake_stream(path):
            Path(path).write_bytes(b"mp3data")
        mock_client.audio.speech.create.return_value.stream_to_file.side_effect = fake_stream
        mock_cls.return_value = mock_client

        generate_audio(script, "alloy", "tts-1-hd", output_path)

    assert mock_client.audio.speech.create.call_count == 2


def test_generate_audio_splits_long_script_into_chunks(tmp_path):
    # Script long enough to require splitting
    long_script = ("Hello world. " * 400).strip()  # ~5200 chars
    output_path = tmp_path / "episode.mp3"

    with patch("plugins.media.src.tts_generate.OpenAI") as mock_cls:
        mock_client = MagicMock()
        # stream_to_file must actually write bytes so stitching works
        def fake_stream(path):
            Path(path).write_bytes(b"mp3data")
        mock_client.audio.speech.create.return_value.stream_to_file.side_effect = fake_stream
        mock_cls.return_value = mock_client

        generate_audio(long_script, "alloy", "tts-1-hd", output_path)

    assert mock_client.audio.speech.create.call_count > 1
    assert output_path.exists()
    # Each call's input must be within the API limit
    for call in mock_client.audio.speech.create.call_args_list:
        assert len(call.kwargs["input"]) <= MAX_TTS_CHARS


def test_generate_audio_does_not_truncate_short_script(tmp_path):
    script = "Short script."
    output_path = tmp_path / "episode.mp3"

    with patch("plugins.media.src.tts_generate.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = MagicMock()
        mock_cls.return_value = mock_client

        generate_audio(script, "nova", "tts-1", output_path)

    called_input = mock_client.audio.speech.create.call_args.kwargs["input"]
    assert called_input == "Short script."


def test_run_reads_config_and_writes_audio(tmp_path, monkeypatch):
    config = {"tts": {"voice": "nova", "model": "tts-1"}}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "script.txt").write_text("Hello podcast.")
    monkeypatch.chdir(tmp_path)

    with patch("plugins.media.src.tts_generate.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = MagicMock()
        mock_cls.return_value = mock_client
        run(str(config_file))

    mock_client.audio.speech.create.assert_called_once_with(
        model="tts-1",
        voice="nova",
        input="Hello podcast.",
    )
