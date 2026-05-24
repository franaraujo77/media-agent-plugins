---
name: story-photo
description: >
  Creates Instagram photo Stories as 1080×1920 (9:16) HTML previews exported to
  PNG, then publishes via the Meta Graph API. Reuses the carousel skill's brand
  setup and design system, but tuned for a single full-screen vertical frame.
  Use whenever the user asks for an "Instagram story", "story de foto",
  "photo story", "stories", or any 9:16 static Instagram post — even if they
  don't explicitly say "skill".
---

# Instagram Story (Photo) Generator

Generates a single 1080×1920px PNG ready to publish as an Instagram photo Story.
Same design system as the carousel skill, but one full-bleed vertical frame.

---

## Step 1: Install the publishing script (one-time)

If `~/InstagramAI/scripts/publish_story_photo.py` does not exist, write the
script in the **"Embedded script"** section below to that path. Confirm
`~/InstagramAI/.env` exists first (run `/instagram-setup` if not).

```bash
test -f /Users/francisaraujo/InstagramAI/scripts/publish_story_photo.py \
  || echo "MISSING — install from SKILL.md"
```

---

## Step 2: Collect Brand Details

If brand details aren't already known from a prior carousel session, ask:

1. **Brand name / Instagram handle** — shown subtly in corner
2. **Primary brand color** (hex) — full palette derived from it
3. **Font preference** — see typography table in the carousel skill
4. **Tone** — professional, casual, bold, etc.
5. **Background image (optional)** — file path; embedded as base64
6. **Idioma** — default Português (BR)
7. **Story purpose** — announcement, quote, link teaser, behind-the-scenes, poll/question, swipe-up CTA

If a carousel was just created in this session, **reuse its palette and fonts** without asking again.

---

## Step 3: Story Layout Rules

### Format
- **Aspect ratio: 9:16** (1080×1920px output, 360×640 in preview)
- Single frame — no progress bar, no swipe arrow
- Safe zones: keep critical text/CTAs in the **center 60%** vertically (Instagram UI overlays the top ~14% and bottom ~14%)

### Layout zones (vertical)

| Zone | Y range | Content |
|------|---------|---------|
| Top safe (IG profile chrome) | 0–14% | Avoid critical content |
| Hook zone | 14–35% | Brand mark, small tag |
| Hero zone | 35–70% | Main headline, key visual, central focus |
| CTA zone | 70–86% | Call to action, link sticker placeholder, swipe-up hint |
| Bottom safe (IG reply bar) | 86–100% | Avoid critical content |

### Story formats

| Format | When to use |
|---|---|
| **Big quote** | Standalone insight, customer testimonial, statistic |
| **Announcement** | Product launch, event, content drop |
| **Carousel teaser** | "Novo carrossel no feed →" — drives traffic to a post |
| **Poll/Question** | Engagement — leave space for IG sticker overlay |
| **Behind-the-scenes** | Photo-led, minimal copy |
| **Link sticker CTA** | "Acessa pelo link da bio" or sticker pointer |

---

## Step 4: Background Image Handling

Same rules as the carousel skill:

1. **NEVER use relative paths** — always base64 `data:` URI
2. **NEVER use `background: url(filepath)`** — use `<img>` tag with `object-fit: cover`
3. **ALWAYS generate HTML via Python `Path.write_text()`** — never shell heredocs
4. **Detect actual MIME with `file` command** before encoding

```python
import base64
from pathlib import Path
img_path = Path("/path/to/bg.jpg")
mime = "image/jpeg"  # verify with: file /path/to/bg.jpg
b64 = base64.b64encode(img_path.read_bytes()).decode()
data_uri = f"data:{mime};base64,{b64}"
```

Embed with semi-transparent overlay (`rgba(0,0,0,0.45)` on dark text,
`rgba(255,255,255,0.35)` on light text) so text stays readable.

---

## Step 5: Generate HTML, Review, Export

1. Build HTML template (see carousel SKILL for component reference)
2. Show preview, ask: **"Quer ajustar algo antes de exportar?"**
3. Iterate on copy/colors as needed
4. Export with Playwright using `device_scale_factor=3` to render 360×640 layout as 1080×1920 PNG

Export pattern (write as `export_story.py` alongside the HTML):

```python
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

INPUT_HTML = Path("/Users/francisaraujo/InstagramAI/story-photo/story.html")
OUTPUT = Path("/Users/francisaraujo/InstagramAI/story-photo/story.png")
VIEW_W, VIEW_H = 360, 640
SCALE = 1080 / 360

async def export():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(
            viewport={"width": VIEW_W, "height": VIEW_H},
            device_scale_factor=SCALE,
        )
        await page.set_content(INPUT_HTML.read_text(encoding="utf-8"), wait_until="networkidle")
        await page.wait_for_timeout(3000)
        await page.evaluate("""() => {
            document.body.style.cssText = 'padding:0;margin:0;background:#000;';
            const f = document.querySelector('.story-frame');
            f.style.cssText += ';border-radius:0;box-shadow:none;margin:0;';
        }""")
        await page.wait_for_timeout(400)
        await page.screenshot(
            path=str(OUTPUT),
            clip={"x": 0, "y": 0, "width": VIEW_W, "height": VIEW_H},
        )
        await browser.close()

asyncio.run(export())
```

---

## Step 6: Publish

```bash
python3 ~/InstagramAI/scripts/publish_story_photo.py \
  --image ~/InstagramAI/story-photo/story.png --dry-run

# Remove --dry-run to publish
```

Stories don't take captions.

---

## Embedded script

Write the following content to `~/InstagramAI/scripts/publish_story_photo.py`
during install:

```python
"""
publish_story_photo.py — Publish a photo as an Instagram Story.
Uses the Instagram Login flow (graph.instagram.com).
Installed by the story-photo skill.
"""
import argparse
import os
import sys
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


def host_image(path: str) -> str:
    with open(path, "rb") as f:
        resp = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (Path(path).name, f, "image/png")},
            timeout=60,
        )
    url = resp.text.strip()
    if not url.startswith("https://"):
        raise RuntimeError(f"Upload failed: {url}")
    print(f"  Hosted: {url}")
    return url


def create_story_container(image_url: str) -> str:
    resp = requests.post(
        f"{BASE_URL}/{IG_USER_ID}/media",
        data={"access_token": TOKEN, "image_url": image_url, "media_type": "STORIES"},
        timeout=60,
    )
    result = resp.json()
    if "id" not in result:
        raise RuntimeError(f"Container error: {result}")
    print(f"  Container: {result['id']}")
    return result["id"]


def wait_ready(container_id: str, max_polls: int = 12) -> bool:
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


def run(image: str, dry_run: bool = False):
    if not IG_USER_ID or not TOKEN:
        print("ERROR: Credentials not found. Run /instagram-setup first.")
        sys.exit(1)
    if not Path(image).exists():
        print(f"ERROR: Image not found: {image}")
        sys.exit(1)

    print(f"\nPublishing photo story: {image}")
    if dry_run:
        print("[DRY RUN] All OK. Remove --dry-run to publish.")
        return

    print("\nStep 1/3 - Hosting image...")
    url = host_image(image)
    print("\nStep 2/3 - Creating story container...")
    container_id = create_story_container(url)
    print("\nStep 3/3 - Publishing...")
    if not wait_ready(container_id):
        print("ERROR: Timeout during processing.")
        sys.exit(1)
    media_id = publish(container_id)
    print(f"\nStory published! Media ID: {media_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.image, args.dry_run)
```

---

## Design Principles

1. **One frame, one idea** — stories are not multi-message
2. **Center your message** — top 14% and bottom 14% are owned by Instagram UI
3. **Big type** — base headline at 36–48px because viewers scroll fast
4. **Brand mark small** — top-left, never compete with the message
5. **CTA at 78–82% Y** — clear of the reply bar but visible
6. **Reuse carousel palette** — keep brand cohesion across formats
