"""Tests for criterion 3 (cost label / token counts), criterion 6 (share mode), and criterion 8 (funnel)."""

import json

import pytest
from click.testing import CliRunner

from tokenburn.reader import parse_jsonl
from tokenburn.analyzer import analyze
from tokenburn.reporter import format_text, format_json
from tokenburn.cli import main

_FUNNEL_URL = "buildwithcrow.com"


def _report(fixture_path):
    return analyze(parse_jsonl(fixture_path))


# ── Criterion 3 — Cost label and token counts ─────────────────────────────────

class TestCostLabel:
    def test_text_contains_api_equivalent_cost(self, session_burn):
        out = format_text(_report(session_burn))
        assert "API-equivalent cost" in out

    def test_text_contains_subscription_warning(self, session_burn):
        out = format_text(_report(session_burn))
        # Must warn that this is NOT what a Pro/Max subscriber pays
        assert "Pro" in out or "subscription" in out.lower()

    def test_text_contains_input_tokens(self, session_burn):
        out = format_text(_report(session_burn))
        assert "Input:" in out

    def test_text_contains_output_tokens(self, session_burn):
        out = format_text(_report(session_burn))
        assert "Output:" in out

    def test_text_contains_cache_read_tokens(self, session_burn):
        out = format_text(_report(session_burn))
        assert "Cache read:" in out

    def test_text_contains_cache_write_tokens(self, session_burn):
        out = format_text(_report(session_burn))
        assert "Cache write:" in out

    def test_text_contains_dollar_sign(self, session_burn):
        out = format_text(_report(session_burn))
        assert "$" in out

    def test_json_has_cost_usd_field(self, session_burn):
        data = json.loads(format_json(_report(session_burn)))
        assert "cost_usd" in data
        assert isinstance(data["cost_usd"], float)

    def test_json_has_note_about_subscription(self, session_burn):
        data = json.loads(format_json(_report(session_burn)))
        assert "note" in data
        note_lower = data["note"].lower()
        assert "subscription" in note_lower or "pro" in note_lower or "max" in note_lower

    def test_json_has_tokens_block(self, session_burn):
        data = json.loads(format_json(_report(session_burn)))
        assert "tokens" in data
        for key in ("input", "output", "cache_read", "cache_write", "total"):
            assert key in data["tokens"]

    def test_json_tokens_match_report(self, session_burn):
        report = _report(session_burn)
        data = json.loads(format_json(report))
        assert data["tokens"]["input"] == report.total_input_tokens
        assert data["tokens"]["output"] == report.total_output_tokens


# ── Criterion 6 — Share mode ──────────────────────────────────────────────────

class TestShareMode:
    def test_share_mode_hides_full_path_in_files(self, session_burn):
        out = format_text(_report(session_burn), session_path="/home/user/.claude/projects/abc/sess.jsonl", share=True)
        # Full paths like /project/hello.py must not appear
        assert "/project/hello.py" not in out
        # Only the filename should appear
        assert "hello.py" in out

    def test_share_mode_hides_session_path(self, session_burn):
        out = format_text(
            _report(session_burn),
            session_path="/home/user/.claude/projects/abc/sess.jsonl",
            share=True,
        )
        assert "/home/user/.claude" not in out

    def test_share_mode_no_session_line(self, session_burn):
        out = format_text(
            _report(session_burn),
            session_path="/home/user/.claude/projects/abc/sess.jsonl",
            share=True,
        )
        assert "Session:" not in out

    def test_no_share_includes_session_path(self, session_burn):
        out = format_text(
            _report(session_burn),
            session_path="/home/user/.claude/projects/abc/sess.jsonl",
            share=False,
        )
        assert "Session:" in out
        assert "/home/user/.claude/projects/abc/sess.jsonl" in out

    def test_share_mode_json_hides_path(self, session_burn):
        data = json.loads(
            format_json(_report(session_burn), session_path="/home/user/.claude/projects/abc/sess.jsonl", share=True)
        )
        # No session key in JSON when sharing
        assert "session" not in data

    def test_share_mode_json_file_path_is_basename_only(self, session_burn):
        data = json.loads(format_json(_report(session_burn), share=True))
        for f in data["files"]:
            assert "/" not in f["path"], f"Full path leaked: {f['path']}"

    def test_no_share_json_keeps_full_path(self, session_burn):
        data = json.loads(format_json(_report(session_burn), share=False))
        paths = [f["path"] for f in data["files"]]
        assert any("/" in p for p in paths)


# ── Funnel line (criterion 8) ─────────────────────────────────────────────────

class TestFunnelLine:
    def test_funnel_present_by_default(self, session_burn):
        out = format_text(_report(session_burn))
        assert _FUNNEL_URL in out

    def test_no_funnel_flag_removes_it(self, session_burn):
        out = format_text(_report(session_burn), no_funnel=True)
        assert _FUNNEL_URL not in out

    def test_no_funnel_env_var_removes_it(self, session_burn):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["analyze", str(session_burn)],
            env={"TOKENBURN_NO_FUNNEL": "1"},
        )
        assert result.exit_code == 0, result.output
        assert _FUNNEL_URL not in result.output

    def test_no_funnel_in_json_output(self, session_burn):
        data = json.loads(format_json(_report(session_burn)))
        assert _FUNNEL_URL not in json.dumps(data)


# ── Burn section in report ────────────────────────────────────────────────────

class TestBurnSection:
    def test_text_has_burn_section(self, session_burn):
        out = format_text(_report(session_burn))
        assert "Burn" in out

    def test_text_shows_burned_turns(self, session_burn):
        out = format_text(_report(session_burn))
        assert "Burned turns:" in out

    def test_text_shows_burn_percentage(self, session_burn):
        out = format_text(_report(session_burn))
        assert "%" in out

    def test_no_write_turns_message(self, session_simple):
        out = format_text(_report(session_simple))
        assert "No write turns" in out

    def test_json_has_burn_block(self, session_burn):
        data = json.loads(format_json(_report(session_burn)))
        assert "burn" in data
        assert "percentage" in data["burn"]
        assert "burned_turns" in data["burn"]


# ── Not-mentioned annotation ──────────────────────────────────────────────────

class TestNotMentionedAnnotation:
    def test_not_mentioned_appears_in_text(self, session_burn):
        out = format_text(_report(session_burn))
        assert "not mentioned" in out

    def test_mentioned_file_has_no_annotation(self, session_burn):
        out = format_text(_report(session_burn))
        # hello.py is mentioned; check the line doesn't have [not mentioned]
        lines = out.splitlines()
        hello_lines = [l for l in lines if "hello.py" in l]
        assert hello_lines, "hello.py not found in output"
        for line in hello_lines:
            assert "not mentioned" not in line

    def test_not_mentioned_in_json_files(self, session_burn):
        data = json.loads(format_json(_report(session_burn)))
        utils = next((f for f in data["files"] if "utils" in f["path"]), None)
        assert utils is not None
        assert utils["mentioned"] is False


# ── Criterion 6 — Share mode with atypical paths ─────────────────────────────

class TestShareModeAtypicalPaths:
    """Verify --share only shows the filename regardless of the session path shape."""

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _text(report, session_path: str) -> str:
        return format_text(report, session_path=session_path, share=True)

    @staticmethod
    def _json(report, session_path: str) -> dict:
        return json.loads(format_json(report, session_path=session_path, share=True))

    # ── path with spaces in directory name ───────────────────────────────────

    def test_text_spaces_in_dir_no_full_path(self, session_burn):
        path = "/home/user/my project folder/sess.jsonl"
        out = self._text(_report(session_burn), path)
        assert "/home/user/my project folder" not in out

    def test_text_spaces_in_dir_no_session_line(self, session_burn):
        path = "/home/user/my project folder/sess.jsonl"
        out = self._text(_report(session_burn), path)
        assert "Session:" not in out

    def test_json_spaces_in_dir_no_session_key(self, session_burn):
        path = "/home/user/my project folder/sess.jsonl"
        data = self._json(_report(session_burn), path)
        assert "session" not in data

    def test_json_spaces_in_dir_files_basename_only(self, session_burn):
        path = "/home/user/my project folder/sess.jsonl"
        data = self._json(_report(session_burn), path)
        for f in data["files"]:
            assert "/" not in f["path"], f"Full path leaked: {f['path']}"

    # ── path with accented / Unicode characters ───────────────────────────────

    def test_text_accented_dir_no_full_path(self, session_burn):
        path = "/home/user/café résumé/sess.jsonl"
        out = self._text(_report(session_burn), path)
        assert "/home/user/café résumé" not in out

    def test_text_accented_dir_no_session_line(self, session_burn):
        path = "/home/user/café résumé/sess.jsonl"
        out = self._text(_report(session_burn), path)
        assert "Session:" not in out

    def test_json_accented_dir_no_session_key(self, session_burn):
        path = "/home/user/café résumé/sess.jsonl"
        data = self._json(_report(session_burn), path)
        assert "session" not in data

    def test_json_accented_dir_files_basename_only(self, session_burn):
        path = "/home/user/café résumé/sess.jsonl"
        data = self._json(_report(session_burn), path)
        for f in data["files"]:
            assert "/" not in f["path"], f"Full path leaked: {f['path']}"

    # ── path with special shell characters ───────────────────────────────────

    def test_text_special_chars_dir_no_full_path(self, session_burn):
        path = "/home/user/project(2024)!final/sess.jsonl"
        out = self._text(_report(session_burn), path)
        assert "/home/user/project(2024)!final" not in out

    def test_text_special_chars_dir_no_session_line(self, session_burn):
        path = "/home/user/project(2024)!final/sess.jsonl"
        out = self._text(_report(session_burn), path)
        assert "Session:" not in out

    def test_json_special_chars_dir_no_session_key(self, session_burn):
        path = "/home/user/project(2024)!final/sess.jsonl"
        data = self._json(_report(session_burn), path)
        assert "session" not in data

    def test_json_special_chars_dir_files_basename_only(self, session_burn):
        path = "/home/user/project(2024)!final/sess.jsonl"
        data = self._json(_report(session_burn), path)
        for f in data["files"]:
            assert "/" not in f["path"], f"Full path leaked: {f['path']}"

    # ── very long path (> 200 chars in directory component) ──────────────────

    def test_text_very_long_path_no_full_path(self, session_burn):
        long_dir = "d" * 200
        path = f"/home/user/{long_dir}/sess.jsonl"
        out = self._text(_report(session_burn), path)
        assert f"/home/user/{long_dir}" not in out

    def test_text_very_long_path_no_session_line(self, session_burn):
        long_dir = "d" * 200
        path = f"/home/user/{long_dir}/sess.jsonl"
        out = self._text(_report(session_burn), path)
        assert "Session:" not in out

    def test_json_very_long_path_no_session_key(self, session_burn):
        long_dir = "d" * 200
        path = f"/home/user/{long_dir}/sess.jsonl"
        data = self._json(_report(session_burn), path)
        assert "session" not in data

    def test_json_very_long_path_files_basename_only(self, session_burn):
        long_dir = "d" * 200
        path = f"/home/user/{long_dir}/sess.jsonl"
        data = self._json(_report(session_burn), path)
        for f in data["files"]:
            assert "/" not in f["path"], f"Full path leaked: {f['path']}"

    # ── filename itself contains spaces ──────────────────────────────────────

    def test_text_filename_with_spaces_no_full_path(self, session_burn):
        path = "/home/user/projects/my session 2024.jsonl"
        out = self._text(_report(session_burn), path)
        assert "/home/user/projects/" not in out

    def test_text_filename_with_spaces_no_session_line(self, session_burn):
        path = "/home/user/projects/my session 2024.jsonl"
        out = self._text(_report(session_burn), path)
        assert "Session:" not in out

    def test_json_filename_with_spaces_no_session_key(self, session_burn):
        path = "/home/user/projects/my session 2024.jsonl"
        data = self._json(_report(session_burn), path)
        assert "session" not in data
