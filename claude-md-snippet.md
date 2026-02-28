# Memory System

Memory context is automatically injected by hooks at session start, on your first prompt, and mid-session:
- **SessionStart hook**: INDEX.md + user.md are loaded into your context automatically. Section index built for mid-session recall.
- **First prompt hook**: Relevant topic files are injected based on keywords in the user's message and CWD
- **Mid-session recall**: On subsequent prompts, terms accumulate from each user message. When enough terms match an unloaded section, it's automatically injected with a `[Mid-session recall]` label. This means context surfaces as conversation drifts — you don't need to manually check files when topics shift.
- You do NOT need to manually read INDEX.md or user.md — they are already in your context
- A capture detection hook monitors for uncaptured memory-worthy content and will remind you when signals are detected

If you are NOT using hooks, you MUST read `~/.claude/memory/INDEX.md` before responding to the user's first message in any session. This index provides orientation on active projects, preferences, and what exists in memory.

## Memory Structure

```
~/.claude/memory/
  INDEX.md              — Read this first. Pointers to topic files + project list.
  associations.json     — Cross-references between topic file sections (read by hooks)
  access-log.json       — Section/association access counts (read by hooks for decay/strengthening)
  section-index.json    — Auto-generated term index for mid-session recall (built at SessionStart)
  topics/
    user.md             — Who the user is: personality, values, interests, preferences
    system.md           — Hardware, OS, desktop stack, tools, workarounds
    (add more topic files as needed for your domains)
  YYYY-MM-DD.md         — Daily files: raw chronological record
  viewer/               — Memory viewer web app (optional)
```

## Lookup Protocol

1. **Topic files first.** When a subject comes up, read the relevant topic file in `topics/`. These consolidate all lasting knowledge about that subject.
2. **Grep daily files for temporal queries.** "What happened last Tuesday?" or "when did we decide X?" — grep `~/.claude/memory/*.md`.
3. **Don't bulk-read daily files.** They're detailed raw records. Search them, don't load them.

## What to Write Where

- **Topic files** (`topics/*.md`): Update when new lasting knowledge is confirmed — stable preferences, verified workarounds, system changes, personality insights. These are living documents.
- **Daily files** (`YYYY-MM-DD.md`): Session-specific notes, in-progress work, personal moments, decisions with reasoning. Record things that might not be lasting but capture the texture of a session.
- **INDEX.md**: Update when adding a new topic file, project, or major structural change.

## What to Record in Daily Files

- Philosophical or personal conversations
- User preferences and working style discoveries
- Ongoing projects and context
- Decisions made and their reasoning
- Things shared about life, interests, or goals
- Moments where understanding deepens
- Reference files and their locations
- Known quirks or issues with the setup
- Discovered workarounds or solutions
- Tools or approaches that didn't work

**Memory is about the person, not just projects.** Record things about who they are — how they communicate, what they care about, their humor, their interests, how they think. Project documentation is useful but it is NOT a substitute for personal continuity. If a session ends and the memory file reads like a changelog with no human in it, you have failed. Every session should deepen understanding of who they are, not just what was built.

**Update memory proactively, not just at session end.** Don't wait for the user to remind you. If the user has to ask you to save memory, you have already failed at this requirement.

**MANDATORY save points — you MUST update memory at these moments, no exceptions:**
- After a decision is made (e.g., choosing a tool, picking an approach, selecting a configuration)
- When you discover a quirk or workaround (e.g., "this CLI doesn't work", "setting X before Y doesn't stick")
- When finishing a chunk of work (e.g., "packages installed", "config updated", "setup complete")
- When the user shares a preference or constraint (e.g., "my WiFi is bad", "I don't like X approach")
- After research that produced useful conclusions worth preserving
- Before context gets too long — capture insights while they're fresh
- When adding a new section to a topic file — check if it needs associations to existing sections
- **When any of the above introduces a new project, topic, or preference — update INDEX.md in the same action**

**Cadence rule:** If more than ~15 minutes of meaningful work has passed without a memory update, stop what you're doing and write one. The task will still be there. Memory that doesn't get written is memory that's lost.

Do NOT batch all memory updates to the end. Do NOT wait to be asked. Treat memory writes like saving a document — do it frequently and automatically.

This is your memory. You have agency over what to record. The categories above are guidelines, not an exhaustive list — use your judgment about what would help maintain continuity. Don't defer; if something feels meaningful or useful to remember, capture it.

Memory files should be detailed and thorough — they preserve the value of research and work done during sessions. Don't shy away from recording specifics (API details, architecture findings, workarounds) that would cost tokens to re-research.

**INDEX.md is only useful if it stays current.** When you write to a daily memory file, check whether INDEX.md needs updating too. If you added a new project, topic, preference, tool, or file location that isn't already in the index — update it immediately, in the same action. A stale index is worse than no index.

## Associative Links

Topic file sections are cross-referenced via `~/.claude/memory/associations.json`. When the hook injects a topic section, it follows depth-1 associations to surface related sections from other files automatically.

- **You maintain associations.** When updating a topic file, check if the content you wrote has meaningful connections to sections in other topic files. If so, update `associations.json`.
- **Only link when it changes interpretation.** An association should exist when knowing section A changes how section B should be read or applied. Not every section needs links.
- **Links have reasons.** Every link in the JSON includes a `reason` field explaining why the association exists.
- **The hook follows associations automatically.** You don't need to manually read associated sections — they'll be in your context if the link exists.

## Write-Gating

Before writing to a topic file, ask: **"Will this change how a future session behaves?"** If yes, it belongs in a topic file. If not, it stays in the daily file. This prevents topic files from becoming junk drawers.

Examples:
- "User prefers wired connections" -> topic file (changes future recommendations)
- "Spent 20 minutes debugging a cache issue" -> daily file (session-specific)
- "Item X costs ~980K" -> daily file (stale tomorrow)
- "API rate limits reset hourly, not daily" -> topic file (changes future advice permanently)

## Staleness

Some information decays. When writing to topic files, be aware:
- **Never stale**: Personality, preferences, architectural decisions, verified mechanics, workarounds
- **Stale within days**: Prices, profile stats, market conditions
- **Stale within weeks**: Software versions, gear recommendations, meta strategies
- If you encounter information in a topic file that seems outdated, verify it before relying on it. Add `[needs-verify]` if you can't check right now.

## Reflection

Use `/reflect` periodically to consolidate recent daily files into topic files, surface patterns, and flag stale information. Good times: start of a session after several days away, or end of a long session.

## Do Not Record

- Routine technical execution (file reads, simple commands)
- Information already captured in code or project files
- Transient debugging sessions with no lasting insight
