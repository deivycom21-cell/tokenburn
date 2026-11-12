"""Format SessionReport as human-readable text or JSON."""

import json
from pathlib import Path

from .analyzer import SessionReport

_COST_WARNING = (
    "This is the API rate. If you use Claude Pro/Max, your actual\n"
    "   cost per session is covered by your subscription."
)
_FUNNEL = "Measure your burn → buildwithcrow.com"


def _mask(path: str, share: bool) -> str:
    return Path(path).name if share else path


def format_text(
    report: SessionReport,
    session_path: str = "",
    share: bool = False,
    no_funnel: bool = False,
) -> str:
    lines: list[str] = []

    lines.append("TokenBurn Report")
    lines.append("=" * 48)
    if not share:
        label = session_path or report.session_id or "(unknown)"
        lines.append(f"Session: {label}")
    lines.append(f"Model:   {report.model}")
    lines.append("")

    lines.append("Tokens")
    lines.append("-" * 24)
    lines.append(f"  Input:        {report.total_input_tokens:>10,}")
    lines.append(f"  Output:       {report.total_output_tokens:>10,}")
    lines.append(f"  Cache read:   {report.total_cache_read_tokens:>10,}")
    lines.append(f"  Cache write:  {report.total_cache_write_tokens:>10,}")
    lines.append(f"  Total:        {report.total_tokens:>10,}")
    lines.append("")

    lines.append(f"API-equivalent cost: ${report.cost_usd:.4f}")
    lines.append(f"⚠  {_COST_WARNING}")
    lines.append("")

    lines.append("Burn  (writes not in final diff)")
    lines.append("-" * 48)
    if report.write_turns == 0:
        lines.append("  No write turns detected.")
    else:
        pct_turns = report.burned_turns / report.write_turns * 100
        lines.append(
            f"  Burned turns:  {report.burned_turns} / {report.write_turns}"
            f" write turns ({pct_turns:.1f}%)"
        )
        lines.append(
            f"  Burned tokens: {report.burned_token_count:,}"
            f" / {report.total_tokens:,} total ({report.burn_percentage:.1f}%)"
        )
    lines.append("")

    if report.files:
        lines.append("Files touched")
        lines.append("-" * 48)
        for f in report.files:
            tag = "" if f.mentioned else "  [not mentioned]"
            path_str = _mask(f.path, share)
            lines.append(f"  {path_str:<40} +{f.lines_added} -{f.lines_deleted}{tag}")
        lines.append("")

    if not no_funnel:
        lines.append("-" * 48)
        lines.append(_FUNNEL)

    return "\n".join(lines)


def format_json(
    report: SessionReport,
    session_path: str = "",
    share: bool = False,
) -> str:
    files = [
        {
            "path": _mask(f.path, share) if share else f.path,
            "lines_added": f.lines_added,
            "lines_deleted": f.lines_deleted,
            "mentioned": f.mentioned,
        }
        for f in report.files
    ]

    data: dict = {
        "model": report.model,
        "tokens": {
            "input": report.total_input_tokens,
            "output": report.total_output_tokens,
            "cache_read": report.total_cache_read_tokens,
            "cache_write": report.total_cache_write_tokens,
            "total": report.total_tokens,
        },
        "cost_usd": round(report.cost_usd, 6),
        "note": (
            "API-equivalent cost only. "
            "Subscription users (Pro/Max) are not charged per token."
        ),
        "burn": {
            "percentage": round(report.burn_percentage, 2),
            "burned_turns": report.burned_turns,
            "total_write_turns": report.write_turns,
            "burned_token_count": report.burned_token_count,
        },
        "files": files,
    }
    if not share:
        data["session"] = session_path or report.session_id

    return json.dumps(data, indent=2)
