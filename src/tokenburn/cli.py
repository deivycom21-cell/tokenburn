"""TokenBurn CLI entry point."""

import sys
from pathlib import Path

import click

from .reader import ParseError, find_sessions, parse_jsonl
from .analyzer import analyze
from .reporter import format_json, format_text

_DISCLAIMER = "Not affiliated with, endorsed by, or sponsored by Anthropic. Claude® is a trademark of Anthropic."


@click.group()
@click.version_option()
def main() -> None:
    """TokenBurn — measure wasted tokens in Claude Code sessions.

    \b
    Not affiliated with Anthropic. Claude® is a trademark of Anthropic.
    API-equivalent cost shown; subscription (Pro/Max) costs differ.
    """


@main.command()
@click.argument("session_file", type=click.Path(path_type=Path), required=False)
@click.option(
    "--projects-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to ~/.claude/projects (default: auto-detect).",
)
@click.option("--json", "output_json", is_flag=True, help="Output JSON.")
@click.option("--share", is_flag=True, help="Hide paths and project name for sharing.")
@click.option(
    "--no-funnel",
    is_flag=True,
    envvar="TOKENBURN_NO_FUNNEL",
    help="Suppress the footer line.",
)
def analyze(
    session_file: Path | None,
    projects_dir: Path | None,
    output_json: bool,
    share: bool,
    no_funnel: bool,
) -> None:
    """Analyze a Claude Code session for token burn."""
    if session_file is None:
        sessions = find_sessions(projects_dir)
        if not sessions:
            click.echo(
                "No Claude Code sessions found. Pass a session file path.", err=True
            )
            sys.exit(1)
        session_file = sessions[-1]
        click.echo(f"Analyzing most recent session: {session_file}", err=True)
    else:
        if not session_file.exists():
            click.echo(f"Session file not found: {session_file}", err=True)
            sys.exit(1)

    try:
        records = parse_jsonl(session_file)
    except ParseError as exc:
        click.echo(str(exc), err=True)
        sys.exit(1)

    report = analyze(records)

    if output_json:
        click.echo(format_json(report, str(session_file), share=share))
    else:
        click.echo(
            format_text(report, str(session_file), share=share, no_funnel=no_funnel)
        )


@main.command(name="list")
@click.option(
    "--projects-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to ~/.claude/projects.",
)
def list_cmd(projects_dir: Path | None) -> None:
    """List available Claude Code sessions."""
    sessions = find_sessions(projects_dir)
    if not sessions:
        click.echo("No sessions found.")
        return
    for s in sessions:
        click.echo(str(s))
