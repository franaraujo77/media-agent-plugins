# podcast-run Plugin Cache Sync Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Claude Code load the current repo's `podcast-run/SKILL.md` (which already delegates to sub-skills) instead of the stale cached version at `c22ba1134bfa`.

**Architecture:** The fix in `1d56773` replaced Python `Bash` calls with `Skill` tool invocations in `podcast-run/SKILL.md`, but the locally-installed plugin cache still points to `c22ba1134bfa` (before that commit). The cache lives at `~/.claude/plugins/cache/franaraujo77-media-agent-plugins/media/c22ba1134bfa/`. Overwriting the stale SKILL.md files in-place is the fastest path; updating `installed_plugins.json` makes it stick across Claude Code restarts.

**Tech Stack:** Shell (cp, jq), `~/.claude/plugins/` filesystem.

---

### Task 1: Overwrite stale cached skill files with current repo versions

**Files:**
- Modify (in cache): `~/.claude/plugins/cache/franaraujo77-media-agent-plugins/media/c22ba1134bfa/skills/podcast-run/SKILL.md`
- Modify (in cache): `~/.claude/plugins/cache/franaraujo77-media-agent-plugins/media/c22ba1134bfa/skills/script-generate/SKILL.md`

The two skills that changed since the cache was snapshotted are `podcast-run` (now uses `Skill` tool) and `script-generate` (now handles keyless generation natively). Both need to be synced.

- [ ] **Step 1: Copy the current podcast-run SKILL.md into the cache**

```bash
cp plugins/media/skills/podcast-run/SKILL.md \
   ~/.claude/plugins/cache/franaraujo77-media-agent-plugins/media/c22ba1134bfa/skills/podcast-run/SKILL.md
```

Expected: no output (success is silent).

- [ ] **Step 2: Copy the current script-generate SKILL.md into the cache**

```bash
cp plugins/media/skills/script-generate/SKILL.md \
   ~/.claude/plugins/cache/franaraujo77-media-agent-plugins/media/c22ba1134bfa/skills/script-generate/SKILL.md
```

- [ ] **Step 3: Verify the cached podcast-run SKILL.md now references Skill tool**

```bash
grep "Skill" ~/.claude/plugins/cache/franaraujo77-media-agent-plugins/media/c22ba1134bfa/skills/podcast-run/SKILL.md
```

Expected output contains:
```
allowed-tools: Bash(rm *), Skill
   Use the `Skill` tool with skill `media:news-fetch` and argument `<argument>`.
   Use the `Skill` tool with skill `media:script-generate` and argument `<argument>`.
   Use the `Skill` tool with skill `media:tts-generate` and argument `<argument>`.
   Use the `Skill` tool with skill `media:spotify-publish` and argument `<argument>`.
```

- [ ] **Step 4: Verify no python3 calls remain in cached podcast-run SKILL.md**

```bash
grep "python3" ~/.claude/plugins/cache/franaraujo77-media-agent-plugins/media/c22ba1134bfa/skills/podcast-run/SKILL.md
```

Expected: no output (zero matches).

- [ ] **Step 5: Commit**

No files to commit — this task only modifies the plugin cache (outside the repo). No commit needed.

---

### Task 2: Run the pipeline to verify the fix

No code changes required — this task verifies the fix from Task 1 works end-to-end.

- [ ] **Step 1: Start a new Claude Code session** (cache is re-read at session start)

Open a new Claude Code session in this repo. This is required because the plugin SKILL.md content is loaded once at session start from the cache; changes to cached files only take effect in new sessions.

- [ ] **Step 2: Run the pipeline**

```
/media:podcast-run plugins/media/configs/prod-grade-ai-podcast.json
```

Expected behavior:
1. `news-fetch` skill runs — outputs `Fetched N news items → output/news-items.json`
2. `script-generate` skill runs — because `ANTHROPIC_API_KEY` is not set, it generates the script natively using Claude's own context. Outputs `output/script.txt`.
3. `tts-generate` skill runs — converts `output/script.txt` to `output/episode.mp3`
4. `spotify-publish` skill runs — publishes and returns the episode URL
5. Cleanup step removes temp files
6. Episode URL is reported

- [ ] **Step 3: Confirm no ANTHROPIC_API_KEY error appears**

The pipeline should complete without any `TypeError: "Could not resolve authentication method"` error.

---

### Background: Why this keeps happening

The plugin is installed from the remote marketplace at a specific git commit SHA. When you commit changes to this repo and push, the cache is NOT automatically updated — Claude Code still loads the version it fetched at install time. 

To avoid this in the future, after pushing commits that change any `SKILL.md` file, run:

```bash
for skill_dir in plugins/media/skills/*/; do
  skill=$(basename "$skill_dir")
  cp "${skill_dir}SKILL.md" \
     ~/.claude/plugins/cache/franaraujo77-media-agent-plugins/media/c22ba1134bfa/skills/${skill}/SKILL.md \
     2>/dev/null && echo "synced: $skill"
done
```

This syncs all skill files at once. A future improvement would be a pre-push git hook that runs this automatically.
