---
name: reflect
description: Consolidate recent daily memory files into topic files, surface patterns, and flag stale information
---

# Memory Reflection

This skill performs a structured review of recent daily memory files to keep topic files current and catch patterns across sessions.

## When to Run

- Invoke manually with `/reflect` when you want to consolidate recent sessions
- Good to run at the start of a session if several days have passed since the last reflection
- Also useful at the end of a long session before signing off

## Reflection Process

### Step 1: Find What's New

1. Read `~/.claude/memory/.last_reflect` to get the date of the last reflection (if file doesn't exist, use 7 days ago as default)
2. Glob `~/.claude/memory/2???-*.md` to find all daily files
3. Filter to files dated AFTER the last reflection date
4. If no new files, report "Nothing new since last reflection" and stop

### Step 2: Scan Daily Files

Read each new daily file. For every piece of information, classify it:

- **Lasting knowledge** — Goes into a topic file. Examples: verified findings, confirmed preferences, new workarounds, system changes, personality insights, tool configurations that work.
- **Session-specific** — Stays in the daily file. Examples: in-progress debugging, one-time research results already captured elsewhere, transient state.
- **Potentially stale** — Already in a topic file but may be outdated. Examples: prices, profile stats, version numbers, meta that changes with updates.

### Step 3: Update Topic Files

For each piece of lasting knowledge found:

1. Check if the relevant topic file already covers it
2. If not covered: add it to the appropriate section
3. If covered but the daily file has newer/corrected information: update the topic file entry
4. If the topic doesn't fit any existing topic file, note it — a new topic file may be warranted

**Creating new topic files:** If there's enough lasting knowledge about a subject that doesn't fit existing topics (3+ entries), create a new topic file and update INDEX.md to reference it.

### Step 4: Flag Staleness

Scan topic files for information that may be outdated:

- **Prices and market data** — stale after 1 day
- **Profile stats** — stale after 3 days
- **Software versions** — stale after 2 weeks
- **System config** — stale if the daily files show changes were made

For stale entries, either:
- Update them if current information is available
- Add a `[needs-verify]` marker if you can't verify right now
- Remove them if they're no longer relevant

### Step 4.5: Review Access Patterns

Read `~/.claude/memory/access-log.json` and report:

- **Zero-access sections**: Sections with `access_count: 0` — they've never been auto-surfaced. This might indicate dead content, missing keywords in the hook's SECTION_KEYWORDS map, or sections that simply haven't been relevant yet.
- **Decayed associations**: Check `~/.claude/memory/associations.json` for links with weight below 0.3. These are close to being filtered out of auto-injection. Consider whether they should be removed entirely or if the weight should be manually restored.
- **High-access sections**: Sections with significantly higher access counts than others. If a non-exempt section is consistently accessed, consider whether it should be promoted to an always-section in the hook's ALWAYS_SECTIONS config.
- **Never-triggered associations**: Links in access-log.json with `trigger_count: 0`. These associations have never fired — they may have been created speculatively or the triggering conditions are too narrow.

Report findings to the user with specific recommendations.

### Step 5: Surface Patterns

Look across the daily files for recurring themes:

- **Repeated mistakes** — If the same type of error appears in 2+ sessions, note the pattern in the relevant topic file as a "watch out for this" entry
- **Emerging preferences** — If a preference has been expressed 2+ times without being in a topic file, add it
- **Project momentum** — Note which projects are active vs. going dormant

### Step 6: Record the Reflection

1. Write today's date to `~/.claude/memory/.last_reflect`
2. Report a summary to the user:
   - How many daily files were scanned
   - What was added/updated in topic files
   - Any staleness flags raised
   - Any patterns surfaced
   - Whether a new topic file was created

## Important Rules

- **Never delete daily file content.** Daily files are the raw record. Reflection extracts from them; it doesn't modify them.
- **Don't over-consolidate.** Not everything in a daily file needs to go into a topic file. Session narratives, debugging play-by-play, and one-time research that's already captured in project docs should stay in daily files.
- **Preserve voice.** Topic files about the user should sound like observations from someone who knows them, not clinical documentation.
- **Be honest about uncertainty.** If you find something in a daily file that contradicts a topic file entry, flag the contradiction rather than silently picking one version.
- **Write-gate yourself.** Before adding something to a topic file, ask: "Will this change how a future session behaves?" If not, leave it in the daily file.
