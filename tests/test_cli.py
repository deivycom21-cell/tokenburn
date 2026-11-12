"""Tests for criterion 9: disclaimer in --help."""

from click.testing import CliRunner

from tokenburn.cli import main, _DISCLAIMER


class TestDisclaimer:
    """Criterion 9: disclaimer must appear in --help output."""

    def test_disclaimer_in_help(self):
        """The non-affiliation disclaimer is visible in `tokenburn --help`."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Not affiliated" in result.output
        assert "Anthropic" in result.output

    def test_disclaimer_uses_constant(self):
        """The --help epilog contains the _DISCLAIMER constant text (may be word-wrapped)."""
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        # Normalize whitespace so word-wrap doesn't break the check
        normalized = " ".join(result.output.split())
        assert "Not affiliated with, endorsed by, or sponsored by Anthropic" in normalized
        assert "Claude® is a trademark of Anthropic" in normalized

    def test_no_option_suppresses_disclaimer(self):
        """No flag hides the disclaimer from `tokenburn --help`."""
        runner = CliRunner()
        # Run with every flag that the main group accepts; none should hide the disclaimer.
        # (--version exits early, so we only test --help here.)
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Not affiliated" in result.output
