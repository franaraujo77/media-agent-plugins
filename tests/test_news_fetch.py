import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from plugins.media.src.news_fetch import fetch_rss, deduplicate, run, filter_by_lookback


def _mock_feed(entries_data: list[dict]):
    """Build a mock feedparser feed from a list of entry dicts."""
    mock_feed = MagicMock()
    mock_feed.entries = [dict(e) for e in entries_data]
    return mock_feed


def test_fetch_rss_returns_structured_items():
    feed = _mock_feed([
        {"title": "Test Article", "summary": "A summary.", "link": "https://example.com/1", "published": "2026-04-20"},
    ])
    with patch("plugins.media.src.news_fetch.feedparser") as mock_fp:
        mock_fp.parse.return_value = feed
        items = fetch_rss("https://example.com/rss", "Test Source", 5)

    assert len(items) == 1
    assert items[0]["title"] == "Test Article"
    assert items[0]["summary"] == "A summary."
    assert items[0]["url"] == "https://example.com/1"
    assert items[0]["source"] == "Test Source"
    assert items[0]["published"] == "2026-04-20"


def test_fetch_rss_respects_max_items():
    entries = [
        {"title": f"Article {i}", "summary": "", "link": f"https://example.com/{i}", "published": "2026-04-20"}
        for i in range(10)
    ]
    feed = _mock_feed(entries)
    with patch("plugins.media.src.news_fetch.feedparser") as mock_fp:
        mock_fp.parse.return_value = feed
        items = fetch_rss("https://example.com/rss", "Source", 3)

    assert len(items) == 3


def test_fetch_rss_falls_back_when_published_missing():
    feed = _mock_feed([{"title": "No Date", "summary": "", "link": "https://example.com/1"}])
    with patch("plugins.media.src.news_fetch.feedparser") as mock_fp:
        mock_fp.parse.return_value = feed
        items = fetch_rss("https://example.com/rss", "Source", 5)

    assert items[0]["published"] != ""


def test_deduplicate_removes_duplicate_urls():
    items = [
        {"url": "https://a.com", "title": "A"},
        {"url": "https://b.com", "title": "B"},
        {"url": "https://a.com", "title": "A again"},
    ]
    result = deduplicate(items)
    assert len(result) == 2
    assert result[0]["url"] == "https://a.com"
    assert result[1]["url"] == "https://b.com"


def test_deduplicate_preserves_order():
    items = [
        {"url": "https://c.com", "title": "C"},
        {"url": "https://a.com", "title": "A"},
        {"url": "https://b.com", "title": "B"},
    ]
    result = deduplicate(items)
    assert [i["url"] for i in result] == ["https://c.com", "https://a.com", "https://b.com"]


def test_run_writes_output_file(tmp_path, monkeypatch):
    config = {
        "sources": [
            {"type": "rss", "url": "https://example.com/rss", "label": "Test", "max_items": 2}
        ]
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))
    monkeypatch.chdir(tmp_path)

    feed = _mock_feed([
        {"title": "Article", "summary": "Summary", "link": "https://example.com/1", "published": "2026-04-20"},
    ])
    with patch("plugins.media.src.news_fetch.feedparser") as mock_fp:
        mock_fp.parse.return_value = feed
        run(str(config_file))

    output = json.loads((tmp_path / "output" / "news-items.json").read_text())
    assert len(output) == 1
    assert output[0]["title"] == "Article"


def _item(title: str, published: str) -> dict:
    return {"title": title, "url": f"https://example.com/{title}", "published": published, "source": "X", "summary": ""}


def test_filter_keeps_items_within_window():
    now = datetime.now(timezone.utc)
    items = [
        _item("recent", now.isoformat()),
        _item("old", (now - timedelta(days=8)).isoformat()),
    ]
    kept, dropped = filter_by_lookback(items, 7)
    assert [i["title"] for i in kept] == ["recent"]
    assert dropped == 1


def test_filter_keeps_items_with_unparseable_date():
    items = [_item("x", "not-a-date")]
    kept, dropped = filter_by_lookback(items, 7)
    assert len(kept) == 1
    assert dropped == 0


def test_filter_drops_item_just_outside_window():
    now = datetime.now(timezone.utc)
    items = [_item("edge", (now - timedelta(days=7, hours=1)).isoformat())]
    kept, dropped = filter_by_lookback(items, 7)
    assert len(kept) == 0
    assert dropped == 1


def test_filter_handles_naive_datetime():
    # Naive datetimes (no timezone) should be treated as UTC
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    items = [_item("naive", now_naive.isoformat())]
    kept, dropped = filter_by_lookback(items, 7)
    assert len(kept) == 1
    assert dropped == 0


def test_run_filters_by_lookback_days(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    config = {
        "sources": [{"type": "rss", "url": "https://example.com/rss", "label": "Test", "max_items": 5}],
        "lookback_days": 3,
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config))

    fresh_entry = {
        "title": "Fresh", "summary": "s", "link": "https://example.com/fresh",
        "published": now.isoformat(),
    }
    stale_entry = {
        "title": "Stale", "summary": "s", "link": "https://example.com/stale",
        "published": (now - timedelta(days=5)).isoformat(),
    }

    mock_feed = MagicMock()
    mock_feed.entries = [fresh_entry, stale_entry]

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.chdir(tmp_path)

    with patch("plugins.media.src.news_fetch.feedparser") as mock_fp:
        mock_fp.parse.return_value = mock_feed
        run(str(config_file))

    items = json.loads((output_dir / "news-items.json").read_text())
    assert len(items) == 1
    assert items[0]["title"] == "Fresh"
