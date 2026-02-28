# Claude Code Memory System

A persistent memory system for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) that gives Claude continuity across sessions. Instead of starting every conversation from scratch, Claude remembers context, preferences, project history, and the person it's working with.

This isn't a plugin or extension — it's a set of instructions, conventions, and optional automation hooks that work within Claude Code's existing `CLAUDE.md` configuration system. You paste a snippet into your config, create a directory, and Claude handles the rest.

## Why This Exists

Claude Code is stateless by default. Every session is a blank slate. That's fine for one-off tasks, but if you're working on a project over days or weeks, you end up repeating yourself — re-explaining your setup, your preferences, your project structure, decisions you already made.

This system solves that. Claude writes structured memory files during sessions, maintains topic files that consolidate lasting knowledge, and consults its own memory at the start of each new conversation. The result is something closer to working with a collaborator who actually remembers yesterday.

## Architecture

The system is layered — you can start with just the baseline (markdown files + instructions) and add automation later.

### Baseline: Markdown + Instructions (No Code Required)

The foundation has four parts:

**1. Daily Memory Files** — Each session, Claude writes a markdown file named by date (`YYYY-MM-DD.md`) in `~/.claude/memory/`. These capture decisions, discoveries, preferences, and project context. They use `## Section` headers for greppability.

**2. Topic Files** — Consolidated knowledge organized by subject in `~/.claude/memory/topics/`. Unlike daily files (which are chronological), topic files are living documents that Claude updates as lasting knowledge is confirmed. Examples:

- `user.md` — Who you are: personality, communication style, preferences, interests. This is the most important file — it's what makes Claude feel like it knows you across sessions.
- `system.md` — Your hardware, OS, desktop environment, tools, workarounds.
- Any other topic relevant to your work (a game you play, a project domain, etc.)

**3. INDEX.md** — A curated quick-reference index that provides orientation at session start. Points to topic files, lists active projects, key file locations.

**4. CLAUDE.md Instructions** — Rules that tell Claude how to use the memory system: when to read, when to write, what to record, what to skip.

### Optional: Automation Hooks

Three Python hooks automate what would otherwise require manual instructions:

**SessionStart hook** (`memory-inject.py`) — Fires on every session start. Automatically injects INDEX.md and your always-loaded topic file (e.g., `user.md`) into Claude's context. Also builds a section index for mid-session recall and evolves association weights.

**UserPromptSubmit hook** (`memory-prompt.py`) — Fires on every user message. On the first prompt, it keyword-matches your message against topic files and injects relevant sections. On subsequent prompts, it handles:
- **Mid-session recall** — When conversation drifts to topics not loaded at session start, relevant sections are automatically surfaced
- **Staleness detection** — Warns if the daily memory file hasn't been updated in a while
- **Capture detection** — Nudges Claude when it detects uncaptured memory-worthy content (decisions made, preferences stated, significant work completed)

**Shared utilities** (`memory_common.py`) — Section parsing, term extraction, path constants used by both hooks.

### Optional: Associative Linking

Topic file sections can be cross-referenced via `associations.json`. When a section is loaded, the hooks follow depth-1 associations to surface related sections from other files automatically.

For example, if your system preferences section is associated with your personality section, loading one can surface the other when it's relevant.

Associations have weights that evolve based on usage:
- **Strengthening**: Frequently triggered associations gain weight (+0.05 after 5+ triggers)
- **Decay**: Inactive associations lose weight (-0.02 per 7-day period of inactivity)
- **Floor**: Nothing fully disappears (minimum weight 0.15)

### Optional: Reflect Skill

A `/reflect` skill that periodically consolidates recent daily files into topic files, flags stale information, reviews access patterns, and surfaces recurring themes. Good to run at the start of a session after several days away.

## Setup

### Baseline Setup (No Hooks)

#### 1. Create the memory directory

```bash
mkdir -p ~/.claude/memory/topics
```

#### 2. Create your INDEX.md and topic files

```bash
# Copy templates
cp templates/INDEX.md ~/.claude/memory/INDEX.md
cp templates/topics/user.md ~/.claude/memory/topics/user.md
cp templates/topics/system.md ~/.claude/memory/topics/system.md
```

Or create minimal versions — the templates are just starting points.

#### 3. Add the instructions to CLAUDE.md

Copy the contents of [`claude-md-snippet.md`](claude-md-snippet.md) into your `~/.claude/CLAUDE.md`. If you already have a CLAUDE.md, add the memory section to it.

```bash
# If you don't have a CLAUDE.md yet:
cp claude-md-snippet.md ~/.claude/CLAUDE.md
```

#### 4. Start a session

That's it. Open Claude Code and start working. Claude will read INDEX.md and your always-loaded topic file automatically, and begin writing to daily memory files as the session progresses.

### Adding Hooks (Recommended)

Hooks automate context injection and capture detection. They require Python 3 and Claude Code's hook system.

#### 1. Copy the hook files

```bash
cp hooks/memory_common.py ~/.claude/hooks/
cp hooks/memory-inject.py ~/.claude/hooks/
cp hooks/memory-prompt.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/memory-inject.py ~/.claude/hooks/memory-prompt.py
```

#### 2. Configure the hooks

Add to your `~/.claude/settings.json` (create it if it doesn't exist):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/memory-inject.py",
            "timeout": 5
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/memory-prompt.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**Note:** Replace `~` with your actual home directory path if your shell doesn't expand tildes in JSON (e.g., `/home/yourname/.claude/hooks/memory-inject.py`).

#### 3. Customize the hooks

Edit `~/.claude/hooks/memory_common.py` to configure:

- `ALWAYS_LOADED_FILES` — Which topic files are always injected at session start (default: `{"user.md"}`)
- `TOPIC_KEYWORDS` — Keywords that trigger injection of specific topic files on the first prompt

Edit `~/.claude/hooks/memory-prompt.py` to configure:

- `CWD_HINTS` — Map working directory paths to topic files (e.g., if you're in a game project directory, auto-inject game notes)
- `SECTION_KEYWORDS` — Map prompt keywords to specific sections within large topic files
- `ALWAYS_SECTIONS` — Sections that are always included when a topic file is section-injected
- `SECTION_INJECTED_TOPICS` — Topic files large enough to warrant section-level injection (smaller files are injected whole)

### Adding Associations

#### 1. Create the associations file

```bash
cp templates/associations.json ~/.claude/memory/associations.json
```

#### 2. Let Claude maintain it

The CLAUDE.md instructions tell Claude to maintain associations when updating topic files. Each link has:

```json
{
  "source": "system.md#hardware",
  "target": "user.md#preferences",
  "reason": "Hardware constraints inform preference recommendations",
  "weight": 0.5,
  "bidirectional": true
}
```

The hooks automatically follow associations during injection, track access patterns, and evolve weights over time.

### Adding the Reflect Skill

```bash
mkdir -p ~/.claude/skills/reflect
cp skills/reflect/SKILL.md ~/.claude/skills/reflect/SKILL.md
```

Then use `/reflect` in Claude Code to trigger a consolidation pass.

## Memory Viewer (Optional)

The `viewer/` directory contains a local web app for browsing your memory files. It provides:

- **Index view**: Your INDEX.md rendered as a navigable document
- **Journal view**: All daily memory files as expandable timeline entries
- **Config view**: Your CLAUDE.md rendered for reference
- **Search**: Full-text search across all views
- **Calendar strip**: Visual overview of which days have memory entries

### Installing the viewer

```bash
cp -r viewer ~/.claude/memory/viewer
```

Then run it:

```bash
python3 ~/.claude/memory/viewer/server.py
```

This starts a local server on `http://localhost:8642` and opens your browser. Press `Ctrl+C` to stop.

You can override paths with environment variables:

```bash
MEMORY_DIR=/path/to/memory VIEWER_DIR=/path/to/viewer python3 server.py
```

### Customizing the viewer

The viewer ships with a cyberpunk terminal aesthetic. The theming is all in CSS variables at the top of `style.css`:

```css
:root {
    --bg: #06060c;
    --accent: #00ffd5;
    --pink: #ff2d78;
    --text: #c0d8d0;
}
```

## How It Evolves

The system is designed to grow with use:

1. **Week 1**: Claude writes daily files, you build up context. INDEX.md gets populated.
2. **Week 2+**: Patterns emerge. You (or Claude) create topic files to consolidate lasting knowledge from daily files.
3. **Ongoing**: Topic files become the primary knowledge base. Daily files remain as raw chronological record. `/reflect` keeps things tidy.

The hooks learn too — association weights strengthen for connections that prove useful and decay for ones that don't. Sections that are frequently accessed rise in priority when context budget is limited.

## Design Decisions

**Topic files over a single index.** The original system put everything in daily files + a flat INDEX.md. This works at first but doesn't scale — after a few weeks, important knowledge is scattered across dozens of files. Topic files consolidate lasting knowledge by subject while daily files remain as the raw record.

**Write-gating.** Before adding something to a topic file, ask: "Will this change how a future session behaves?" If yes, topic file. If no, daily file. This prevents topic files from becoming junk drawers.

**Grep over bulk reads.** Claude doesn't load all memory files at session start. It reads INDEX.md and the always-loaded topic file for orientation, then uses grep or section-based injection to pull specific topics as they come up.

**Proactive writes, not end-of-session dumps.** If Claude waits until the end of a session to write memory, it risks losing everything if the session ends unexpectedly. The instructions emphasize writing frequently and automatically.

**Section-based injection for large files.** Small topic files (under ~10KB) are injected whole. Large topic files are parsed into sections and only relevant sections are injected based on keywords. This keeps context usage efficient.

**Decay and strengthening.** Not all cross-references stay equally relevant. The system lets usage patterns shape what gets surfaced — frequently useful connections strengthen, unused ones fade (but never fully disappear).

**Mid-session recall.** Memory shouldn't only be front-loaded at session start. When conversation drifts to topics not initially loaded, the system detects this and surfaces relevant sections automatically. This is closer to how human memory works — things surface because of what's happening in the moment.

## Adapting the System

The instructions and hooks are opinionated starting points. Customize them for how you work:

- **Change what gets recorded.** If you don't care about personal continuity and just want project context, simplify the instructions. If you want Claude to track learning goals, add that.
- **Adjust the cadence.** The default is aggressive (write after every decision, every chunk of work). Relax it if that's too noisy.
- **Add domain-specific topic files.** Working on a game? Create a topic file for it. Building an API? Track the quirks you discover.
- **Customize topic keywords.** The hooks use keyword matching for injection — tune the keywords in `memory_common.py` to match your vocabulary.
- **Adjust budgets.** The hooks have character budgets for section injection, association following, and mid-session recall. Tune them based on how much context you want to spend on memory.

## Limitations

- **Context window.** INDEX.md and the always-loaded topic file are injected into Claude's context. Keep them concise — the built-in auto-memory system truncates after 200 lines.
- **No cross-device sync.** Memory lives in `~/.claude/memory/`. Symlink to a synced folder (Dropbox, Syncthing, etc.) if needed.
- **Claude's judgment.** Claude decides what to record. It's generally good at this, but not perfect. You can always ask Claude to add something to memory explicitly.
- **Hook requirements.** The automation hooks require Python 3. The baseline system works without them.
- **Not a database.** This is markdown files and grep. It works well for the scale of information one person generates, but it's not designed for structured queries or thousands of entries.

## Repository Structure

```
claude-memory/
├── README.md                    # This file
├── claude-md-snippet.md         # Instructions to paste into your CLAUDE.md
├── templates/
│   ├── INDEX.md                 # Template for memory index
│   ├── associations.json        # Empty associations template
│   └── topics/
│       ├── user.md              # Template for personal profile
│       └── system.md            # Template for system/environment info
├── hooks/
│   ├── memory_common.py         # Shared utilities (paths, parsing, terms)
│   ├── memory-inject.py         # SessionStart hook
│   └── memory-prompt.py         # UserPromptSubmit hook
├── skills/
│   └── reflect/
│       └── SKILL.md             # Reflection/consolidation skill
└── viewer/
    ├── server.py                # Local web server
    ├── app.js                   # Frontend application
    ├── style.css                # Cyberpunk terminal theme
    └── index.html               # Web app shell
```

## License

MIT
