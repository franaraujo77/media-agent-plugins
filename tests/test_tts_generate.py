import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from plugins.media.src.tts_generate import generate_audio, run, MAX_TTS_CHARS


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


def test_generate_audio_truncates_script_over_limit(tmp_path):
    long_script = "x" * (MAX_TTS_CHARS + 500)
    output_path = tmp_path / "episode.mp3"

    with patch("plugins.media.src.tts_generate.OpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = MagicMock()
        mock_cls.return_value = mock_client

        generate_audio(long_script, "alloy", "tts-1-hd", output_path)

    called_input = mock_client.audio.speech.create.call_args.kwargs["input"]
    assert len(called_input) == MAX_TTS_CHARS


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
