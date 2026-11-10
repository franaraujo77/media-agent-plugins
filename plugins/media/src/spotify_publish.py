import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

PROFILE_DIR = Path.home() / ".spotify-creator-profile"
FAILURE_DIR = Path("output/failures")
# Spotify for Creators rejects episode descriptions longer than this, and the
# Details step silently refuses to advance when the limit is exceeded.
MAX_DESCRIPTION_CHARS = 4000


def render_episode_title(template: str, date_str: str) -> str:
    return template.replace("{date}", date_str)


def build_description(news_items: list[dict], max_chars: int = MAX_DESCRIPTION_CHARS) -> str:
    """Format news items as a bulleted description, dropping whole items that
    would push it past Spotify's character limit."""
    lines = []
    length = 0
    for item in news_items:
        entry = f"- {item['title']} ({item['source']})\n  {item['url']}"
        # +1 for the newline joining this entry to the previous one
        added = len(entry) + (1 if lines else 0)
        if length + added > max_chars:
            break
        lines.append(entry)
        length += added
    return "\n".join(lines)


def load_credentials(credentials_env: str) -> tuple[str, str]:
    parts = [v.strip() for v in credentials_env.split(",")]
    return os.environ[parts[0]], os.environ[parts[1]]


class EpisodeAlreadyExists(Exception):
    """Raised when an episode with the same title is already on the show."""


class SpotifyLoginRequired(Exception):
    """Raised when Spotify asks for an emailed verification code: a person must log in at the Mac."""


LOGIN_REQUIRED_CODE = "spotify_login_required"
# Spotify's email-verification step: a one-time-code input, or the page text asking for the code.
VERIFICATION_SELECTOR = (
    'input[autocomplete="one-time-code"], input[name="otp"], '
    'input[data-testid="verification-code-input"]'
)
LOGIN_STEP_TIMEOUT_MS = 30000


def wait_for_login_step(page) -> str:
    """After the email is submitted, wait briefly for the next login step.

    Returns "password" or "wizard". Raises SpotifyLoginRequired on the email
    verification prompt instead of waiting for someone to type the code.
    """
    page.wait_for_function(
        "() => document.querySelector('#password') !== null || "
        "      window.location.href.includes('episode/wizard') || "
        f"      document.querySelector({json.dumps(VERIFICATION_SELECTOR)}) !== null || "
        "      /verification code|6-digit code/i.test(document.body.innerText)",
        timeout=LOGIN_STEP_TIMEOUT_MS,
    )
    if page.query_selector("#password"):
        return "password"
    if "episode/wizard" in page.url:
        return "wizard"
    raise SpotifyLoginRequired("Spotify asked for an email verification code")


def capture_failure(page, step: str) -> Path | None:
    """Save a screenshot and the page HTML so an unattended failure is diagnosable."""
    try:
        FAILURE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        prefix = FAILURE_DIR / f"{stamp}-{step}"
        shot = prefix.with_suffix(".png")
        page.screenshot(path=str(shot), full_page=True)
        prefix.with_suffix(".html").write_text(page.content())
        print(f"Failure at step '{step}' — url: {page.url}", file=sys.stderr)
        print(f"Saved screenshot → {shot}", file=sys.stderr)
        return shot
    except Exception as exc:  # never mask the original error
        print(f"Could not capture failure state: {exc}", file=sys.stderr)
        return None


def episode_exists(page, show_id: str, episode_title: str) -> bool:
    """Check the show's episode list (which includes drafts) for this title."""
    page.goto(
        f"https://creators.spotify.com/pod/show/{show_id}/episodes",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    page.wait_for_timeout(3000)
    return page.get_by_text(episode_title, exact=False).count() > 0


def publish(
    email: str,
    password: str,
    show_id: str,
    episode_title: str,
    description: str,
    audio_path: Path,
) -> str:
    PROFILE_DIR.mkdir(exist_ok=True)
    target_url = f"https://creators.spotify.com/pod/show/{show_id}/episode/wizard"
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            slow_mo=50,
        )
        page = context.pages[0] if context.pages else context.new_page()
        step = "open-wizard"
        try:
            # Navigate directly to the target — Spotify redirects to login with return_to if needed
            page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(3000)

            if "episode/wizard" not in page.url:
                step = "login"
                # Redirected to login — complete the auth flow
                page.evaluate("document.querySelector('#accept-recommended-btn-handler')?.click()")
                page.wait_for_timeout(1500)
                page.get_by_role("button", name="Continue with Spotify").click()
                page.wait_for_selector("#username", timeout=15000)
                page.click("#username")
                page.keyboard.type(email, delay=50)
                page.keyboard.press("Enter")
                # A verification prompt raises SpotifyLoginRequired right away.
                if wait_for_login_step(page) == "password":
                    page.fill("#password", password)
                    page.click("button[type=submit]")
                # Wait for any creators.spotify.com page (login complete)
                page.wait_for_url("**/creators.spotify.com/**", timeout=60000)
            # Don't upload a duplicate: a previous run may have left a draft
            # behind after failing partway through the wizard.
            step = "check-existing"
            if episode_exists(page, show_id, episode_title):
                raise EpisodeAlreadyExists(episode_title)

            step = "open-wizard"
            page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            step = "upload-audio"
            with page.expect_file_chooser() as fc_info:
                page.get_by_test_id("uploadAreaWrapper").get_by_role("button", name="Select a file").click()
            fc_info.value.set_files(str(audio_path.resolve()))
            # Upload auto-advances to Details page; wait for status-message = "Preview ready!"
            page.get_by_test_id("status-message").wait_for(timeout=300000)

            step = "fill-details"
            page.fill("#title-input", episode_title)
            page.locator('[name="description"]').click()
            page.locator('[name="description"]').fill(description)

            step = "review"
            page.get_by_role("button", name="Next").click()
            # Review step — select "Now" and publish
            page.locator('label[for="publish-date-now"]').wait_for(timeout=15000)
            page.locator('label[for="publish-date-now"]').click()
            # Spotify keeps the Publish button disabled while it finishes
            # processing the uploaded audio — this can take far longer than the
            # default 30s click timeout. Wait for the review form's submit button
            # to become enabled before clicking.
            page.wait_for_function(
                """() => {
                    const btn = [...document.querySelectorAll('button')]
                        .find(b => b.getAttribute('form') === 'review-form');
                    return btn && !btn.disabled;
                }""",
                timeout=600000,
            )
            step = "publish"
            page.get_by_role("button", name="Publish").click()
            page.wait_for_url("**/episodes", timeout=60000)

            episode_url = page.url
        except (EpisodeAlreadyExists, SpotifyLoginRequired):
            raise
        except Exception:
            capture_failure(page, step)
            raise
        finally:
            context.close()
    return episode_url


def run(config_path: str) -> None:
    audio_path = Path("output/episode.mp3")
    if not audio_path.exists():
        sys.exit("Error: output/episode.mp3 not found. Run tts-generate first.")

    news_path = Path("output/news-items.json")
    if not news_path.exists():
        sys.exit("Error: output/news-items.json not found. Run news-fetch first.")

    config = json.loads(Path(config_path).read_text())
    podcast = config["podcast"]
    spotify = config["spotify"]

    try:
        email, password = load_credentials(spotify["credentials_env"])
    except KeyError as exc:
        sys.exit(f"Error: environment variable {exc} is not set. Check credentials_env in config.")
    today = date.today().strftime("%Y-%m-%d")
    episode_title = render_episode_title(podcast["episode_title_template"], today)

    news_items = json.loads(news_path.read_text())
    description = build_description(news_items)

    try:
        episode_url = publish(
            email=email,
            password=password,
            show_id=spotify["show_id"],
            episode_title=episode_title,
            description=description,
            audio_path=audio_path,
        )
    except SpotifyLoginRequired:
        print(
            "Spotify asked for an email verification code, so the publish stopped. "
            "Log in to Spotify for Creators at the Mac, then run it again.",
            file=sys.stderr,
        )
        print(f"code={LOGIN_REQUIRED_CODE}")  # the final line: the report step reads it
        sys.exit(3)
    except EpisodeAlreadyExists:
        sys.exit(
            f'Error: an episode titled "{episode_title}" already exists on this show '
            "(it may be a draft left by a failed run). Delete or publish it manually, "
            "then re-run."
        )
    print(f"Published: {episode_title} → {episode_url}")


if __name__ == "__main__":
    run(sys.argv[1])
