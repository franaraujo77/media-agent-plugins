import anthropic
import json
import sys
from datetime import date
from pathlib import Path


def resolve_soul(config: dict) -> dict | None:
    soul = config.get("soul")
    if soul is None:
        return None
    if isinstance(soul, str):
        path = Path(soul)
        if not path.exists():
            sys.exit(f"Error: soul file not found: {soul}")
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as e:
            sys.exit(f"Error: soul file is not valid JSON: {soul} ({e})")
    return soul


SYSTEM_PROMPT = (
    "You are a professional podcast host writing scripts for a daily news podcast. "
    "Your style is conversational, engaging, and concise. "
    "You summarize complex topics in plain language suitable for general audiences."
)


def build_user_prompt(
    podcast_name: str, description: str, today: str, news_items: list[dict]
) -> str:
    news_text = "\n\n".join(
        f"**{item['title']}** ({item['source']})\n{item['summary']}"
        for item in news_items
    )
    return f"""Write a podcast script for "{podcast_name}" — {description}.

Today's date: {today}

News items:
{news_text}

Structure:
- Brief intro (2-3 sentences, welcome listeners, mention the date)
- One segment per news item (2-3 sentences each, conversational tone, no URLs)
- Brief closing (1-2 sentences)

Target: 450-750 words. Write only the spoken script — no labels, no stage directions."""


def generate_script(
    podcast_name: str, description: str, today: str, news_items: list[dict]
) -> str:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": build_user_prompt(podcast_name, description, today, news_items),
            }
        ],
    )
    return response.content[0].text


def run(config_path: str) -> None:
    news_path = Path("output/news-items.json")
    if not news_path.exists():
        sys.exit("Error: output/news-items.json not found. Run news-fetch first.")

    config = json.loads(Path(config_path).read_text())
    podcast = config["podcast"]
    news_items = json.loads(news_path.read_text())
    today = date.today().strftime("%B %d, %Y")

    script = generate_script(podcast["name"], podcast["description"], today, news_items)

    Path("output").mkdir(exist_ok=True)
    Path("output/script.txt").write_text(script)
    print(f"Generated script ({len(script.split())} words) → output/script.txt")


if __name__ == "__main__":
    run(sys.argv[1])
