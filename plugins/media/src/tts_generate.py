import json
import re
import shutil
import sys
from pathlib import Path
from openai import OpenAI

MAX_TTS_CHARS = 4096


def split_into_chunks(text: str, max_chars: int = MAX_TTS_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_chars:
            chunks.append(text)
            break
        segment = text[:max_chars]
        last_boundary = None
        for m in re.finditer(r'\. (?=[A-Z])', segment):
            last_boundary = m.start() + 1  # position just after the period
        if last_boundary:
            chunks.append(text[:last_boundary].strip())
            text = text[last_boundary:].strip()
        else:
            chunks.append(segment)
            text = text[max_chars:]
    return [c for c in chunks if c]


def generate_audio(script: str, voice: str, model: str, output_path: Path) -> None:
    client = OpenAI()
    chunks = split_into_chunks(script)
    if len(chunks) == 1:
        response = client.audio.speech.create(model=model, voice=voice, input=chunks[0])
        response.stream_to_file(str(output_path))
        return
    chunks_dir = output_path.parent / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    chunk_paths = []
    try:
        for i, chunk in enumerate(chunks):
            chunk_path = chunks_dir / f"chunk_{i:03d}.mp3"
            response = client.audio.speech.create(model=model, voice=voice, input=chunk)
            response.stream_to_file(str(chunk_path))
            chunk_paths.append(chunk_path)
        with open(output_path, "wb") as outfile:
            for path in chunk_paths:
                outfile.write(path.read_bytes())
    finally:
        shutil.rmtree(chunks_dir, ignore_errors=True)


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
