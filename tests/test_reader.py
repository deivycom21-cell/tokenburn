"""Tests for criterion 1 (source/scope) and criterion 7 (robustness)."""

from pathlib import Path

import pytest

from tokenburn.reader import ParseError, find_sessions, parse_jsonl


# ── Criterion 1 ──────────────────────────────────────────────────────────────

class TestParseValidSession:
    def test_returns_list_of_dicts(self, session_simple):
        records = parse_jsonl(session_simple)
        assert isinstance(records, list)
        assert all(isinstance(r, dict) for r in records)

    def test_correct_record_count(self, session_simple):
        records = parse_jsonl(session_simple)
        # 2 user + 2 assistant messages in session_simple
        assert len(records) == 4

    def test_has_expected_types(self, session_simple):
        records = parse_jsonl(session_simple)
        types = {r["type"] for r in records}
        assert "user" in types
        assert "assistant" in types

    def test_assistant_has_usage(self, session_simple):
        records = parse_jsonl(session_simple)
        assistants = [r for r in records if r["type"] == "assistant"]
        for a in assistants:
            usage = a["message"]["usage"]
            assert "input_tokens" in usage
            assert "output_tokens" in usage

    def test_session_id_present(self, session_simple):
        records = parse_jsonl(session_simple)
        assert records[0]["sessionId"] == "sess_simple"

    def test_burn_fixture_has_three_assistant_turns(self, session_burn):
        records = parse_jsonl(session_burn)
        assistants = [r for r in records if r["type"] == "assistant"]
        assert len(assistants) == 3


class TestFindSessions:
    def test_returns_list(self, tmp_path):
        result = find_sessions(tmp_path)
        assert isinstance(result, list)

    def test_empty_dir_returns_empty(self, tmp_path):
        assert find_sessions(tmp_path) == []

    def test_nonexistent_dir_returns_empty(self):
        assert find_sessions(Path("/nonexistent/path")) == []

    def test_finds_jsonl_files(self, tmp_path):
        (tmp_path / "proj1").mkdir()
        (tmp_path / "proj1" / "sess1.jsonl").write_text("{}")
        (tmp_path / "proj1" / "sess2.jsonl").write_text("{}")
        result = find_sessions(tmp_path)
        assert len(result) == 2

    def test_ignores_non_jsonl(self, tmp_path):
        (tmp_path / "file.txt").write_text("hello")
        (tmp_path / "file.json").write_text("{}")
        (tmp_path / "sess.jsonl").write_text("{}")
        result = find_sessions(tmp_path)
        assert len(result) == 1

    def test_results_are_sorted(self, tmp_path):
        for name in ("c.jsonl", "a.jsonl", "b.jsonl"):
            (tmp_path / name).write_text("{}")
        result = find_sessions(tmp_path)
        names = [p.name for p in result]
        assert names == sorted(names)


# ── Criterion 7 (robustness) ─────────────────────────────────────────────────

class TestRobustness:
    def test_empty_file_returns_empty_list(self, session_empty):
        records = parse_jsonl(session_empty)
        assert records == []

    def test_malformed_raises_parse_error(self, session_malformed):
        with pytest.raises(ParseError) as exc_info:
            parse_jsonl(session_malformed)
        assert "Malformed JSONL" in str(exc_info.value)
        assert "TokenBurn cannot analyze" in str(exc_info.value)

    def test_parse_error_includes_line_number(self, session_malformed):
        with pytest.raises(ParseError) as exc_info:
            parse_jsonl(session_malformed)
        # Should mention line 2 (the bad line)
        assert "line 2" in str(exc_info.value)

    def test_no_partial_numbers_on_error(self, session_malformed):
        """On parse error we raise immediately; no partial results returned."""
        with pytest.raises(ParseError):
            parse_jsonl(session_malformed)
        # The fact that an exception is raised (not a partial list) satisfies
        # the "never show partial numbers" requirement.

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_jsonl(tmp_path / "nonexistent.jsonl")

    def test_file_not_found_message_is_clear(self, tmp_path):
        try:
            parse_jsonl(tmp_path / "ghost.jsonl")
        except FileNotFoundError as e:
            assert "ghost.jsonl" in str(e)

    def test_single_valid_line(self, tmp_path):
        p = tmp_path / "s.jsonl"
        p.write_text('{"type":"user","message":{}}\n')
        records = parse_jsonl(p)
        assert len(records) == 1

    def test_blank_lines_are_skipped(self, tmp_path):
        p = tmp_path / "s.jsonl"
        p.write_text('\n{"type":"user","message":{}}\n\n{"type":"user","message":{}}\n')
        records = parse_jsonl(p)
        assert len(records) == 2

    def test_unknown_fields_are_accepted(self, tmp_path):
        """Unknown fields are tolerated — format extensions don't break parsing."""
        p = tmp_path / "s.jsonl"
        p.write_text('{"type":"future_type","new_field":42,"other":{"nested":true}}\n')
        records = parse_jsonl(p)
        assert records[0]["new_field"] == 42
