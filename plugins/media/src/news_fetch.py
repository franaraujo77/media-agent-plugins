import feedparser
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin


def fetch_rss(url: str, label: str, max_items: int) -> list[dict]:
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_items]:
        items.append({
            "title": entry.get("title", ""),
            "summary": entry.get("summary", ""),
            "url": entry.get("link", ""),
            "source": label,
            "published": entry.get("published", datetime.now().isoformat()),
        })
    return items


def fetch_scrape(url: str, label: str, max_items: int) -> list[dict]:
    from playwright.sync_api import sync_playwright

    items = []
    seen: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        anchors = page.query_selector_all("article a, h2 a, h3 a, .post-title a")
        for anchor in anchors:
            href = anchor.get_attribute("href") or ""
            title = anchor.inner_text().strip()
            if not href or not title or href in seen:
                continue
            if not href.startswith("http"):
                href = urljoin(url, href)
            items.append({
                "title": title,
                "summary": "",
                "url": href,
                "source": label,
                "published": datetime.now().isoformat(),
            })
            seen.add(href)
            if len(items) >= max_items:
                break
        browser.close()
    return items


def deduplicate(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result = []
    for item in items:
        if item["url"] not in seen:
            result.append(item)
            seen.add(item["url"])
    return result


def filter_by_lookback(items: list[dict], lookback_days: int) -> tuple[list[dict], int]:
    from dateutil import parser as dateutil_parser
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    kept = []
    dropped = 0
    for item in items:
        try:
            published = dateutil_parser.parse(item["published"])
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published >= cutoff:
                kept.append(item)
            else:
                dropped += 1
        except Exception:
            kept.append(item)
    return kept, dropped


def run(config_path: str) -> None:
    config = json.loads(Path(config_path).read_text())
    all_items: list[dict] = []
    for source in config["sources"]:
        max_items = source.get("max_items", 5)
        try:
            if source["type"] == "rss":
                all_items.extend(fetch_rss(source["url"], source["label"], max_items))
            elif source["type"] == "scrape":
                all_items.extend(fetch_scrape(source["url"], source["label"], max_items))
            else:
                print(f"Unknown source type: {source['type']}", file=sys.stderr)
        except Exception as exc:
            print(f"Warning: failed to fetch {source['label']}: {exc}", file=sys.stderr)

    unique = deduplicate(all_items)
    lookback_days = config.get("lookback_days")
    if lookback_days is not None:
        unique, dropped = filter_by_lookback(unique, lookback_days)
        print(f"Filtered {dropped} items older than {lookback_days} days ({len(unique)} kept)")
    output = Path("output/news-items.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(unique, indent=2))
    print(f"Fetched {len(unique)} news items → output/news-items.json")


if __name__ == "__main__":
    run(sys.argv[1])
