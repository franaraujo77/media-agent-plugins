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


def build_system_prompt(soul: dict | None) -> str:
    if soul is None:
        return SYSTEM_PROMPT
    writer = soul.get("writer", {})
    persona = writer.get("persona", "a professional podcast host")
    tone = writer.get("tone", "neutral")
    formality = writer.get("formality", "mixed")
    humor = writer.get("humor", "none")
    return (
        f"You are {persona}. "
        f"Your tone is {tone}. "
        f"Your writing style is {formality}. "
        f"Your humor is {humor}. "
        "Write scripts that reflect this personality consistently."
    )


def build_user_prompt(
    podcast_name: str, description: str, today: str, news_items: list[dict], soul: dict | None = None
) -> str:
    news_text = "\n\n".join(
        f"**{item['title']}** ({item['source']})\n{item['summary']}"
        for item in news_items
    )
    delivery = ""
    if soul and soul.get("speaker", {}).get("delivery"):
        delivery = (
            f"\nDelivery style: {soul['speaker']['delivery']} "
            "Apply these cues throughout the script so the text reads naturally when converted to audio."
        )
    return f"""Write a podcast script for "{podcast_name}" — {description}.

Today's date: {today}

News items:
{news_text}

Structure:
- Brief intro (2-3 sentences, welcome listeners, mention the date)
- One segment per news item (2-3 sentences each, conversational tone, no URLs)
- Brief closing (1-2 sentences)

Target: 450-750 words. Write only the spoken script — no labels, no stage directions.{delivery}"""


def generate_script(
    podcast_name: str, description: str, today: str, news_items: list[dict], soul: dict | None = None
) -> str:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": build_system_prompt(soul),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": build_user_prompt(podcast_name, description, today, news_items, soul),
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
    soul = resolve_soul(config)

    script = generate_script(podcast["name"], podcast["description"], today, news_items, soul)

    Path("output").mkdir(exist_ok=True)
    Path("output/script.txt").write_text(script)
    print(f"Generated script ({len(script.split())} words) → output/script.txt")


if __name__ == "__main__":
    run(sys.argv[1])
