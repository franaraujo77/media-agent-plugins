---
name: reel
description: >
  Publishes a video as an Instagram Reel (9:16, 3–90s) with caption, hashtags,
  and optional cover image via the Meta Graph API. Optionally merges a
  separate audio track into the video before publish. Validates the file
  locally, hosts it publicly, then creates and publishes the Reel container.
  Use whenever the user asks to "publicar reel", "post reel", "create a reel",
  "reel com música", or hands over a vertical video meant for the Reels tab/feed.
---

# Instagram Reel Publisher

Validates and publishes a video file as an Instagram Reel. Unlike Stories,
Reels stay on the profile permanently and support captions/hashtags.
Supports optional audio-track merging (e.g., adding a music bed) before upload.

---

## Step 1: Install the publishing script (one-time)

If `~/InstagramAI/scripts/publish_reel.py` does not exist, write the script in
the **"Embedded script"** section below to that path.

```bash
test -f /Users/francisaraujo/InstagramAI/scripts/publish_reel.py \
  || echo "MISSING — install from SKILL.md"
```

Requires `ffmpeg`/`ffprobe`:

```bash
which ffmpeg ffprobe || brew install ffmpeg
```

---

## Step 2: Collect Inputs

Ask the user for:

1. **Video file path** — `.mp4` preferred (H.264 + AAC)
2. **Caption** — required. Never publish a Reel without one
3. **Hashtags** — 5–15 relevant tags, will be appended to caption
4. **Optional audio file** — `.mp3`/`.aac`/`.wav` to merge over the video
5. **Cover image (optional)** — 1080×1920 PNG/JPG for the thumbnail
6. **Share to feed?** — default `true`
7. **Action** — dry-run or publish

---

## Step 3: Audio Merge (optional)

When `--audio` is supplied, ffmpeg replaces the video's audio track:

```bash
ffmpeg -i video.mp4 -i music.mp3 \
  -map 0:v -map 1:a \
  -c:v copy -c:a aac -b:a 192k -ar 48000 \
  -shortest \
  merged.mp4
```

**Important:** The Instagram Graph API does NOT support music stickers or
licensed audio from Meta's catalog. Audio must be baked into the video file.
For copyright safety, use royalty-free music or your own original audio.

---

## Step 4: Validate the Video

| Spec | Required |
|------|----------|
| Aspect ratio | 9:16 (1080×1920 ideal) |
| Duration | 3–90 seconds |
| Container | MP4 |
| Video codec | H.264, progressive scan |
| Audio codec | AAC, 48kHz |
| Max file size | 1 GB |
| Min bitrate | 5 Mbps recommended |

Re-encode template for fixing codec/aspect issues:

```bash
ffmpeg -i input.mp4 \
  -c:v libx264 -preset slow -crf 21 -profile:v high -level 4.0 \
  -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black" \
  -c:a aac -b:a 192k -ar 48000 \
  -movflags +faststart \
  output.mp4
```

---

## Step 5: Caption Strategy

If the user provides a topic instead of a finished caption, generate one:

1. **Hook line (≤8 words)** — appears in the truncated preview
2. **Blank line**
3. **Context / payoff (1–3 sentences)**
4. **CTA** — "Salva pra ler depois", "Marca alguém"
5. **Blank line**
6. **Hashtags** — 5–15, mix broad + niche

Total ≤2200 chars. Show caption for approval before publishing.

---

## Step 6: Host + Publish

1. POST `/{ig-user-id}/media` with `video_url`, `media_type=REELS`, `caption`,
   optional `cover_url`, `share_to_feed`
2. Poll `/{creation_id}?fields=status_code` (5s × 60 = up to 5 min)
3. POST `/{ig-user-id}/media_publish` with `creation_id`
4. Fetch permalink to confirm

---

## Step 7: Run

```bash
# Validate only
python3 ~/InstagramAI/scripts/publish_reel.py \
  --video reel.mp4 --caption "Hook\n\nPayoff\n\n#tags" --dry-run

# Validate + publish
python3 ~/InstagramAI/scripts/publish_reel.py \
  --video reel.mp4 --caption "Hook\n\nPayoff\n\n#tags"

# With audio merge + cover
python3 ~/InstagramAI/scripts/publish_reel.py \
  --video reel.mp4 --audio music.mp3 --cover thumb.jpg \
  --caption "Hook\n\nPayoff\n\n#tags"
```

---

## Embedded script

Write the following content to `~/InstagramAI/scripts/publish_reel.py`
during install:

```python
"""
publish_reel.py — Publish a video as an Instagram Reel.
Uses the Instagram Login flow (graph.instagram.com).
Optionally merges a separate audio track into the video before publish.
Installed by the reel skill.
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
    out = Path(tempfile.gettempdir()) / f"reel_merged_{int(time.time())}.mp4"
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
         "-show_entries", "format=duration,size,bit_rate",
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
    if not (3 <= duration <= 90):
        issues.append(f"Duration {duration:.1f}s is outside 3–90s")
    if size_mb > 1024:
        issues.append(f"Size {size_mb:.1f}MB exceeds 1GB")
    if codec != "h264":
        issues.append(f"Codec {codec} is not h264")

    print(f"  {w}x{h}, {duration:.1f}s, {size_mb:.1f}MB, codec={codec}")
    if issues:
        print("  Issues:")
        for issue in issues:
            print(f"    - {issue}")
        return {"ok": False, "issues": issues}
    return {"ok": True}


def host_file(path: str, mime: str = "video/mp4") -> str:
    with open(path, "rb") as f:
        resp = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (Path(path).name, f, mime)},
            timeout=600,
        )
    url = resp.text.strip()
    if not url.startswith("https://"):
        raise RuntimeError(f"Upload failed: {url}")
    print(f"  Hosted: {url}")
    return url


def create_reel_container(video_url: str, caption: str, cover_url: str = None,
                          share_to_feed: bool = True) -> str:
    payload = {
        "access_token": TOKEN,
        "video_url": video_url,
        "media_type": "REELS",
        "caption": caption,
        "share_to_feed": "true" if share_to_feed else "false",
    }
    if cover_url:
        payload["cover_url"] = cover_url
    resp = requests.post(f"{BASE_URL}/{IG_USER_ID}/media", data=payload, timeout=60)
    result = resp.json()
    if "id" not in result:
        raise RuntimeError(f"Container error: {result}")
    print(f"  Container: {result['id']}")
    return result["id"]


def wait_ready(container_id: str, max_polls: int = 60) -> bool:
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


def fetch_permalink(media_id: str) -> str:
    resp = requests.get(
        f"{BASE_URL}/{media_id}",
        params={"fields": "permalink", "access_token": TOKEN},
        timeout=15,
    )
    return resp.json().get("permalink", "")


def run(video: str, caption: str, audio: str = None, cover: str = None,
        share_to_feed: bool = True, dry_run: bool = False,
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
    if cover and not Path(cover).exists():
        print(f"ERROR: Cover not found: {cover}")
        sys.exit(1)
    if len(caption) > 2200:
        print(f"ERROR: Caption is {len(caption)} chars, max 2200.")
        sys.exit(1)

    print(f"\nPublishing Reel: {video}")
    print(f"Caption: {caption[:80]}{'...' if len(caption) > 80 else ''}")

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

    print("\nStep 1/4 - Hosting video (may take a moment)...")
    video_url = host_file(target_video, "video/mp4")

    cover_url = None
    if cover:
        print("\nStep 2/4 - Hosting cover image...")
        cover_url = host_file(cover, "image/jpeg")
    else:
        print("\nStep 2/4 - No cover provided, skipping...")

    print("\nStep 3/4 - Creating Reel container...")
    container_id = create_reel_container(video_url, caption, cover_url, share_to_feed)

    print("\nStep 4/4 - Waiting for processing (Reels take 60–180s)...")
    if not wait_ready(container_id):
        print("ERROR: Timeout during processing.")
        sys.exit(1)
    media_id = publish(container_id)
    print(f"\nReel published! Media ID: {media_id}")
    permalink = fetch_permalink(media_id)
    if permalink:
        print(f"Permalink: {permalink}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--caption", required=True)
    parser.add_argument("--audio", help="Optional audio file to merge over the video")
    parser.add_argument("--cover", help="Optional cover image (1080×1920 PNG/JPG)")
    parser.add_argument("--no-share-to-feed", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args()
    run(args.video, args.caption, args.audio, args.cover,
        share_to_feed=not args.no_share_to_feed,
        dry_run=args.dry_run, skip_validation=args.skip_validation)
```

---

## Design Principles

1. **Captions are mandatory** — never publish a Reel without one
2. **Audio merge is opt-in** — never modify the user's original file
3. **Replace audio, don't mix** — `-map 1:a` cleanly swaps the track
4. **Use royalty-free or original audio** — Graph API can't use IG's licensed catalog
5. **Validate locally first** — saves API quota
6. **Cover image worth the effort** — first frame is often a bad thumbnail
7. **Poll patiently** — Reels processing is 2–3x slower than Stories
