# Claude Code Memory System

A persistent memory system for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that gives Claude continuity across sessions. Instead of starting every conversation from scratch, Claude remembers context, preferences, project history, and the person it's working with.

This isn't a plugin or extension — it's a set of instructions and conventions that work within Claude Code's existing `CLAUDE.md` configuration system. You paste a snippet into your config, create a directory, and Claude handles the rest.

## Why This Exists

Claude Code is stateless by default. Every session is a blank slate. That's fine for one-off tasks, but if you're working on a project over days or weeks, you end up repeating yourself — re-explaining your setup, your preferences, your project structure, decisions you already made.

This system solves that. Claude writes structured daily memory files during sessions, maintains a searchable index, and consults its own memory at the start of each new conversation. The result is something closer to working with a collaborator who actually remembers yesterday.

## How It Works

The system has three parts:

### 1. Daily Memory Files

Each session, Claude writes (or updates) a markdown file named by date (`YYYY-MM-DD.md`) in `~/.claude/memory/`. These files capture:

- Decisions made and their reasoning
- Project context and progress
- Preferences and working style
- Workarounds and solutions discovered
- Technical details worth preserving (so they don't need to be re-researched)

The files use `## Section` headers to organize entries by topic. This makes them greppable — Claude can search across all memory files for a specific subject without loading everything into context.

**Example daily file** (`2026-02-14.md`):

```markdown
# 2026-02-14

## Project: Website Redesign
- Decided on a static site approach using vanilla HTML/CSS/JS
- Key pages: home, projects, about
- Hosting on GitHub Pages from the main branch

## Technical: Fish Shell Config
- User's $SHELL reports zsh but they actually use fish
- Config lives at ~/.config/fish/config.fish
- Added custom aliases for project shortcuts

## Preferences
- Prefers minimal dependencies — no frameworks unless truly needed
- Likes Tokyo Night color scheme across tools
- Values clear commit messages that explain "why" not "what"
```

### 2. INDEX.md

A curated quick-reference index that Claude reads at the start of every session. It provides orientation without Claude needing to load every daily file. Think of it as a table of contents for Claude's memory.

The index organizes information into sections like active projects, completed projects, system/hardware details, tools and workarounds, and file locations. Claude updates it whenever a new project, preference, or important detail is added to a daily file.

A [template](templates/INDEX.md) is included to get you started.

### 3. CLAUDE.md Instructions

The instructions that tell Claude *how* to use the memory system. These go in your `~/.claude/CLAUDE.md` (global) or a project-level `CLAUDE.md`. They define:

- **When to read**: Check INDEX.md at session start, grep daily files as topics come up
- **When to write**: After decisions, discoveries, finished work chunks, shared preferences
- **What to record**: Anything that would be costly to re-learn or that builds continuity
- **What to skip**: Routine commands, info already in code, transient debugging

The instructions are opinionated about proactive writes — Claude shouldn't wait until the end of a session or be asked to save. Memory that doesn't get written is memory that's lost.

## Setup

### 1. Create the memory directory

```bash
mkdir -p ~/.claude/memory
```

### 2. Create your INDEX.md

Copy the template into your memory directory:

```bash
cp templates/INDEX.md ~/.claude/memory/INDEX.md
```

Or create a minimal one:

```markdown
# Memory Index

Quick-reference index of all topics in daily memory files.

## Active Projects

## Preferences

## Tools & Workarounds

## File Locations
```

### 3. Add the instructions to CLAUDE.md

Copy the contents of [`claude-md-snippet.md`](claude-md-snippet.md) into your `~/.claude/CLAUDE.md`. If you already have a CLAUDE.md, add the memory section to it.

If you don't have a CLAUDE.md yet:

```bash
cp claude-md-snippet.md ~/.claude/CLAUDE.md
```

### 4. Start a session

That's it. Open Claude Code and start working. Claude will read INDEX.md automatically at session start and begin writing to today's memory file as the session progresses.

## Memory Viewer (Optional)

The `viewer/` directory contains a local web app for browsing your memory files. It provides:

- **Index view**: Your INDEX.md rendered as a navigable document
- **Journal view**: All daily memory files as expandable timeline entries
- **Config view**: Your CLAUDE.md rendered for reference
- **Search**: Full-text search across all views
- **Calendar strip**: Visual overview of which days have memory entries

### Installing the viewer

Copy the viewer files into your memory directory:

```bash
cp -r viewer ~/.claude/memory/viewer
```

Then run it:

```bash
python3 ~/.claude/memory/viewer/server.py
```

This starts a local server on `http://localhost:8642` and opens your browser. Press `Ctrl+C` to stop.

You can add a shell alias for convenience:

```bash
alias memory-viewer="python3 ~/.claude/memory/viewer/server.py"
```

The viewer is entirely local — nothing is sent anywhere. It reads directly from your `~/.claude/memory/` directory.

### Customizing the viewer

The viewer ships with a cyberpunk terminal aesthetic (scanlines, glitch effects, monospace everything). If that's not your style, the theming is all in CSS variables at the top of `style.css`:

```css
:root {
    --bg: #06060c;
    --accent: #00ffd5;
    --pink: #ff2d78;
    --text: #c0d8d0;
    /* ... */
}
```

You can also add a background character image by placing a PNG in the viewer directory and adding a positioned element to `index.html` with styling like:

```css
.background-character {
    position: fixed;
    bottom: 0;
    right: 40px;
    z-index: 10;
    pointer-events: none;
    opacity: 0.12;
    filter: brightness(0.9) saturate(0.2) sepia(0.6) hue-rotate(120deg) contrast(1.1);
}

.background-character img {
    display: block;
    height: 420px;
    width: auto;
}
```

## Design Decisions

A few choices worth explaining:

**Grep over bulk reads.** Claude doesn't load all memory files at session start. That would waste context window on irrelevant history. Instead, it reads INDEX.md for orientation and uses grep to pull specific topics from daily files as they come up. This scales to months or years of memory without degrading performance.

**Daily files, not a single file.** A monolithic memory file would become unwieldy fast. Daily files keep things naturally organized and make it easy to grep by date range. They also mean Claude only needs to append to today's file rather than rewriting a large document.

**Proactive writes, not end-of-session dumps.** If Claude waits until the end of a session to write memory, it risks losing everything if the session ends unexpectedly (context limit, crash, user closes terminal). The instructions emphasize writing frequently and automatically.

**INDEX.md as a curated summary.** The index isn't auto-generated — Claude maintains it with judgment about what's important enough to surface at session start. This keeps the session-start cost low while still providing good orientation.

**Opinionated instructions.** The CLAUDE.md snippet is deliberately specific about when to write, what to record, and what cadence to maintain. Vague instructions produce inconsistent behavior. The instructions act as a contract between you and Claude about how memory should work.

## Adapting the System

The instructions in `claude-md-snippet.md` are a starting point. You should customize them for how you work:

- **Change what gets recorded.** If you don't care about personal continuity and just want project context, remove the personal memory instructions. If you want Claude to track your learning goals, add that.
- **Adjust the cadence.** The default is aggressive (write after every decision, every chunk of work). If that's too noisy, relax it to key milestones only.
- **Add project-specific sections.** If you're working on a specific codebase, add instructions about what architectural decisions or patterns to track.
- **Change the INDEX.md structure.** The template sections are suggestions. Organize it however makes sense for your work.

## Limitations

- **Context window.** INDEX.md is loaded into Claude's system prompt. Keep it concise — the included instructions note that lines after 200 will be truncated.
- **No cross-device sync.** Memory lives in `~/.claude/memory/`. If you use Claude Code on multiple machines, memory doesn't sync automatically. You could symlink the directory to a synced folder (Dropbox, Syncthing, etc.).
- **Claude's judgment.** Claude decides what to record. It generally does a good job, but it's not perfect. If something important was missed, you can always ask Claude to add it to memory explicitly.
- **Not a database.** This is markdown files and grep. It works surprisingly well for the scale of information one person generates, but it's not designed for structured queries or thousands of entries.

## License

MIT
