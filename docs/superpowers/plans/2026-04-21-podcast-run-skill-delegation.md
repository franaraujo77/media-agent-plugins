# podcast-run Skill Delegation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `podcast-run` to invoke the other four media skills in sequence (via the `Skill` tool) instead of calling their Python scripts directly, so that skills like `script-generate` can apply their own conditional logic (e.g. keyless native generation).

**Architecture:** Replace the four `python3 plugins/media/src/*.py` Bash calls in `podcast-run/SKILL.md` with `Skill` tool invocations for `media:news-fetch`, `media:script-generate`, `media:tts-generate`, and `media:spotify-publish`. Add `Skill` to `allowed-tools`. Keep the cleanup Bash step as-is.

**Tech Stack:** SKILL.md (Claude Code skill files), no Python changes needed.

---

### Task 1: Update `podcast-run/SKILL.md` to delegate to sub-skills

**Files:**
- Modify: `plugins/media/skills/podcast-run/SKILL.md`

- [ ] **Step 1: Read the current file**

```bash
cat plugins/media/skills/podcast-run/SKILL.md
```

Confirm the current content matches what is expected (steps 1–4 each call `python3 plugins/media/src/<name>.py`).

- [ ] **Step 2: Replace the file with the updated version**

Write the following content to `plugins/media/skills/podcast-run/SKILL.md`:

```markdown
---
name: podcast-run
description: Run the full podcast pipeline end-to-end — fetch news, generate script, create audio, publish to Spotify. Pass a config file as the argument. Calls all four media skills in sequence.
argument-hint: <path-to-config.json>
allowed-tools: Bash(rm *), Skill
---

# podcast-run

Run the complete pipeline for the podcast defined in the config file provided as the argument.

## Steps

Invoke each skill in sequence. Stop and report the full error message if any step fails — do not continue to the next step.

1. Fetch news:

   Use the `Skill` tool with skill `media:news-fetch` and argument `<argument>`.

2. Generate script:

   Use the `Skill` tool with skill `media:script-generate` and argument `<argument>`.

3. Generate audio:

   Use the `Skill` tool with skill `media:tts-generate` and argument `<argument>`.

4. Publish to Spotify:

   Use the `Skill` tool with skill `media:spotify-publish` and argument `<argument>`.

5. Clean up temp files:

   ```bash
   rm -f output/news-items.json output/script.txt output/episode.mp3
   ```

6. Report the published episode URL from step 4's output.
```

- [ ] **Step 3: Verify the file was written correctly**

```bash
cat plugins/media/skills/podcast-run/SKILL.md
```

Confirm:
- `allowed-tools` line contains `Skill` and no longer contains `Bash(python3 *)`
- Steps 1–4 reference `Skill` tool invocations, not `python3` commands
- Steps 5–6 are unchanged

- [ ] **Step 4: Commit**

```bash
git add plugins/media/skills/podcast-run/SKILL.md
git commit -m "fix: podcast-run delegates to sub-skills instead of calling Python directly"
```

---

### Task 2: Bump plugin version

**Files:**
- Modify: `plugins/media/plugin.json`

- [ ] **Step 1: Read current version**

```bash
cat plugins/media/plugin.json
```

Note the current `version` field (e.g. `"1.8.0"`).

- [ ] **Step 2: Increment the patch version**

Edit `plugins/media/plugin.json` and increment the patch digit of `version` (e.g. `"1.8.0"` → `"1.8.1"`).

- [ ] **Step 3: Verify**

```bash
grep '"version"' plugins/media/plugin.json
```

Confirm the version was incremented.

- [ ] **Step 4: Commit**

```bash
git add plugins/media/plugin.json
git commit -m "chore: bump plugin version to 1.8.1"
```
