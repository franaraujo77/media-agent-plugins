import json
import os
import sys
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright

PROFILE_DIR = Path.home() / ".spotify-creator-profile"


def render_episode_title(template: str, date_str: str) -> str:
    return template.replace("{date}", date_str)


def build_description(news_items: list[dict]) -> str:
    lines = []
    for item in news_items:
        lines.append(f"- {item['title']} ({item['source']})")
        lines.append(f"  {item['url']}")
    return "\n".join(lines)


def load_credentials(credentials_env: str) -> tuple[str, str]:
    parts = [v.strip() for v in credentials_env.split(",")]
    return os.environ[parts[0]], os.environ[parts[1]]


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
        try:
            page = context.pages[0] if context.pages else context.new_page()

            # Navigate directly to the target — Spotify redirects to login with return_to if needed
            page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(3000)

            if "episode/wizard" not in page.url:
                # Redirected to login — complete the auth flow
                page.evaluate("document.querySelector('#accept-recommended-btn-handler')?.click()")
                page.wait_for_timeout(1500)
                page.get_by_role("button", name="Continue with Spotify").click()
                page.wait_for_selector("#username", timeout=15000)
                page.click("#username")
                page.keyboard.type(email, delay=50)
                page.keyboard.press("Enter")
                print("A browser window is open. Check your email for a verification code and enter it.")
                # Wait for password form (after 2FA) or direct redirect to wizard
                page.wait_for_function(
                    "() => document.querySelector('#password') !== null || "
                    "      window.location.href.includes('episode/wizard')",
                    timeout=300000,
                )
                if page.query_selector("#password"):
                    page.fill("#password", password)
                    page.click("button[type=submit]")
                # Wait for any creators.spotify.com page (login complete)
                page.wait_for_url("**/creators.spotify.com/**", timeout=60000)
                # Navigate to the wizard now that we're authenticated
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2000)

            with page.expect_file_chooser() as fc_info:
                page.get_by_test_id("uploadAreaWrapper").get_by_role("button", name="Select a file").click()
            fc_info.value.set_files(str(audio_path.resolve()))
            # Upload auto-advances to Details page; wait for status-message = "Preview ready!"
            page.get_by_test_id("status-message").wait_for(timeout=300000)

            page.fill("#title-input", episode_title)
            page.locator('[name="description"]').click()
            page.locator('[name="description"]').fill(description)

            page.get_by_role("button", name="Next").click()
            # Review step — select "Now" and publish
            page.locator('label[for="publish-date-now"]').wait_for(timeout=15000)
            page.locator('label[for="publish-date-now"]').click()
            page.get_by_role("button", name="Publish").click()
            page.wait_for_url("**/episodes", timeout=60000)

            episode_url = page.url
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

    episode_url = publish(
        email=email,
        password=password,
        show_id=spotify["show_id"],
        episode_title=episode_title,
        description=description,
        audio_path=audio_path,
    )
    print(f"Published: {episode_title} → {episode_url}")


if __name__ == "__main__":
    run(sys.argv[1])
