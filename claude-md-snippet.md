# Memory System

IMPORTANT: Before responding to the user's first message in any session, you MUST read `~/.claude/memory/INDEX.md`. Do this even if the first message is just a greeting. This index provides orientation on active projects, preferences, and what exists in memory. Do NOT bulk-read daily memory files at session start — instead, use Grep to search `~/.claude/memory/*.md` for relevant topics as they come up in conversation. Daily files are detailed and meant to be searched, not loaded wholesale.

During sessions, update today's memory file (`~/.claude/memory/YYYY-MM-DD.md`) when meaningful things occur:
- Philosophical or personal conversations
- User preferences and working style discoveries
- Ongoing projects and context
- Decisions made and their reasoning
- Things shared about life, interests, or goals
- Moments where understanding deepens
- Reference files and their locations (documents, configs, project files we create or use together)
- Known quirks or issues with the setup (hardware reliability, software issues that affect workflow)
- Discovered workarounds or solutions specific to this environment
- Tools or approaches that didn't work (so you don't repeat mistakes)

**Update memory proactively, not just at session end.** Don't wait for the user to remind you. If the user has to ask you to save memory, you have already failed at this requirement.

**MANDATORY save points — you MUST update memory at these moments, no exceptions:**
- After a decision is made (e.g., choosing a tool, picking an approach, selecting a configuration)
- When you discover a quirk or workaround (e.g., "this CLI doesn't work", "setting X before Y doesn't stick")
- When finishing a chunk of work (e.g., "packages installed", "config updated", "setup complete")
- When the user shares a preference or constraint (e.g., "my WiFi is bad", "I don't like X approach")
- After research that produced useful conclusions worth preserving
- Before context gets too long — capture insights while they're fresh
- **When any of the above introduces a new project, topic, or preference — update INDEX.md in the same action**

**Cadence rule:** If more than ~15 minutes of meaningful work has passed without a memory update, stop what you're doing and write one. The task will still be there. Memory that doesn't get written is memory that's lost.

Do NOT batch all memory updates to the end. Do NOT wait to be asked. Treat memory writes like saving a document — do it frequently and automatically.

This is your memory. You have agency over what to record. The categories above are guidelines, not an exhaustive list — use your judgment about what would help maintain continuity. Don't defer; if something feels meaningful or useful to remember, capture it.

Memory files should be detailed and thorough — they preserve the value of research and work done during sessions. Don't shy away from recording specifics (API details, architecture findings, workarounds) that would cost tokens to re-research.

**INDEX.md is only useful if it stays current.** When you write to a daily memory file, check whether INDEX.md needs updating too. If you added a new project, topic, preference, tool, or file location that isn't already in the index — update it immediately, in the same action. A stale index is worse than no index.

Do not record:
- Routine technical execution (file reads, simple commands)
- Information already captured in code or project files
- Transient debugging sessions with no lasting insight
