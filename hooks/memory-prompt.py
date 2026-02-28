#!/usr/bin/env python3
"""UserPromptSubmit hook: topic injection + mid-session recall + staleness + capture.

Fires on every user prompt. Four concerns:
  1. First prompt (prompt_count == 0): keyword-match and inject relevant topic files,
     follow associative links to surface cross-referenced sections
  2. Subsequent prompts: mid-session recall — score unloaded sections against
     accumulated conversation terms, inject when threshold met
  3. Subsequent prompts: staleness check + capture detection
  4. Always: update session state
"""

import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

from memory_common import (
    MEMORY_DIR, TOPICS_DIR, STATE_DIR, ASSOCIATIONS_FILE, ACCESS_LOG_FILE,
    SECTION_INDEX_FILE, ALWAYS_LOADED_FILES, TOPIC_KEYWORDS,
    parse_topic_sections, section_slug, extract_terms, extract_compound_terms,
)

# Max characters of associated sections from non-primary files (~500 tokens)
ASSOCIATION_CHAR_BUDGET = 2000

# Decay and strengthening
MIN_ASSOCIATION_WEIGHT = 0.25  # Associations below this weight are not auto-surfaced
SECTION_CHAR_BUDGET = 10000   # Max chars of keyword-matched sections before prominence ranking

# Mid-session recall
RECALL_SCORE_THRESHOLD = 3     # Minimum raw score to trigger injection
RECALL_PER_INJECTION_CAP = 4000  # Max chars per single recall injection
RECALL_SESSION_CAP = 12000     # Max total chars from mid-session recall per session

# If cwd contains these path fragments, auto-inject the topic.
# Customize for your projects — map directory names to topic files.
CWD_HINTS = {
    # Example: "my-project": "project-notes.md",
}

# Sections to always include when a topic file is section-injected.
# Only relevant for large topic files listed in SECTION_INJECTED_TOPICS.
ALWAYS_SECTIONS = {
    # Example for a large topic file:
    # "project-notes.md": [
    #     "key-decisions",
    #     "known-issues",
    # ],
}

# Map prompt keywords to section slugs within each topic file.
# This enables fine-grained injection — only relevant sections of large files
# are loaded based on what the user is asking about.
SECTION_KEYWORDS = {
    # Example for a large topic file:
    # "project-notes.md": {
    #     "api": ["api-design"],
    #     "deploy": ["deployment-notes"],
    #     "bug": ["known-issues"],
    #     "database": ["data-model"],
    # },
}

# Topic files large enough to warrant section-level injection.
# Small files (< ~10KB) are injected whole; large files use keyword matching
# to inject only relevant sections.
SECTION_INJECTED_TOPICS = set()
# Example: SECTION_INJECTED_TOPICS = {"project-notes.md"}

# --- Capture detection ---

DECISION_PATTERNS = [
    r"\b(?:let'?s go with|i'?ll take|decided?|choose|pick|prefer|go ahead)\b",
    r"\b(?:don'?t like|not that|instead|actually|change to|switch to)\b",
    r"\b(?:found|discovered|turns out|realized|noticed|workaround|fix)\b",
    r"\b(?:remember|always|never)\b.*\b(?:use|do|want|like)\b",
]

SIGNAL_WEIGHTS = {
    "time_elapsed": 2,
    "user_messages": 1,
    "file_writes": 2,
    "decision_language": 3,
}

NUDGE_THRESHOLD = 3
NUDGE_COOLDOWN_PROMPTS = 3
STALENESS_SECONDS = 1800  # 30 minutes


# --- Access log ---

def load_access_log():
    """Load access-log.json, returning empty structure if missing."""
    try:
        if ACCESS_LOG_FILE.exists():
            return json.loads(ACCESS_LOG_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {"version": 1, "updated": "", "sections": {}, "associations": {}}


def save_access_log(data):
    """Write access-log.json with updated timestamp."""
    data["updated"] = datetime.date.today().isoformat()
    try:
        ACCESS_LOG_FILE.write_text(json.dumps(data, indent=2))
    except OSError:
        pass


def record_access(injected_section_ids, triggered_link_keys):
    """Record section and association access to access-log.json."""
    today = datetime.date.today().isoformat()
    log = load_access_log()

    for section_id in injected_section_ids:
        entry = log["sections"].setdefault(section_id, {
            "access_count": 0, "last_accessed": None, "exempt": False
        })
        entry["access_count"] += 1
        entry["last_accessed"] = today

    for link_key in triggered_link_keys:
        entry = log["associations"].setdefault(link_key, {
            "trigger_count": 0, "last_triggered": None
        })
        entry["trigger_count"] += 1
        entry["last_triggered"] = today

    save_access_log(log)


# --- Associations ---

def load_associations():
    """Load association graph from associations.json."""
    try:
        if ASSOCIATIONS_FILE.exists():
            data = json.loads(ASSOCIATIONS_FILE.read_text())
            graph = {}
            for link in data.get("links", []):
                src = link["source"]
                tgt = link["target"]
                weight = link.get("weight", 0.5)
                graph.setdefault(src, []).append((tgt, weight))
                if link.get("bidirectional", False):
                    graph.setdefault(tgt, []).append((src, weight))
            return graph
    except (json.JSONDecodeError, OSError, KeyError):
        pass
    return {}


def follow_associations(graph, matched_ids, already_injected_files):
    """Follow depth-1 associations from matched section IDs, filtered by weight."""
    extra = {}  # filename -> {slug: weight}
    triggered_links = []

    for section_id in matched_ids:
        for target_id, weight in graph.get(section_id, []):
            if weight < MIN_ASSOCIATION_WEIGHT:
                continue
            if "#" not in target_id:
                continue
            filename, slug = target_id.split("#", 1)
            if filename in already_injected_files:
                continue
            current = extra.get(filename, {}).get(slug, 0)
            extra.setdefault(filename, {})[slug] = max(current, weight)
            triggered_links.append(f"{section_id} -> {target_id}")

    return extra, triggered_links


def inject_associated_sections(extra_by_file):
    """Read and extract associated sections, prioritized by weight, within budget."""
    if not extra_by_file:
        return ""

    candidates = []
    for filename, slug_weights in extra_by_file.items():
        for slug, weight in slug_weights.items():
            candidates.append((weight, filename, slug))
    candidates.sort(key=lambda x: x[0], reverse=True)

    parts = []
    total_chars = 0
    file_sections_cache = {}

    for weight, filename, slug in candidates:
        if filename not in file_sections_cache:
            topic_path = TOPICS_DIR / filename
            if not topic_path.exists():
                continue
            file_sections_cache[filename] = parse_topic_sections(topic_path.read_text())

        sections = file_sections_cache[filename]
        if slug not in sections:
            continue
        section_content = sections[slug]
        if total_chars + len(section_content) <= ASSOCIATION_CHAR_BUDGET:
            parts.append(section_content)
            total_chars += len(section_content)

    if not parts:
        return ""

    return (
        "[Associated context — cross-referenced from matched topics]\n\n"
        + "\n\n".join(parts)
    )


# --- State management ---

def load_state(session_id):
    """Load session state, returning defaults if missing or corrupt."""
    state_file = STATE_DIR / f"{session_id}.json"
    try:
        if state_file.exists():
            return json.loads(state_file.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {
        "prompt_count": 1,
        "topics_injected": [],
        "sections_injected": [],
        "recall_terms": [],
        "recall_compounds": [],
        "recall_budget_used": 0,
        "last_nudge_prompt": 0,
        "source": "unknown",
        "created_at": time.time(),
    }


def save_state(session_id, state):
    """Save session state."""
    state_file = STATE_DIR / f"{session_id}.json"
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state))
    except OSError:
        pass


# --- First prompt: topic injection + association following ---

def extract_topic_sections(topic_file, prompt_lower, sections):
    """Determine which sections of a topic file to inject based on keywords."""
    matched_slugs = set()

    # Always-include sections
    for slug in ALWAYS_SECTIONS.get(topic_file, []):
        if slug in sections:
            matched_slugs.add(slug)

    # Keyword-matched sections
    kw_map = SECTION_KEYWORDS.get(topic_file, {})
    for keyword, slugs in kw_map.items():
        if keyword in prompt_lower:
            for slug in slugs:
                if slug in sections:
                    matched_slugs.add(slug)

    if not matched_slugs:
        # No specific matches — inject full file
        full_content = "\n".join(
            sections[slug] for slug in sections
        )
        return full_content, set(sections.keys()) - {"_preamble"}

    # Check if keyword-matched sections (excluding always-sections) exceed budget
    always = set(ALWAYS_SECTIONS.get(topic_file, []))
    keyword_matched = matched_slugs - always
    keyword_chars = sum(len(sections[s]) for s in keyword_matched if s in sections)

    if keyword_chars > SECTION_CHAR_BUDGET and len(keyword_matched) > 1:
        # Budget-constrained: rank keyword-matched sections by prominence
        access_log = load_access_log()
        ranked = []
        for slug in keyword_matched:
            section_id = f"{topic_file}#{slug}"
            entry = access_log.get("sections", {}).get(section_id, {})
            count = entry.get("access_count", 0)
            last = entry.get("last_accessed")
            if last:
                try:
                    days_ago = (datetime.date.today() - datetime.date.fromisoformat(last)).days
                except ValueError:
                    days_ago = 60
                recency = max(0.2, 1.0 - (days_ago / 60))
            else:
                recency = 0.2
            prominence = count * recency
            ranked.append((prominence, slug))
        ranked.sort(reverse=True)

        result_parts = []
        for slug in sections:
            if slug in always:
                result_parts.append(sections[slug])

        budget_used = 0
        for prominence, slug in ranked:
            section_content = sections[slug]
            if budget_used + len(section_content) <= SECTION_CHAR_BUDGET:
                result_parts.append(section_content)
                budget_used += len(section_content)
            else:
                matched_slugs.discard(slug)

        return "\n\n".join(result_parts), matched_slugs

    # Preserve original section order
    result_parts = []
    for slug in sections:
        if slug in matched_slugs:
            result_parts.append(sections[slug])

    return "\n\n".join(result_parts), matched_slugs


def handle_first_prompt(prompt, cwd, state):
    """Keyword-match the first prompt, follow associations, return relevant context."""
    prompt_lower = f" {prompt.lower()} "
    injected = list(state.get("topics_injected", []))
    sections_injected = list(state.get("sections_injected", []))
    context_parts = []
    all_matched_ids = set()

    # Collect topic files to inject (CWD + keyword matching)
    topics_to_inject = []

    # CWD-based injection
    for path_fragment, topic_file in CWD_HINTS.items():
        if topic_file and path_fragment in cwd and topic_file not in injected:
            topic_path = TOPICS_DIR / topic_file
            if topic_path.exists():
                topics_to_inject.append((topic_file, topic_path.read_text()))
                injected.append(topic_file)

    # Keyword-based injection
    for topic_file, keywords in TOPIC_KEYWORDS.items():
        if topic_file in injected:
            continue
        if any(kw in prompt_lower for kw in keywords):
            topic_path = TOPICS_DIR / topic_file
            if topic_path.exists():
                topics_to_inject.append((topic_file, topic_path.read_text()))
                injected.append(topic_file)

    # Inject each matched topic file (section-based or whole)
    for topic_file, content in topics_to_inject:
        if topic_file in SECTION_INJECTED_TOPICS:
            sections = parse_topic_sections(content)
            extracted, matched_slugs = extract_topic_sections(
                topic_file, prompt_lower, sections
            )
            context_parts.append(extracted)
            for slug in matched_slugs:
                section_id = f"{topic_file}#{slug}"
                all_matched_ids.add(section_id)
                if section_id not in sections_injected:
                    sections_injected.append(section_id)
        else:
            # Whole file injected — mark ALL sections as injected
            context_parts.append(content)
            sections = parse_topic_sections(content)
            for slug in sections:
                if slug != "_preamble":
                    section_id = f"{topic_file}#{slug}"
                    if section_id not in sections_injected:
                        sections_injected.append(section_id)

    # Follow associations (depth=1, weight-filtered)
    triggered_links = []
    if all_matched_ids:
        assoc_graph = load_associations()
        if assoc_graph:
            already_injected = set(injected)
            extra_by_file, triggered_links = follow_associations(
                assoc_graph, all_matched_ids, already_injected
            )
            associated_context = inject_associated_sections(extra_by_file)
            if associated_context:
                context_parts.append(associated_context)
                state["associations_followed"] = sorted(all_matched_ids)
                state["associations_injected"] = sorted(
                    f"{f}#{s}" for f, slugs in extra_by_file.items() for s in slugs
                )
                # Track associated sections as injected too
                for f, slugs in extra_by_file.items():
                    for s in slugs:
                        sid = f"{f}#{s}"
                        if sid not in sections_injected:
                            sections_injected.append(sid)

    # Record access for decay/strengthening
    if all_matched_ids or triggered_links:
        record_access(all_matched_ids, triggered_links)

    state["topics_injected"] = injected
    state["sections_injected"] = sections_injected
    return "\n\n---\n\n".join(context_parts) if context_parts else ""


# --- Mid-session recall ---

def score_section(section_entry, recall_terms_set, recall_compounds_set):
    """Score a section against accumulated recall terms.

    Returns a raw score (int). Higher = more relevant.
    No normalization — raw match counts are the signal.
    Header matches weighted 2x (section name is strong signal).
    Compound matches weighted 4x (precise multi-word terms).
    Threshold is applied externally (RECALL_SCORE_THRESHOLD).
    """
    header_terms = set(section_entry["header_terms"])
    body_terms = set(section_entry["body_terms"])
    compounds = set(section_entry["compounds"])

    header_matches = len(header_terms & recall_terms_set)
    body_matches = len(body_terms & recall_terms_set)
    compound_matches = len(compounds & recall_compounds_set)

    return (header_matches * 2) + body_matches + (compound_matches * 4)


def handle_mid_session_recall(prompt, state):
    """Check for mid-session recall opportunities.

    Extracts terms from the user's message, accumulates them in session state,
    and scores unloaded sections against the accumulated term set.

    Returns context string to inject (or "") and list of newly injected section IDs.
    """
    # Extract terms from current message
    message_terms = extract_terms(prompt)
    message_compounds = extract_compound_terms(prompt)

    # Accumulate terms across session
    existing_terms = set(state.get("recall_terms", []))
    existing_terms.update(message_terms)
    state["recall_terms"] = sorted(existing_terms)

    # Accumulate compounds across session
    existing_compounds = set(state.get("recall_compounds", []))
    existing_compounds.update(message_compounds)
    state["recall_compounds"] = sorted(existing_compounds)

    # Load section index
    try:
        if not SECTION_INDEX_FILE.exists():
            return "", []
        index = json.loads(SECTION_INDEX_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return "", []

    sections_data = index.get("sections", {})
    if not sections_data:
        return "", []

    # What's already in context?
    already_injected = set(state.get("sections_injected", []))
    topics_injected = set(state.get("topics_injected", []))

    # Budget check
    budget_used = state.get("recall_budget_used", 0)
    budget_remaining = RECALL_SESSION_CAP - budget_used
    if budget_remaining <= 0:
        return "", []

    # Score against accumulated terms and compounds
    recall_terms_set = existing_terms
    recall_compounds_set = existing_compounds

    candidates = []
    for section_id, entry in sections_data.items():
        # Skip if already in context
        if section_id in already_injected:
            continue

        # Skip if the whole file is already loaded (non-section-injected files)
        file_name = section_id.split("#")[0]
        if file_name in topics_injected and file_name not in SECTION_INJECTED_TOPICS:
            continue

        # Skip if file is always loaded
        if file_name in ALWAYS_LOADED_FILES:
            continue

        score = score_section(entry, recall_terms_set, recall_compounds_set)
        if score >= RECALL_SCORE_THRESHOLD:
            candidates.append((score, section_id, entry["char_count"]))

    if not candidates:
        return "", []

    # Sort by score descending
    candidates.sort(key=lambda x: x[0], reverse=True)

    # Inject top candidates within budget
    parts = []
    injected_ids = []
    injection_chars = 0
    file_sections_cache = {}

    for score, section_id, char_count in candidates:
        # Check per-injection and session budgets
        if injection_chars + char_count > RECALL_PER_INJECTION_CAP:
            continue
        if budget_used + injection_chars + char_count > RECALL_SESSION_CAP:
            continue

        # Read the actual section content
        file_name, slug = section_id.split("#", 1)
        if file_name not in file_sections_cache:
            topic_path = TOPICS_DIR / file_name
            if not topic_path.exists():
                continue
            file_sections_cache[file_name] = parse_topic_sections(
                topic_path.read_text()
            )

        sections = file_sections_cache[file_name]
        if slug not in sections:
            continue

        content = sections[slug]
        parts.append(content)
        injected_ids.append(section_id)
        injection_chars += len(content)

        print(
            f"mid-session recall: {section_id} (score={score:.2f}, "
            f"chars={len(content)})",
            file=sys.stderr,
        )

    if not parts:
        return "", []

    # Update budget
    state["recall_budget_used"] = budget_used + injection_chars

    context = (
        "[Mid-session recall — surfaced by conversation context]\n\n"
        + "\n\n---\n\n".join(parts)
    )
    return context, injected_ids


# --- Subsequent prompts: staleness + capture detection ---

def check_staleness():
    """Check if today's daily memory file is stale (>30 min since last write)."""
    today = datetime.date.today().isoformat()
    memory_file = MEMORY_DIR / f"{today}.md"

    if memory_file.exists():
        try:
            last_mod = memory_file.stat().st_mtime
            elapsed = time.time() - last_mod
            if elapsed > STALENESS_SECONDS:
                mins = int(elapsed / 60)
                return (
                    f"MEMORY STALENESS: Today's daily file hasn't been updated "
                    f"in {mins} minutes. If meaningful work has happened, update "
                    f"~/.claude/memory/{today}.md now. Also check if topic files "
                    f"in topics/ need updates with lasting knowledge."
                )
        except OSError:
            pass
    else:
        if TOPICS_DIR.exists():
            return (
                f"MEMORY: No daily memory file exists for today ({today}). "
                f"Create ~/.claude/memory/{today}.md when meaningful work begins."
            )

    return ""


def find_last_memory_write(transcript_path):
    """Find the ISO timestamp of the most recent Write/Edit to a memory file."""
    if not transcript_path or not os.path.exists(transcript_path):
        return ""

    last_ts = ""
    try:
        with open(transcript_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") != "assistant":
                    continue

                msg = entry.get("message", {})
                content = msg.get("content", [])
                if not isinstance(content, list):
                    continue

                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use":
                        continue
                    name = block.get("name", "")
                    inp = block.get("input", {})
                    if name in ("Write", "Edit"):
                        fp = inp.get("file_path", "")
                        if ".claude/memory" in fp:
                            ts = entry.get("timestamp", "")
                            if ts > last_ts:
                                last_ts = ts
    except OSError:
        pass

    return last_ts


def iso_to_epoch(ts_str):
    """Convert ISO 8601 timestamp to epoch seconds."""
    if not ts_str:
        return 0
    try:
        ts_str = ts_str.rstrip("Z")
        if "." in ts_str:
            dt = datetime.datetime.fromisoformat(ts_str)
        else:
            dt = datetime.datetime.fromisoformat(ts_str)
        return dt.replace(tzinfo=datetime.timezone.utc).timestamp()
    except (ValueError, AttributeError):
        return 0


def detect_capture_signals(transcript_path, last_memory_write_ts):
    """Scan transcript for uncaptured memory-worthy content."""
    if not transcript_path or not os.path.exists(transcript_path):
        return []

    signals = []
    last_write_epoch = iso_to_epoch(last_memory_write_ts)

    user_message_count = 0
    write_edit_count = 0
    found_decision = False

    try:
        with open(transcript_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_ts = iso_to_epoch(entry.get("timestamp", ""))

                if last_write_epoch > 0 and entry_ts <= last_write_epoch:
                    continue

                entry_type = entry.get("type", "")

                if entry_type == "user":
                    user_message_count += 1
                    if not found_decision:
                        msg = entry.get("message", {})
                        content = msg.get("content", "")
                        if isinstance(content, list):
                            content = " ".join(
                                b.get("text", "")
                                for b in content
                                if isinstance(b, dict)
                            )
                        content_lower = content.lower()
                        for pattern in DECISION_PATTERNS:
                            if re.search(pattern, content_lower):
                                found_decision = True
                                break

                elif entry_type == "assistant":
                    msg = entry.get("message", {})
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            if block.get("type") == "tool_use":
                                name = block.get("name", "")
                                if name in ("Write", "Edit"):
                                    fp = block.get("input", {}).get("file_path", "")
                                    if ".claude/memory" not in fp:
                                        write_edit_count += 1
    except OSError:
        return []

    score = 0

    if last_write_epoch > 0:
        elapsed = time.time() - last_write_epoch
        if elapsed > 900:
            mins = int(elapsed / 60)
            signals.append(f"{mins} minutes since last memory update")
            score += SIGNAL_WEIGHTS["time_elapsed"]
    else:
        if user_message_count >= 3:
            signals.append("No memory updates this session")
            score += SIGNAL_WEIGHTS["time_elapsed"]

    if user_message_count >= 5:
        signals.append(f"{user_message_count} user messages since last memory update")
        score += SIGNAL_WEIGHTS["user_messages"]

    if write_edit_count >= 3:
        signals.append(f"{write_edit_count} file writes/edits (significant work completed)")
        score += SIGNAL_WEIGHTS["file_writes"]

    if found_decision:
        signals.append("User expressed a decision or preference")
        score += SIGNAL_WEIGHTS["decision_language"]

    if score >= NUDGE_THRESHOLD:
        return signals
    return []


def build_capture_nudge(signals):
    """Build a capture reminder from detected signals."""
    today = datetime.date.today().isoformat()
    signal_list = "\n".join(f"  - {s}" for s in signals)
    return (
        f"MEMORY CAPTURE: The following signals suggest uncaptured "
        f"memory-worthy content:\n{signal_list}\n"
        f"Consider updating ~/.claude/memory/{today}.md and checking "
        f"if topic files need updates. Focus on: decisions made, "
        f"preferences stated, discoveries or workarounds found."
    )


def main():
    hook_input = json.loads(sys.stdin.read())
    session_id = hook_input.get("session_id", "unknown")
    prompt = hook_input.get("prompt", "")
    transcript_path = hook_input.get("transcript_path", "")
    cwd = hook_input.get("cwd", "")

    state = load_state(session_id)
    context_parts = []

    if state["prompt_count"] == 0:
        # FIRST PROMPT: topic injection + association following
        topic_context = handle_first_prompt(prompt, cwd, state)
        if topic_context:
            context_parts.append(topic_context)
    else:
        # SUBSEQUENT PROMPTS: mid-session recall + staleness + capture detection

        # 1. Mid-session recall
        recall_context, recalled_ids = handle_mid_session_recall(prompt, state)
        if recall_context:
            context_parts.append(recall_context)
            # Update sections_injected
            sections_injected = list(state.get("sections_injected", []))
            sections_injected.extend(recalled_ids)
            state["sections_injected"] = sections_injected
            # Record access for decay/strengthening
            record_access(set(recalled_ids), [])

        # 2. Staleness check
        staleness_msg = check_staleness()
        if staleness_msg:
            context_parts.append(staleness_msg)

        # 3. Capture detection (with anti-spam)
        last_nudge = state.get("last_nudge_prompt", 0)
        current_prompt = state["prompt_count"]
        if current_prompt - last_nudge >= NUDGE_COOLDOWN_PROMPTS:
            last_write_ts = find_last_memory_write(transcript_path)
            signals = detect_capture_signals(transcript_path, last_write_ts)
            if signals:
                nudge = build_capture_nudge(signals)
                context_parts.append(nudge)
                state["last_nudge_prompt"] = current_prompt

    # Update state
    state["prompt_count"] = state.get("prompt_count", 0) + 1
    save_state(session_id, state)

    # Output
    if context_parts:
        context = "\n\n".join(context_parts)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": context,
            }
        }
        json.dump(output, sys.stdout)


if __name__ == "__main__":
    main()
