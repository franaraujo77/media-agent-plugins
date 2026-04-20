---
name: news-fetch
description: Fetch and deduplicate news items from RSS feeds and web pages for a configured podcast. Writes output/news-items.json. Run before script-generate.
argument-hint: <path-to-config.json>
allowed-tools: Bash(python3 *)
---

# news-fetch

Fetch today's news items for the podcast defined in the config file provided as the argument.

## Steps

1. Run the news fetch script with the config path argument:

   ```bash
   python3 plugins/media/src/news_fetch.py <argument>
   ```

2. Report how many items were fetched and confirm `output/news-items.json` was written.
   If the script errors, report the full error message.
