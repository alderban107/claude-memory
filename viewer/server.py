#!/usr/bin/env python3
"""Memory viewer — lightweight local server for browsing Claude's memory files."""

import http.server
import json
import os
import re
import socketserver
import threading
import webbrowser
from pathlib import Path

PORT = 8642
MEMORY_DIR = Path.home() / ".claude" / "memory"
VIEWER_DIR = MEMORY_DIR / "viewer"

# Allow overriding paths via environment variables
if os.environ.get("MEMORY_DIR"):
    MEMORY_DIR = Path(os.environ["MEMORY_DIR"])
if os.environ.get("VIEWER_DIR"):
    VIEWER_DIR = Path(os.environ["VIEWER_DIR"])


def get_memories():
    """Read all memory markdown files and return as structured data."""
    memories = []
    for f in sorted(MEMORY_DIR.glob("*.md"), reverse=True):
        if f.name == "INDEX.md":
            continue
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
        date = date_match.group(1) if date_match else f.stem
        content = f.read_text(encoding="utf-8")

        # Extract ## sections
        sections = []
        current_title = None
        current_lines = []
        for line in content.split("\n"):
            if line.startswith("## "):
                if current_title is not None:
                    sections.append({"title": current_title, "content": "\n".join(current_lines).strip()})
                current_title = line[3:].strip()
                current_lines = []
            elif current_title is not None:
                current_lines.append(line)
            # Skip lines before first ## (the # date header)
        if current_title is not None:
            sections.append({"title": current_title, "content": "\n".join(current_lines).strip()})

        memories.append({
            "date": date,
            "filename": f.name,
            "sections": sections,
            "raw": content,
        })
    return memories


def get_index():
    """Read INDEX.md and return its content."""
    index_path = MEMORY_DIR / "INDEX.md"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "# No INDEX.md found"


def get_config():
    """Read CLAUDE.md and return its content."""
    config_path = Path.home() / ".claude" / "CLAUDE.md"
    if config_path.exists():
        return config_path.read_text(encoding="utf-8")
    return "# No CLAUDE.md found"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(VIEWER_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/memories":
            data = json.dumps(get_memories())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(data.encode()))
            self.end_headers()
            self.wfile.write(data.encode())
        elif self.path == "/api/index":
            data = json.dumps({"content": get_index()})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(data.encode()))
            self.end_headers()
            self.wfile.write(data.encode())
        elif self.path == "/api/config":
            data = json.dumps({"content": get_config()})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", len(data.encode()))
            self.end_headers()
            self.wfile.write(data.encode())
        else:
            super().do_GET()

    def log_message(self, format, *args):
        # Suppress default request logging
        pass


def main():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}"
        print(f"Memory viewer running at {url}")
        print("Press Ctrl+C to stop")
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")
            httpd.shutdown()


if __name__ == "__main__":
    main()
