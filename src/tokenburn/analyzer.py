"""Core burn and scope analysis for Claude Code sessions.

Burn rule (Deivy, 6 nov): only writes whose result does not survive in the
final diff are counted.  Within a session this means: a write to file F in
turn T is burned when a later turn also writes to F (overwriting the work).
A turn is counted as burned if it has file writes AND every one of those
writes is later overwritten.  Bash commands without a traceable file path
are excluded from burn tracking (conservative: we cannot determine their
effect without executing the session).

The rule and mapping are intentional and documented in the README.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .prices import calculate_cost

# Tools that constitute unambiguous file writes.
_WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}

# Shell patterns that indicate file modification.
_BASH_WRITE_RES = [
    re.compile(r"\s>>?\s"),           # output/append redirect
    re.compile(r"\|\s*tee\b"),        # pipe to tee
    re.compile(r"\brm\b"),            # delete
    re.compile(r"\bmv\b"),            # move/rename
    re.compile(r"\bcp\b"),            # copy
    re.compile(r"\bmkdir\b"),         # create directory
    re.compile(r"\btouch\b"),         # create/update file
    re.compile(r"\bsed\s+-i\b"),      # in-place sed
    re.compile(r"\bgit\s+(add|commit|push)\b"),
    re.compile(r"\bnpm\s+install\b"),
    re.compile(r"\bpip\s+install\b"),
    re.compile(r"\bchmod\b"),
    re.compile(r"\bchown\b"),
    re.compile(r"\btruncate\b"),
]

# Shell patterns for read-only / check-only commands.
_BASH_CHECK_RES = [
    re.compile(r"^pytest\b"),
    re.compile(r"^python\s+-m\s+pytest\b"),
    re.compile(r"^npm\s+(run\s+)?test\b"),
    re.compile(r"^npx\s+jest\b"),
    re.compile(r"^cargo\s+test\b"),
    re.compile(r"^go\s+test\b"),
    re.compile(r"^eslint\b"),
    re.compile(r"^flake8\b"),
    re.compile(r"^mypy\b"),
    re.compile(r"^ruff\s+check\b"),
    re.compile(r"^black\s+--check\b"),
    re.compile(r"^isort\s+--check\b"),
    re.compile(r"^make\s+(test|lint|check|typecheck|format-check)\b"),
    re.compile(r"^cat\b"),
    re.compile(r"^ls\b"),
    re.compile(r"^grep\b"),
    re.compile(r"^find\b"),
    re.compile(r"^head\b"),
    re.compile(r"^tail\b"),
    re.compile(r"^wc\b"),
    re.compile(r"^diff\b"),
    re.compile(r"^git\s+(log|status|diff|show|branch|remote)\b"),
    re.compile(r"^echo\b"),
    re.compile(r"^printf\b"),
    re.compile(r"^which\b"),
    re.compile(r"^type\b"),
    re.compile(r"^python\b"),          # python script execution (read-only by default)
    re.compile(r"^node\b"),
]


def _bash_is_write(cmd: str) -> bool:
    """Heuristic: return True if this Bash command likely modifies files.

    Write patterns take priority so that "echo hello > file.txt" is correctly
    classified as a write even though the command starts with "echo".
    """
    s = cmd.strip()
    for pat in _BASH_WRITE_RES:
        if pat.search(s):
            return True
    for pat in _BASH_CHECK_RES:
        if pat.match(s):
            return False
    return False  # Unknown → conservative: not counted as write


@dataclass
class WriteOp:
    tool: str
    file_path: Optional[str]  # None for un-traceable Bash writes
    lines_added: int = 0
    lines_deleted: int = 0


@dataclass
class TurnStats:
    uuid: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    writes: list[WriteOp] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_write_tokens
            + self.cache_read_tokens
        )


@dataclass
class FileStats:
    path: str
    lines_added: int
    lines_deleted: int
    mentioned: bool


@dataclass
class SessionReport:
    model: str
    session_id: str
    total_input_tokens: int
    total_output_tokens: int
    total_cache_write_tokens: int
    total_cache_read_tokens: int
    cost_usd: float
    burn_percentage: float
    burned_token_count: int
    write_turns: int
    burned_turns: int
    files: list[FileStats]

    @property
    def total_tokens(self) -> int:
        return (
            self.total_input_tokens
            + self.total_output_tokens
            + self.total_cache_write_tokens
            + self.total_cache_read_tokens
        )


def _extract_turns(records: list[dict]) -> list[TurnStats]:
    turns: list[TurnStats] = []
    for rec in records:
        if rec.get("type") != "assistant":
            continue
        msg = rec.get("message", {})
        usage = msg.get("usage", {})
        content = msg.get("content", [])
        model = msg.get("model") or rec.get("model") or "unknown"

        turn = TurnStats(
            uuid=rec.get("uuid", ""),
            model=model,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_write_tokens=usage.get("cache_creation_input_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
        )

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name", "")
            inp = block.get("input", {})

            if name == "Write":
                fp = inp.get("file_path") or inp.get("path") or ""
                body = inp.get("content", "")
                turn.writes.append(WriteOp(
                    tool="Write",
                    file_path=fp or None,
                    lines_added=len(body.splitlines()),
                ))

            elif name == "Edit":
                fp = inp.get("file_path") or inp.get("path") or ""
                old = inp.get("old_string", "")
                new = inp.get("new_string", "")
                turn.writes.append(WriteOp(
                    tool="Edit",
                    file_path=fp or None,
                    lines_added=len(new.splitlines()),
                    lines_deleted=len(old.splitlines()),
                ))

            elif name == "MultiEdit":
                fp = inp.get("file_path") or inp.get("path") or ""
                added = deleted = 0
                for edit in inp.get("edits", []):
                    added += len(edit.get("new_string", "").splitlines())
                    deleted += len(edit.get("old_string", "").splitlines())
                turn.writes.append(WriteOp(
                    tool="MultiEdit",
                    file_path=fp or None,
                    lines_added=added,
                    lines_deleted=deleted,
                ))

            elif name == "Bash":
                cmd = inp.get("command") or inp.get("cmd") or ""
                if _bash_is_write(cmd):
                    turn.writes.append(WriteOp(tool="Bash", file_path=None))

        turns.append(turn)
    return turns


def _extract_user_texts(records: list[dict]) -> list[str]:
    texts: list[str] = []
    for rec in records:
        if rec.get("type") != "user":
            continue
        content = rec.get("message", {}).get("content", [])
        if isinstance(content, str):
            texts.append(content)
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
    return texts


def _compute_burned(turns: list[TurnStats]) -> list[bool]:
    """Return a parallel bool list: True if the turn is burned.

    A turn is burned when it has file writes AND every one of those
    file writes is overwritten by a later turn.  Turns whose only
    writes are un-traceable Bash commands are never marked burned.
    """
    # Last turn index that wrote each file
    last_write_at: dict[str, int] = {}
    for i, turn in enumerate(turns):
        for w in turn.writes:
            if w.file_path:
                last_write_at[w.file_path] = i

    burned: list[bool] = []
    for i, turn in enumerate(turns):
        if not turn.writes:
            burned.append(False)
            continue

        file_ops = [w for w in turn.writes if w.file_path]
        bash_ops = [w for w in turn.writes if not w.file_path]

        # Un-traceable Bash writes → not counted as burned
        if bash_ops:
            burned.append(False)
            continue

        if not file_ops:
            burned.append(False)
            continue

        # Burned only if every file write is later overwritten
        all_dead = all(last_write_at.get(w.file_path) != i for w in file_ops)
        burned.append(all_dead)

    return burned


def _aggregate_files(turns: list[TurnStats], user_texts: list[str]) -> list[FileStats]:
    file_data: dict[str, dict[str, int]] = {}
    for turn in turns:
        for w in turn.writes:
            if not w.file_path:
                continue
            if w.file_path not in file_data:
                file_data[w.file_path] = {"added": 0, "deleted": 0}
            file_data[w.file_path]["added"] += w.lines_added
            file_data[w.file_path]["deleted"] += w.lines_deleted

    combined = " ".join(user_texts).lower()
    result: list[FileStats] = []
    for path, data in sorted(file_data.items()):
        name = Path(path).name.lower()
        path_lower = path.lower()
        mentioned = name in combined or path_lower in combined
        result.append(FileStats(
            path=path,
            lines_added=data["added"],
            lines_deleted=data["deleted"],
            mentioned=mentioned,
        ))
    return result


def analyze(records: list[dict]) -> SessionReport:
    """Analyze a parsed session and return a SessionReport."""
    if not records:
        return SessionReport(
            model="unknown", session_id="",
            total_input_tokens=0, total_output_tokens=0,
            total_cache_write_tokens=0, total_cache_read_tokens=0,
            cost_usd=0.0, burn_percentage=0.0, burned_token_count=0,
            write_turns=0, burned_turns=0, files=[],
        )

    turns = _extract_turns(records)
    user_texts = _extract_user_texts(records)

    model = "unknown"
    for t in turns:
        if t.model and t.model != "unknown":
            model = t.model
            break

    session_id = records[0].get("sessionId", "") if records else ""

    total_in = sum(t.input_tokens for t in turns)
    total_out = sum(t.output_tokens for t in turns)
    total_cw = sum(t.cache_write_tokens for t in turns)
    total_cr = sum(t.cache_read_tokens for t in turns)
    total_all = total_in + total_out + total_cw + total_cr

    cost = calculate_cost(model, total_in, total_out, total_cw, total_cr)

    is_burned = _compute_burned(turns)

    write_turns = sum(1 for t in turns if t.writes)
    burned_turns = sum(1 for i, t in enumerate(turns) if is_burned[i] and t.writes)
    burned_token_count = sum(
        t.total_tokens for i, t in enumerate(turns) if is_burned[i] and t.writes
    )
    burn_pct = (burned_token_count / total_all * 100) if total_all > 0 else 0.0

    files = _aggregate_files(turns, user_texts)

    return SessionReport(
        model=model,
        session_id=session_id,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        total_cache_write_tokens=total_cw,
        total_cache_read_tokens=total_cr,
        cost_usd=cost,
        burn_percentage=burn_pct,
        burned_token_count=burned_token_count,
        write_turns=write_turns,
        burned_turns=burned_turns,
        files=files,
    )
