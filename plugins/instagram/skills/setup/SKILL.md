---
name: setup
description: >
  Configures the complete integration between the AI agent and Instagram for automatic
  publishing of carousels and posts. Guides the user step by step to obtain
  Meta API credentials, saves everything in the right place, and tests the connection.
  Use when the user wants to connect the AI agent to Instagram for the first time,
  or when they say "I want to publish on Instagram", "configure instagram", "setup instagram".
---

# Setup Instagram — Automatic Integration with AI

Configures everything needed to publish posts and carousels automatically
to Instagram directly through the AI agent, without opening Canva, without copy-pasting anything.

---

## What this skill does

1. Checks the prerequisites
2. Guides through obtaining the Meta API token (step by step with screenshots)
3. Automatically discovers the Instagram Business ID
4. Saves the credentials in the right place
5. Installs the publishing script
6. Tests the connection live
7. Confirms that everything is working

**Estimated time: 10 minutes**

---

## STEP 0 — Welcome and prerequisites

When invoked, introduce yourself like this:

> Hi! I'll set everything up so you can publish to Instagram automatically through the AI agent.
> I need about 10 minutes of your time and some information that only you have access to.
> Let's do this together — I'll guide you through each step.

Ask the user:

**"Before we start, confirm for me:"**

1. Is your Instagram account **Professional** (Business or Creator)?
   - If you don't know: Settings → Account → Account type
   - If it's personal: instruct them to convert to Creator (free, no followers lost)

2. Do you have a **Facebook Page** linked to Instagram?
   - If not: instruct them to create a basic Facebook page

3. Do you have access to the **Facebook email/password** that manages this page?

If all yes → proceed to Step 1
If any no → resolve the item before continuing

---

## STEP 1 — Create a Meta developer account (if needed)

Instruct the user:

> "Let's access the Meta developer dashboard. It's free."

**Steps:**
1. Open in browser: `https://developers.facebook.com`
2. Click **"Get Started"** or **"Log In"** (use the Facebook account that has the Page)
3. If asked to verify identity, confirm by phone
4. Once you reach the dashboard, ask: **"Did you get to the dashboard? Tell me what you see on the screen."**

---

## STEP 2 — Access the Graph API Explorer

Instruct the user:

> "Now we'll use a Meta tool called Graph API Explorer. This is where we get the token."

**Steps:**
1. Visit: `https://developers.facebook.com/tools/explorer`
2. In the top-right corner, under **"Meta App"**, select an existing app
   - If you don't have one: click "Create App" → type **Business** → fill in any name (e.g. "MyBot") → confirm
3. Just below, under **"User or Page"**, click and select **your Facebook Page** (not "User")
4. Ask: **"Did you select the Page? What name appeared?"**

---

## STEP 3 — Add required permissions

Instruct the user:

> "Now let's add the permissions to publish to Instagram. There are 3 we need."

**In the Graph API Explorer:**
1. Click **"Add a Permission"**
2. Search and add them one by one:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
3. Click **"Generate Access Token"**
4. A Facebook window will open asking for authorization — click **Continue** and **OK** on everything
5. The token will appear in the text field (starts with `EAAU...`)
6. Instruct: **"Copy that whole token and paste it here for me"**

> ⚠️ Warn: "Do not share this token with anyone. It gives access to your account."

---

## STEP 4 — Receive and validate the token

When the user pastes the token:

1. Check that it starts with `EAA` and has more than 100 characters
2. Test immediately with an API call:

```bash
node -e "
const TOKEN = 'USER_TOKEN_HERE';
fetch('https://graph.facebook.com/v19.0/me/accounts?fields=id,name,instagram_business_account&access_token=' + TOKEN)
  .then(r => r.json())
  .then(d => console.log(JSON.stringify(d, null, 2)));
"
```

3. If it returns data → token valid, identify which account is the user's Instagram
4. If it returns an error → diagnose the problem:
   - `OAuthException` → invalid token, ask to generate again
   - `permissions` → some permission was not added, go back to Step 3

---

## STEP 5 — Identify the Instagram Business ID

After validating the token, from the API result:

1. Show the pages found in a friendly format:

```
I found these pages linked to your account:

1. [Page Name]    → Instagram ID: XXXXXXXXX
2. [Other Page]   → no Instagram linked

Which one do you want to use for publishing?
```

2. Confirm with the user which account to use
3. Store: `PAGE_TOKEN` and `INSTAGRAM_BUSINESS_ID`

---

## STEP 6 — Save the credentials

Determine where to save based on what exists on the user's computer:

**Automatic check (use Glob/Bash):**
```bash
# Check if the AIOS project exists
ls "/Users/*/my-project-aios/squads" 2>/dev/null
ls "/Users/*/InstagramAI" 2>/dev/null
```

**Scenario A — User has the AIOS project:**
Save in: `[found-folder]/squads/aios-team/.env`

**Scenario B — User does not have the AIOS project:**
Create folder and save in: `/Users/[user]/InstagramAI/.env`

**.env content:**
```
# Instagram / Meta — Generated by setup
INSTAGRAM_BUSINESS_ID=[ID found]
FACEBOOK_PAGE_ID=[Page ID found]
INSTAGRAM_ACCESS_TOKEN=[user's token]
META_API_VERSION=v19.0
```

Confirm: **"Credentials saved at [path]. Did you note this path? It's important!"**

---

## STEP 7 — Install the publishing script

Check if `publish_instagram.py` already exists on the system:

```bash
find "/Users" -name "publish_instagram.py" 2>/dev/null | head -5
```

**If it doesn't exist**, create at `[same folder as .env]/scripts/publish_instagram.py`:

```python
"""
publish_instagram.py — Automatic Instagram publishing via Meta Graph API
Generated by the setup-instagram skill of the AI agent
"""
import argparse, os, sys, time, requests
from pathlib import Path
from dotenv import load_dotenv

# Find the .env automatically (goes up to 3 levels)
script_dir = Path(__file__).parent
for i in range(4):
    env_file = script_dir / (".." * i).rstrip("/") / ".env" if i > 0 else script_dir.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        break

IG_ID      = os.getenv("INSTAGRAM_BUSINESS_ID")
PAGE_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
BASE_URL   = f"https://graph.facebook.com/{os.getenv('META_API_VERSION', 'v19.0')}"


def host_image(image_path: str) -> str:
    """Host image at a public URL via catbox.moe"""
    with open(image_path, "rb") as f:
        resp = requests.post(
            "https://catbox.moe/user/api.php",
            data={"reqtype": "fileupload"},
            files={"fileToUpload": (Path(image_path).name, f, "image/png")},
            timeout=60,
        )
    url = resp.text.strip()
    if not url.startswith("https://"):
        raise RuntimeError(f"Upload failed: {url}")
    print(f"  Hosted: {url}")
    return url


def create_media_container(image_path: str) -> str:
    resp = requests.post(f"{BASE_URL}/{IG_ID}/media", data={
        "access_token": PAGE_TOKEN,
        "image_url": host_image(image_path),
        "is_carousel_item": "true",
    }, timeout=60)
    result = resp.json()
    if "id" not in result:
        raise RuntimeError(f"Container error: {result}")
    print(f"  Container: {result['id']}")
    return result["id"]


def create_carousel(media_ids: list, caption: str) -> str:
    resp = requests.post(f"{BASE_URL}/{IG_ID}/media", data={
        "access_token": PAGE_TOKEN,
        "media_type": "CAROUSEL",
        "children": ",".join(media_ids),
        "caption": caption,
    }, timeout=30)
    result = resp.json()
    if "id" not in result:
        raise RuntimeError(f"Carousel error: {result}")
    print(f"  Carousel: {result['id']}")
    return result["id"]


def wait_ready(container_id: str) -> bool:
    for i in range(12):
        resp = requests.get(f"{BASE_URL}/{container_id}",
            params={"fields": "status_code", "access_token": PAGE_TOKEN}, timeout=15)
        status = resp.json().get("status_code", "")
        if status == "FINISHED":
            return True
        if status == "ERROR":
            raise RuntimeError(f"Container with error: {resp.json()}")
        print(f"  Processing... {i*5}s")
        time.sleep(5)
    return False


def publish(container_id: str) -> str:
    resp = requests.post(f"{BASE_URL}/{IG_ID}/media_publish", data={
        "access_token": PAGE_TOKEN,
        "creation_id": container_id,
    }, timeout=30)
    result = resp.json()
    if "id" not in result:
        raise RuntimeError(f"Publish error: {result}")
    return result["id"]


def run(images: list, caption: str, dry_run: bool = False):
    if not IG_ID or not PAGE_TOKEN:
        print("ERROR: Credentials not found. Run /setup-instagram first.")
        sys.exit(1)
    if len(images) < 2:
        print("ERROR: Minimum 2 images for carousel.")
        sys.exit(1)
    if len(images) > 10:
        print("ERROR: Maximum 10 images.")
        sys.exit(1)

    print(f"\nPublishing {len(images)} slides to Instagram...")
    if dry_run:
        print("[DRY RUN] All OK. Remove --dry-run to publish.")
        return

    print("\nStep 1/3 - Creating containers...")
    ids = [create_media_container(img) for img in images]

    print("\nStep 2/3 - Assembling carousel...")
    carousel_id = create_carousel(ids, caption)

    print("\nStep 3/3 - Publishing...")
    if not wait_ready(carousel_id):
        print("ERROR: Timeout during processing.")
        sys.exit(1)

    post_id = publish(carousel_id)
    print(f"\nPublished successfully!")
    print(f"Post ID: {post_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", nargs="+", required=True)
    parser.add_argument("--caption", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.images, args.caption, args.dry_run)
```

**Install dependencies:**
```bash
pip install requests python-dotenv -q
```

---

## STEP 8 — Live connection test

Run the final test:

```bash
node -e "
const TOKEN = 'SAVED_TOKEN';
const IG_ID = 'SAVED_IG_ID';
fetch('https://graph.facebook.com/v19.0/' + IG_ID + '?fields=id,name,username&access_token=' + TOKEN)
  .then(r => r.json())
  .then(d => console.log(JSON.stringify(d, null, 2)));
"
```

If it returns `username`, show the user:

```
Connection tested successfully!

Connected account: @[username]
Name: [name]
ID: [id]

Everything is ready to publish automatically.
```

---

## STEP 9 — Final confirmation and next steps

Show the full summary:

```
Setup complete!

What was configured:
  Credentials saved at:  [.env path]
  Publishing script:     [publish_instagram.py path]
  Connected account:     @[username]

How to use it now:

1. Create carousel:
   /carousel

2. Export the slides:
   python export_slides.py

3. Publish to Instagram:
   python publish_instagram.py --images slides/*.png --caption "your caption"

Or ask for everything at once:
   "Create a carousel about [topic] and publish it to my Instagram"
```

---

## Common error diagnosis

| Error | Cause | Solution |
|------|-------|---------|
| `OAuthException #200` | Missing permissions | Go back to Graph API Explorer and add the 3 permissions |
| `OAuthException #100 image_url required` | API does not accept local file | The script already handles this via catbox.moe |
| `Invalid OAuth access token` | Expired token | Generate a new token in Graph API Explorer |
| `Instagram account not found` | Account is not Business/Creator | Convert the account in Settings → Account |
| `Pages not found` | Page not linked to Instagram | Link in Instagram Settings → Account → Linked Page |

---

## Important note about the token

The token generated in the Graph API Explorer **expires in 1 hour**.

For production use, instruct the user to generate a **long-lived token**:

```bash
# Replace with your data
curl "https://graph.facebook.com/v19.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id={APP_ID}
  &client_secret={APP_SECRET}
  &fb_exchange_token={CURRENT_TOKEN}"
```

Or instruct: "Tell me when the token expires and I'll generate a new one for you in 1 minute."