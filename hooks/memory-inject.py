#!/usr/bin/env python3
"""SessionStart hook: inject baseline memory context + evolve weights + build section index.

Fires on every session start (startup, resume, clear, compact).
Injects INDEX.md + user.md into Claude's context automatically.
Initializes session state for the UserPromptSubmit hook.
Evolves association weights based on access patterns (decay + strengthening).
Builds section index for mid-session recall.
"""

import datetime
import json
import sys
import time
from pathlib import Path

from memory_common import (
    MEMORY_DIR, TOPICS_DIR, STATE_DIR, ASSOCIATIONS_FILE, ACCESS_LOG_FILE,
    SECTION_INDEX_FILE, ALWAYS_LOADED_FILES, TOPIC_KEYWORDS,
    parse_topic_sections, extract_terms, extract_compound_terms,
    extract_header_terms,
)

MAX_STATE_AGE = 86400  # 24 hours

# Weight evolution constants
STRENGTHEN_THRESHOLD = 5    # Trigger count before strengthening kicks in
STRENGTHEN_STEP = 0.05      # Weight increase per evolution cycle
DECAY_START_DAYS = 7        # Days of inactivity before decay begins
DECAY_STEP = 0.02           # Weight decrease per 7-day period of inactivity
WEIGHT_CEILING = 1.0
WEIGHT_FLOOR = 0.15         # Nothing fully disappears


def cleanup_old_state():
    """Remove state files older than MAX_STATE_AGE."""
    now = time.time()
    try:
        for entry in STATE_DIR.iterdir():
            if entry.suffix == ".json":
                try:
                    if now - entry.stat().st_mtime > MAX_STATE_AGE:
                        entry.unlink()
                except OSError:
                    pass
    except OSError:
        pass


def evolve_weights():
    """Evolve association weights based on access patterns.

    Strengthens frequently-triggered associations and decays inactive ones.
    Only writes to associations.json if any weight actually changed.
    """
    try:
        if not ASSOCIATIONS_FILE.exists() or not ACCESS_LOG_FILE.exists():
            return
        assoc_data = json.loads(ASSOCIATIONS_FILE.read_text())
        access_log = json.loads(ACCESS_LOG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return

    today = datetime.date.today()
    log_created = access_log.get("updated", "")
    any_changed = False

    for link in assoc_data.get("links", []):
        src = link["source"]
        tgt = link["target"]
        link_key = f"{src} -> {tgt}"
        old_weight = link.get("weight", 0.5)
        new_weight = old_weight

        access_entry = access_log.get("associations", {}).get(link_key, {})
        trigger_count = access_entry.get("trigger_count", 0)
        last_triggered = access_entry.get("last_triggered")

        # Strengthening: frequent use nudges weight up
        if trigger_count >= STRENGTHEN_THRESHOLD:
            new_weight = min(WEIGHT_CEILING, new_weight + STRENGTHEN_STEP)

        # Decay: inactivity nudges weight down
        if last_triggered:
            try:
                last_date = datetime.date.fromisoformat(last_triggered)
                days_inactive = (today - last_date).days
            except ValueError:
                days_inactive = 0
        elif log_created:
            # Never triggered — use log creation date as baseline
            try:
                created_date = datetime.date.fromisoformat(log_created)
                days_inactive = (today - created_date).days
            except ValueError:
                days_inactive = 0
        else:
            days_inactive = 0

        if days_inactive >= DECAY_START_DAYS:
            decay_periods = days_inactive // DECAY_START_DAYS
            decay_amount = DECAY_STEP * decay_periods
            new_weight = max(WEIGHT_FLOOR, new_weight - decay_amount)

        # Round to 2 decimal places for clean JSON
        new_weight = round(new_weight, 2)

        if new_weight != old_weight:
            print(
                f"weight evolution: {link_key}: {old_weight:.2f} -> {new_weight:.2f}",
                file=sys.stderr,
            )
            link["weight"] = new_weight
            any_changed = True

    if any_changed:
        assoc_data["updated"] = today.isoformat()
        try:
            ASSOCIATIONS_FILE.write_text(json.dumps(assoc_data, indent=2))
        except OSError:
            pass


def build_section_index():
    """Build section index from all topic files for mid-session recall.

    Parses each topic file (except always-loaded ones) into sections,
    extracts terms, and writes a lookup index to section-index.json.

    Skips rebuild if no topic files have changed since last build.
    """
    if not TOPICS_DIR.exists():
        return

    # Collect topic files to index (skip always-loaded files)
    topic_files = sorted(
        f for f in TOPICS_DIR.iterdir()
        if f.suffix == ".md" and f.name not in ALWAYS_LOADED_FILES
    )

    if not topic_files:
        return

    # Check if rebuild is needed by comparing mtimes
    current_mtimes = {}
    for f in topic_files:
        try:
            current_mtimes[f.name] = f.stat().st_mtime
        except OSError:
            continue

    try:
        if SECTION_INDEX_FILE.exists():
            existing = json.loads(SECTION_INDEX_FILE.read_text())
            stored_mtimes = existing.get("file_mtimes", {})
            # Compare — skip rebuild if all mtimes match
            if all(
                stored_mtimes.get(name) == mtime
                for name, mtime in current_mtimes.items()
            ) and len(stored_mtimes) == len(current_mtimes):
                return
    except (json.JSONDecodeError, OSError):
        pass  # Rebuild on any error

    # Build the index
    index = {
        "version": 1,
        "built": datetime.date.today().isoformat(),
        "file_mtimes": current_mtimes,
        "sections": {},
    }

    for topic_file in topic_files:
        try:
            content = topic_file.read_text()
        except OSError:
            continue

        sections = parse_topic_sections(content)

        for slug, section_content in sections.items():
            if slug == "_preamble":
                continue

            section_id = f"{topic_file.name}#{slug}"

            # Extract the header line for header terms
            first_line = section_content.split("\n", 1)[0]
            header_terms = sorted(extract_header_terms(first_line))

            # Extract body terms (everything after header)
            body_terms_set = extract_terms(section_content)
            # Merge in TOPIC_KEYWORDS for this file — bridges vocabulary gaps
            file_keywords = TOPIC_KEYWORDS.get(topic_file.name, [])
            if file_keywords:
                body_terms_set.update(extract_terms(" ".join(file_keywords)))
            # Remove header terms from body to avoid double-counting
            header_set = set(header_terms)
            body_terms = sorted(body_terms_set - header_set)

            # Extract compound terms from full section content
            compounds = sorted(extract_compound_terms(section_content))

            index["sections"][section_id] = {
                "header_terms": header_terms,
                "body_terms": body_terms,
                "compounds": compounds,
                "char_count": len(section_content),
            }

    try:
        SECTION_INDEX_FILE.write_text(json.dumps(index, indent=2))
        n = len(index["sections"])
        print(f"section index: built with {n} sections", file=sys.stderr)
    except OSError:
        pass


def main():
    hook_input = json.loads(sys.stdin.read())
    session_id = hook_input.get("session_id", "unknown")
    source = hook_input.get("source", "startup")

    # Ensure state directory exists
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Clean up old state files
    cleanup_old_state()

    # Evolve association weights based on access patterns
    evolve_weights()

    # Build section index for mid-session recall
    build_section_index()

    # Initialize session state
    # NOTE: Update "topics_injected" to match your ALWAYS_LOADED_FILES
    state = {
        "prompt_count": 0,
        "topics_injected": list(ALWAYS_LOADED_FILES),
        "sections_injected": [],
        "recall_terms": [],
        "recall_compounds": [],
        "recall_budget_used": 0,
        "last_nudge_prompt": 0,
        "source": source,
        "created_at": time.time(),
    }
    state_file = STATE_DIR / f"{session_id}.json"
    state_file.write_text(json.dumps(state))

    # Build context injection
    parts = []

    # Always inject INDEX.md — project orientation
    index_path = MEMORY_DIR / "INDEX.md"
    if index_path.exists():
        parts.append(index_path.read_text())

    # Always inject the always-loaded topic file(s)
    for filename in sorted(ALWAYS_LOADED_FILES):
        topic_path = TOPICS_DIR / filename
        if topic_path.exists():
            parts.append(topic_path.read_text())

    if not parts:
        sys.exit(0)

    context = "\n\n---\n\n".join(parts)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
    json.dump(output, sys.stdout)


if __name__ == "__main__":
    main()
