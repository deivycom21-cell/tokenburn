"""Read and parse Claude Code session JSONL files."""

import json
from pathlib import Path


class ParseError(Exception):
    """Raised when a session file cannot be parsed."""


def parse_jsonl(path: Path) -> list[dict]:
    """Parse a Claude Code session JSONL file.

    Raises ParseError on malformed input so callers never receive partial data.
    Returns an empty list for empty files.
    """
    if not path.exists():
        raise FileNotFoundError(f"Session file not found: {path}")

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []

    records: list[dict] = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ParseError(
                f"Malformed JSONL in {path}, line {lineno}: {exc}\n"
                "TokenBurn cannot analyze this session. No partial numbers will be shown."
            ) from exc

    return records


def find_sessions(projects_dir: Path | None = None) -> list[Path]:
    """Return all Claude Code session JSONL files, sorted by path."""
    if projects_dir is None:
        projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return []
    return sorted(projects_dir.glob("**/*.jsonl"))
