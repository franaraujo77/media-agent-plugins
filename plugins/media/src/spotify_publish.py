import json
import os
import sys
from datetime import date
from pathlib import Path
from playwright.sync_api import sync_playwright


def render_episode_title(template: str, date_str: str) -> str:
    return template.replace("{date}", date_str)


def build_description(news_items: list[dict]) -> str:
    return "\n".join(f"- {item['title']} ({item['source']})" for item in news_items)


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
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            page.goto("https://creators.spotify.com/pod/login")
            page.get_by_label("Email address").fill(email)
            page.get_by_label("Password").fill(password)
            page.get_by_role("button", name="Log In").click()
            page.wait_for_url("**/dashboard**", timeout=15000)

            page.goto(f"https://creators.spotify.com/pod/show/{show_id}/episodes/new")

            with page.expect_file_chooser() as fc_info:
                page.get_by_text("Select a file").click()
            fc_info.value.set_files(str(audio_path.resolve()))
            page.get_by_text("Upload complete").wait_for(timeout=120000)

            page.get_by_placeholder("Episode title").fill(episode_title)
            page.get_by_placeholder("What's this episode about?").fill(description)

            page.get_by_role("button", name="Publish Now").click()
            page.wait_for_url("**/episodes/**", timeout=30000)

            episode_url = page.url
        finally:
            browser.close()
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
