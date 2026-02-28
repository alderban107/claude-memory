"""Shared utilities for memory hooks.

Section parsing, term extraction, and common paths used by both
memory-inject.py (SessionStart) and memory-prompt.py (UserPromptSubmit).
"""

import re
from pathlib import Path

MEMORY_DIR = Path.home() / ".claude" / "memory"
TOPICS_DIR = MEMORY_DIR / "topics"
STATE_DIR = Path.home() / ".claude" / "hooks" / ".state"
ASSOCIATIONS_FILE = MEMORY_DIR / "associations.json"
ACCESS_LOG_FILE = MEMORY_DIR / "access-log.json"
SECTION_INDEX_FILE = MEMORY_DIR / "section-index.json"

# Files that are always fully loaded at session start (skip indexing for recall).
# Add your always-loaded topic file(s) here.
ALWAYS_LOADED_FILES = {"user.md"}

# Topic-level keywords — used for first-prompt injection AND index enrichment.
# These bridge vocabulary gaps between how users talk and how things are documented
# in topic files. For example, a user might say "my GPU" but the hardware section
# says "NVIDIA RTX 4070" — adding "gpu" and "nvidia" here bridges that gap.
#
# Customize these for your topic files. The keys are topic filenames,
# the values are lists of keywords that should trigger injection of that file.
TOPIC_KEYWORDS = {
    # Example: uncomment and customize for your topics
    # "project-notes.md": [
    #     "project", "api", "endpoint", "deploy", "database",
    # ],
    "system.md": [
        "hardware", "gpu", "cpu", "monitor", "driver",
        "desktop", "wayland", "config", "shell", "terminal",
        "font", "theme", "browser", "package",
    ],
}

# --- Stopwords for term extraction ---

STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "this", "that",
    "these", "those", "me", "him", "her", "us", "them", "my", "your",
    "his", "its", "our", "their", "what", "which", "who", "whom", "where",
    "when", "why", "how", "not", "no", "nor", "so", "if", "then", "than",
    "too", "very", "just", "about", "also", "some", "any", "all", "each",
    "every", "both", "few", "more", "most", "other", "into", "over",
    "such", "only", "same", "as", "up", "out", "here", "there", "been",
    "she", "he", "it", "we", "they", "you", "i",
})


# --- Section parsing ---

def section_slug(header_text):
    """Convert a ## header line to a URL-style slug.

    '## Things We Got Wrong (Corrections / Bad Advice)' -> 'things-we-got-wrong'
    '## Money-Making Methods — Tried and Evaluated' -> 'money-making-methods'
    """
    text = header_text.lstrip("#").strip()
    text = re.split(r"\s*[\(\[\—]", text)[0].strip()
    text = text.replace("'", "")
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug


def parse_topic_sections(content):
    """Parse any topic file into {slug: content_string} at ## level.

    Returns an ordered dict (insertion order) of slug -> content.
    The preamble (content before the first ##) gets slug '_preamble'.
    """
    sections = {}
    current_slug = "_preamble"
    current_lines = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_lines:
                sections[current_slug] = "\n".join(current_lines)
            current_slug = section_slug(line)
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_slug] = "\n".join(current_lines)

    return sections


# --- Term extraction ---

_WORD_SPLIT_RE = re.compile(r"[^a-zA-Z0-9]+")


def extract_terms(text):
    """Extract significant single-word terms from text.

    Returns a set of lowercase terms, filtered for stopwords, length, and noise.
    """
    words = _WORD_SPLIT_RE.split(text.lower())
    return {
        w for w in words
        if len(w) >= 3
        and w not in STOPWORDS
        and not w.isdigit()           # skip pure numbers
        and not re.match(r"^\d+[kmb]?$", w)  # skip "140k", "15m"
    }


# Words that start sentences but aren't meaningful compound components
_COMPOUND_STOP = frozenset({
    "the", "this", "that", "these", "those", "when", "where", "what",
    "how", "who", "which", "each", "every", "also", "but", "and",
    "for", "from", "with", "use", "using", "used", "note", "see",
    "set", "get", "can", "will", "may", "not", "all", "has", "had",
    "was", "are", "been", "does", "did", "its", "our", "per", "via",
    "pre", "non", "new", "old", "now", "yet", "try", "let", "run",
    "add", "any", "few", "max", "min", "raw", "top", "key",
    "currently", "because", "however", "verified", "discovered",
    "confirmed", "returns", "requires", "applies", "checked",
    "instead", "actually", "important", "example", "tested",
    "updated", "removed", "added", "fixed", "moved", "works",
    "evaluated", "current", "best", "first", "last", "still",
})


def extract_compound_terms(text):
    """Find consecutive capitalized words as compound terms.

    'Experimentation Table' -> {'experimentation table'}
    'Shadow Assassin armor' -> {'shadow assassin'}

    Filters aggressively to avoid sentence-initial false positives.
    Only keeps 2-3 word compounds where all words are meaningful.
    """
    compounds = set()
    # Remove markdown formatting
    clean = re.sub(r"\*\*|`|#{1,6}\s*|\|", "", text)
    # Merge stop sets for compound filtering
    stop = _COMPOUND_STOP | STOPWORDS

    for line in clean.split("\n"):
        words = line.split()
        if not words:
            continue
        i = 0
        # Skip first word of each line (sentence-initial capitalization)
        start = 0
        stripped = line.lstrip()
        if stripped.startswith(("-", "*", "\u2022")):
            start = 1  # skip the marker
        else:
            start = 1  # skip sentence-initial word

        while i < len(words):
            word = words[i].strip(".,;:!?()[]{}\"':")
            if (word and len(word) >= 3 and word[0].isupper() and word.isalpha()
                    and word.lower() not in stop and i >= start):
                compound = [word]
                j = i + 1
                while j < len(words) and len(compound) < 3:
                    next_word = words[j].strip(".,;:!?()[]{}\"':")
                    if (next_word and len(next_word) >= 3
                            and next_word[0].isupper() and next_word.isalpha()
                            and next_word.lower() not in stop):
                        compound.append(next_word)
                        j += 1
                    else:
                        break
                if len(compound) >= 2:
                    compounds.add(" ".join(compound).lower())
                i = j
            else:
                i += 1
    return compounds


def extract_header_terms(header_line):
    """Extract terms from a section header line (## Header Text).

    Returns terms from just the header text, which get weighted higher in scoring.
    """
    text = header_line.lstrip("#").strip()
    # Take text before parenthetical/bracket/em-dash (same as section_slug but keep words)
    text = re.split(r"\s*[\(\[\—]", text)[0].strip()
    return extract_terms(text)
