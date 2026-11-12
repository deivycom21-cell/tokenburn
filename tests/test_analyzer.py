"""Tests for criterion 4 (burn rule) and criterion 5 (scope / not-mentioned)."""

import pytest

from tokenburn.reader import parse_jsonl
from tokenburn.analyzer import analyze, _bash_is_write, SessionReport


# ── Criterion 4 — Burn rule ───────────────────────────────────────────────────

class TestBurnReadOnly:
    def test_no_writes_means_no_write_turns(self, session_simple):
        records = parse_jsonl(session_simple)
        report = analyze(records)
        assert report.write_turns == 0

    def test_no_writes_means_zero_burn_percentage(self, session_simple):
        records = parse_jsonl(session_simple)
        report = analyze(records)
        assert report.burn_percentage == 0.0

    def test_no_writes_means_zero_burned_turns(self, session_simple):
        records = parse_jsonl(session_simple)
        report = analyze(records)
        assert report.burned_turns == 0

    def test_read_only_session_has_tokens(self, session_simple):
        records = parse_jsonl(session_simple)
        report = analyze(records)
        assert report.total_tokens > 0


class TestBurnAllSurvive:
    def test_all_survive_means_zero_burned_turns(self, session_all_survive):
        records = parse_jsonl(session_all_survive)
        report = analyze(records)
        assert report.burned_turns == 0

    def test_all_survive_means_zero_burn_percentage(self, session_all_survive):
        records = parse_jsonl(session_all_survive)
        report = analyze(records)
        assert report.burn_percentage == 0.0

    def test_all_survive_has_two_write_turns(self, session_all_survive):
        records = parse_jsonl(session_all_survive)
        report = analyze(records)
        assert report.write_turns == 2

    def test_zero_burned_token_count(self, session_all_survive):
        records = parse_jsonl(session_all_survive)
        report = analyze(records)
        assert report.burned_token_count == 0


class TestBurnWithOverwrite:
    def test_overwritten_write_counts_as_burned_turn(self, session_burn):
        records = parse_jsonl(session_burn)
        report = analyze(records)
        # Turn 1 writes hello.py; turn 2 overwrites it → turn 1 is burned
        assert report.burned_turns == 1

    def test_three_write_turns_total(self, session_burn):
        records = parse_jsonl(session_burn)
        report = analyze(records)
        assert report.write_turns == 3

    def test_burn_percentage_is_one_third(self, session_burn):
        records = parse_jsonl(session_burn)
        report = analyze(records)
        # 1 of 3 write turns burned; each turn has equal tokens → 33.3%
        assert abs(report.burn_percentage - 100 / 3) < 0.1

    def test_burned_token_count(self, session_burn):
        records = parse_jsonl(session_burn)
        report = analyze(records)
        # Turn 1: 100 input + 50 output = 150 tokens
        assert report.burned_token_count == 150

    def test_total_tokens(self, session_burn):
        records = parse_jsonl(session_burn)
        report = analyze(records)
        # 3 turns * (100 input + 50 output) = 450
        assert report.total_tokens == 450

    def test_last_write_to_file_survives(self, session_burn):
        """The second write to hello.py is not burned."""
        records = parse_jsonl(session_burn)
        report = analyze(records)
        # 3 write turns, only 1 burned → 2 survive
        assert report.write_turns - report.burned_turns == 2


class TestBurnEdgeCases:
    def test_empty_session_returns_zero_burn(self):
        report = analyze([])
        assert report.burn_percentage == 0.0
        assert report.write_turns == 0
        assert report.burned_turns == 0

    def test_single_write_never_burned(self, tmp_path):
        """A single write with no overwrites is not burned."""
        content = (
            '{"type":"user","message":{"role":"user","content":[{"type":"text","text":"Create x.py"}]},'
            '"uuid":"u1","sessionId":"s1","cwd":"/p","version":"1.0","userType":"human","isSidechain":false,"parentUuid":null}\n'
            '{"type":"assistant","message":{"id":"m1","type":"message","role":"assistant","model":"claude-sonnet-4-6",'
            '"content":[{"type":"tool_use","id":"t1","name":"Write","input":{"file_path":"/p/x.py","content":"x=1"}}],'
            '"stop_reason":"tool_use","usage":{"input_tokens":50,"output_tokens":20,"cache_creation_input_tokens":0,'
            '"cache_read_input_tokens":0}},"uuid":"a1","sessionId":"s1","cwd":"/p","version":"1.0","userType":"ai",'
            '"isSidechain":false,"parentUuid":"u1"}\n'
        )
        p = tmp_path / "s.jsonl"
        p.write_text(content)
        from tokenburn.reader import parse_jsonl
        records = parse_jsonl(p)
        report = analyze(records)
        assert report.burned_turns == 0
        assert report.write_turns == 1
        assert report.burn_percentage == 0.0

    def test_check_only_bash_is_not_a_write_turn(self, tmp_path):
        """pytest/eslint bash commands do not count as write turns."""
        content = (
            '{"type":"assistant","message":{"id":"m1","type":"message","role":"assistant","model":"claude-sonnet-4-6",'
            '"content":[{"type":"tool_use","id":"t1","name":"Bash","input":{"command":"pytest tests/"}}],'
            '"stop_reason":"tool_use","usage":{"input_tokens":50,"output_tokens":20,"cache_creation_input_tokens":0,'
            '"cache_read_input_tokens":0}},"uuid":"a1","sessionId":"s1","cwd":"/p","version":"1.0","userType":"ai",'
            '"isSidechain":false,"parentUuid":null}\n'
        )
        p = tmp_path / "s.jsonl"
        p.write_text(content)
        from tokenburn.reader import parse_jsonl
        records = parse_jsonl(p)
        report = analyze(records)
        assert report.write_turns == 0


class TestBashClassification:
    @pytest.mark.parametrize("cmd", [
        "pytest tests/",
        "python -m pytest",
        "npm test",
        "npm run test",
        "eslint src/",
        "flake8 .",
        "mypy src/",
        "ruff check .",
        "git status",
        "git diff",
        "cat file.txt",
        "ls -la",
        "grep -r foo .",
        "echo hello",
        "python script.py",
    ])
    def test_check_command_is_not_write(self, cmd):
        assert _bash_is_write(cmd) is False

    @pytest.mark.parametrize("cmd", [
        "echo hello > file.txt",
        "cat data >> output.log",
        "rm -rf dist/",
        "mv old.py new.py",
        "cp src dst",
        "mkdir -p build/",
        "touch new_file.py",
        "sed -i 's/foo/bar/' file.txt",
        "git add .",
        "git commit -m 'fix'",
        "pip install requests",
    ])
    def test_write_command_is_write(self, cmd):
        assert _bash_is_write(cmd) is True


# ── Criterion 5 — Scope / not-mentioned heuristic ────────────────────────────

class TestScope:
    def test_files_are_listed(self, session_burn):
        records = parse_jsonl(session_burn)
        report = analyze(records)
        paths = [f.path for f in report.files]
        assert "/project/hello.py" in paths
        assert "/project/utils.py" in paths

    def test_mentioned_file_is_marked(self, session_burn):
        records = parse_jsonl(session_burn)
        report = analyze(records)
        hello = next(f for f in report.files if "hello.py" in f.path)
        assert hello.mentioned is True

    def test_not_mentioned_file_is_marked(self, session_burn):
        """utils.py is never mentioned in any user message."""
        records = parse_jsonl(session_burn)
        report = analyze(records)
        utils = next(f for f in report.files if "utils.py" in f.path)
        assert utils.mentioned is False

    def test_lines_added_counted(self, session_all_survive):
        records = parse_jsonl(session_all_survive)
        report = analyze(records)
        a_file = next(f for f in report.files if "a.py" in f.path)
        # a.py content: "x = 1\ny = 2\nprint(x + y)\n" = 3 lines
        assert a_file.lines_added == 3

    def test_all_survive_files_mentioned(self, session_all_survive):
        records = parse_jsonl(session_all_survive)
        report = analyze(records)
        for f in report.files:
            assert f.mentioned is True, f"{f.path} should be mentioned"

    def test_scope_heuristic_uses_filename(self, tmp_path):
        """Mention of just the filename (not full path) counts as mentioned."""
        content = (
            '{"type":"user","message":{"role":"user","content":[{"type":"text","text":"Edit config.py"}]},'
            '"uuid":"u1","sessionId":"s1","cwd":"/deep/project","version":"1.0","userType":"human","isSidechain":false,"parentUuid":null}\n'
            '{"type":"assistant","message":{"id":"m1","type":"message","role":"assistant","model":"claude-sonnet-4-6",'
            '"content":[{"type":"tool_use","id":"t1","name":"Write","input":{"file_path":"/deep/project/config.py","content":"x=1"}}],'
            '"stop_reason":"tool_use","usage":{"input_tokens":50,"output_tokens":20,"cache_creation_input_tokens":0,'
            '"cache_read_input_tokens":0}},"uuid":"a1","sessionId":"s1","cwd":"/deep/project","version":"1.0","userType":"ai",'
            '"isSidechain":false,"parentUuid":"u1"}\n'
        )
        p = tmp_path / "s.jsonl"
        p.write_text(content)
        from tokenburn.reader import parse_jsonl
        records = parse_jsonl(p)
        report = analyze(records)
        config = report.files[0]
        assert config.mentioned is True

    def test_no_files_in_read_only_session(self, session_simple):
        records = parse_jsonl(session_simple)
        report = analyze(records)
        assert report.files == []


# ── Criterion 3 — Token counts and cost ──────────────────────────────────────

class TestTokenCounts:
    def test_input_tokens_summed(self, session_burn):
        records = parse_jsonl(session_burn)
        report = analyze(records)
        # 3 turns * 100 input = 300
        assert report.total_input_tokens == 300

    def test_output_tokens_summed(self, session_burn):
        records = parse_jsonl(session_burn)
        report = analyze(records)
        # 3 turns * 50 output = 150
        assert report.total_output_tokens == 150

    def test_cache_tokens_zero(self, session_burn):
        records = parse_jsonl(session_burn)
        report = analyze(records)
        assert report.total_cache_read_tokens == 0
        assert report.total_cache_write_tokens == 0

    def test_cost_is_positive(self, session_burn):
        records = parse_jsonl(session_burn)
        report = analyze(records)
        assert report.cost_usd > 0

    def test_model_extracted(self, session_burn):
        records = parse_jsonl(session_burn)
        report = analyze(records)
        assert report.model == "claude-sonnet-4-6"
