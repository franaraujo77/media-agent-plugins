---
name: story-video
description: >
  Publishes a video as an Instagram Story (9:16, up to 60s) via the Meta Graph
  API. Optionally merges a separate audio track into the video before publish.
  Validates the file locally (aspect ratio, duration, codec), hosts it
  publicly, then creates and publishes the Story container. Use whenever the
  user asks to "post story video", "publicar story em vídeo", "story
  animado/animation", "story com música", or hands over an .mp4/.mov for
  Instagram Stories.
---

# Instagram Story (Video) Publisher

Validates and publishes a video file as an Instagram Story. No design/preview
step — the video itself is the asset. Supports optional audio-track merging
(e.g., adding a music bed to a silent screen recording) before upload.

---

## Step 1: Install the publishing script (one-time)

If `~/InstagramAI/scripts/publish_story_video.py` does not exist, write the
script in the **"Embedded script"** section below to that path.

```bash
test -f /Users/francisaraujo/InstagramAI/scripts/publish_story_video.py \
  || echo "MISSING — install from SKILL.md"
```

Also requires `ffmpeg`/`ffprobe` on PATH for validation and audio merge:

```bash
which ffmpeg ffprobe || brew install ffmpeg
```

---

## Step 2: Collect Inputs

Ask the user for:

1. **Video file path** — `.mp4` or `.mov` preferred (H.264 + AAC)
2. **Optional audio file** — `.mp3`, `.aac`, or `.wav` to merge over the video.
   Original video audio will be **replaced** by the new track.
3. **Action** — dry-run only, or publish

---

## Step 3: Audio Merge (optional)

When a separate audio track is supplied via `--audio`, the script merges it
into the video using ffmpeg before validation:

```bash
ffmpeg -i video.mp4 -i music.mp3 \
  -map 0:v -map 1:a \
  -c:v copy -c:a aac -b:a 192k -ar 48000 \
  -shortest \
  merged.mp4
```

- `-shortest` trims the output to the shorter of the two streams (typical: video is shorter)
- `-c:v copy` keeps the video stream as-is — no re-encoding
- Output goes to a temp file; original input is never modified

**Important:** The Instagram Graph API does NOT support music stickers or
licensed audio from Meta's catalog. Audio must be baked into the video file.

---

## Step 4: Validate the Video

After any merge, ffprobe validates against Story requirements:

| Spec | Required |
|------|----------|
| Aspect ratio | 9:16 (1080×1920 ideal; ratio ~0.55–0.57) |
| Duration | 3–60 seconds |
| Container | MP4 or MOV |
| Video codec | H.264 |
| Audio codec | AAC |
| Max file size | 100MB |

If validation fails, the script reports the issues and exits unless
`--skip-validation` is passed.

---

## Step 5: Host + Publish

`catbox.moe` hosts files publicly (up to 200MB). Warn the user if the video
is sensitive.

API flow:
1. POST `/{ig-user-id}/media` with `video_url`, `media_type=STORIES`
2. Poll `/{creation_id}?fields=status_code` (5s × 24 = up to 2 min)
3. POST `/{ig-user-id}/media_publish` with `creation_id`

---

## Step 6: Run

```bash
# Validate only
python3 ~/InstagramAI/scripts/publish_story_video.py \
  --video clip.mp4 --dry-run

# Validate + publish
python3 ~/InstagramAI/scripts/publish_story_video.py \
  --video clip.mp4

# With audio merge
python3 ~/InstagramAI/scripts/publish_story_video.py \
  --video clip.mp4 --audio song.mp3
```

---

## Embedded script

Write the following content to `~/InstagramAI/scripts/publish_story_video.py`
during install:

```python
"""
publish_story_video.py — Publish a video as an Instagram Story.
Uses the Instagram Login flow (graph.instagram.com).
Optionally merges a separate audio track into the video before publish.
Installed by the story-video skill.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

script_dir = Path(__file__).resolve().parent
for candidate in [script_dir.parent / ".env", script_dir / ".env"]:
    if candidate.exists():
        load_dotenv(candidate)
        break

IG_USER_ID = os.getenv("INSTAGRAM_USER_ID")
TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
API_VERSION = os.getenv("META_API_VERSION", "v19.0")
BASE_URL = f"{os.getenv('META_API_BASE', 'https://graph.instagram.com')}/{API_VERSION}"


def merge_audio(video: str, audio: str) -> str:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not on PATH — install with: brew install ffmpeg")
    out = Path(tempfile.gettempdir()) / f"story_merged_{int(time.time())}.mp4"
    print(f"  Merging audio into video → {out}")
    subprocess.run(
        ["ffmpeg", "-y", "-i", video, "-i", audio,
         "-map", "0:v", "-map", "1:a",
         "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-shortest", str(out)],
        check=True, capture_output=True,
    )
    return str(out)


def validate_video(path: str) -> dict:
    if not shutil.which("ffprobe"):
        print("WARN: ffprobe not installed — skipping local validation.")
        return {}
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,codec_name,r_frame_rate",
         "-show_entries", "format=duration,size",
         "-of", "json", path],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(out.stdout)
    stream = data.get("streams", [{}])[0]
    fmt = data.get("format", {})
    w, h = stream.get("width", 0), stream.get("height", 0)
    duration = float(fmt.get("duration", 0))
    size_mb = int(fmt.get("size", 0)) / (1024 * 1024)
    codec = stream.get("codec_name", "")

    issues = []
    if not (0.55 <= w / h <= 0.57):
        issues.append(f"Aspect ratio {w}x{h} is not 9:16")
    if not (3 <= duration <= 60):
        issues.append(f"Duration {duration:.1f}s is outside 3–60s")
    if size_mb > 100:
        issues.append(f"Size {size_mb:.1f}MB exceeds 100MB")
    if codec != "h264":
        issues.append(f"Codec {codec} is not h264")

    print(f"  {w}x{h}, {duration:.1f}s, {size_mb:.1f}MB, codec={codec}")
    if issues:
        print("  Issues:")
        for issue in issues:
            print(f"    - {issue}")
        return {"ok": False, "issues": issues}
    return {"ok": True}


def host_video(path: str) -> str:
    with open(path, "rb") as f:
        resp = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (Path(path).name, f, "video/mp4")},
            timeout=300,
        )
    url = resp.text.strip()
    if not url.startswith("https://"):
        raise RuntimeError(f"Upload failed: {url}")
    print(f"  Hosted: {url}")
    return url


def create_story_container(video_url: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/{IG_USER_ID}/media",
        data={"access_token": TOKEN, "video_url": video_url, "media_type": "STORIES"},
        timeout=60,
    )
    result = resp.json()
    if "id" not in result:
        raise RuntimeError(f"Container error: {result}")
    print(f"  Container: {result['id']}")
    return result["id"]


def wait_ready(container_id: str, max_polls: int = 24) -> bool:
    for i in range(max_polls):
        resp = requests.get(
            f"{BASE_URL}/{container_id}",
            params={"fields": "status_code", "access_token": TOKEN},
            timeout=15,
        )
        status = resp.json().get("status_code", "")
        if status == "FINISHED":
            return True
        if status == "ERROR":
            raise RuntimeError(f"Container error: {resp.json()}")
        print(f"  Processing... {i * 5}s ({status})")
        time.sleep(5)
    return False


def publish(container_id: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/{IG_USER_ID}/media_publish",
        data={"access_token": TOKEN, "creation_id": container_id},
        timeout=30,
    )
    result = resp.json()
    if "id" not in result:
        raise RuntimeError(f"Publish error: {result}")
    return result["id"]


def run(video: str, audio: str = None, dry_run: bool = False,
        skip_validation: bool = False):
    if not IG_USER_ID or not TOKEN:
        print("ERROR: Credentials not found. Run /instagram-setup first.")
        sys.exit(1)
    if not Path(video).exists():
        print(f"ERROR: Video not found: {video}")
        sys.exit(1)
    if audio and not Path(audio).exists():
        print(f"ERROR: Audio not found: {audio}")
        sys.exit(1)

    print(f"\nPublishing video story: {video}")

    target_video = video
    if audio:
        print("\nStep 0 - Merging audio track...")
        target_video = merge_audio(video, audio)

    if not skip_validation:
        print("\nValidating video...")
        result = validate_video(target_video)
        if result.get("ok") is False:
            print("\nVideo failed local validation. Fix the issues above and retry,")
            print("or pass --skip-validation to attempt upload anyway.")
            sys.exit(1)

    if dry_run:
        print("\n[DRY RUN] All OK. Remove --dry-run to publish.")
        return

    print("\nStep 1/3 - Hosting video (may take a moment)...")
    url = host_video(target_video)
    print("\nStep 2/3 - Creating story container...")
    container_id = create_story_container(url)
    print("\nStep 3/3 - Waiting for processing + publishing...")
    if not wait_ready(container_id):
        print("ERROR: Timeout during processing.")
        sys.exit(1)
    media_id = publish(container_id)
    print(f"\nStory video published! Media ID: {media_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--audio", help="Optional audio file to merge over the video")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args()
    run(args.video, args.audio, args.dry_run, args.skip_validation)
```

---

## Design Principles

1. **Validate before upload** — fail fast locally, don't burn API calls
2. **Audio merge is opt-in** — never modify the user's original file
3. **Replace audio, don't mix** — `-map 1:a` cleanly swaps the track; mixing requires more args
4. **Never silently transform user files** — show issues, suggest the fix
5. **Warn about public hosting** — catbox.moe is public
6. **Poll patiently** — video containers take 30–90s
