import json
import sys
from pathlib import Path
from openai import OpenAI

MAX_TTS_CHARS = 4096


def generate_audio(script: str, voice: str, model: str, output_path: Path) -> None:
    if len(script) > MAX_TTS_CHARS:
        script = script[:MAX_TTS_CHARS]
    client = OpenAI()
    response = client.audio.speech.create(
        model=model,
        voice=voice,
        input=script,
    )
    response.stream_to_file(str(output_path))


def run(config_path: str) -> None:
    script_path = Path("output/script.txt")
    if not script_path.exists():
        sys.exit("Error: output/script.txt not found. Run script-generate first.")

    config = json.loads(Path(config_path).read_text())
    tts = config["tts"]
    script = script_path.read_text()
    Path("output").mkdir(exist_ok=True)
    output_path = Path("output/episode.mp3")
    generate_audio(script, tts["voice"], tts["model"], output_path)
    print("Generated audio → output/episode.mp3")


if __name__ == "__main__":
    run(sys.argv[1])
