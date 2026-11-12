"""Tests for criterion 2 — no network socket is ever opened during analysis."""

import socket
from unittest.mock import MagicMock, patch

from tokenburn.reader import parse_jsonl
from tokenburn.analyzer import analyze


class TestNoNetwork:
    def test_parse_does_not_open_socket(self, session_burn):
        with patch("socket.socket") as mock_sock, \
             patch("socket.create_connection") as mock_conn:
            parse_jsonl(session_burn)
            mock_sock.assert_not_called()
            mock_conn.assert_not_called()

    def test_analyze_does_not_open_socket(self, session_burn):
        records = parse_jsonl(session_burn)
        with patch("socket.socket") as mock_sock, \
             patch("socket.create_connection") as mock_conn:
            report = analyze(records)
            mock_sock.assert_not_called()
            mock_conn.assert_not_called()
        assert report.cost_usd >= 0  # Analysis completed successfully

    def test_get_price_does_not_open_socket(self):
        from tokenburn.prices import get_price
        with patch("socket.socket") as mock_sock:
            get_price("claude-sonnet-4-6")
            mock_sock.assert_not_called()

    def test_calculate_cost_does_not_open_socket(self):
        from tokenburn.prices import calculate_cost
        with patch("socket.socket") as mock_sock:
            calculate_cost("claude-sonnet-4-6", 1000, 500)
            mock_sock.assert_not_called()

    def test_full_pipeline_survives_blocked_network(self, session_burn):
        """Analysis completes even when all sockets raise OSError."""
        with patch("socket.socket", side_effect=OSError("network blocked")), \
             patch("socket.create_connection", side_effect=OSError("network blocked")):
            records = parse_jsonl(session_burn)
            report = analyze(records)
        # Pipeline completed: cost and burn calculated from bundled data only.
        assert report.cost_usd > 0
        assert report.total_tokens > 0

    def test_reporter_does_not_open_socket(self, session_burn):
        from tokenburn.reporter import format_text, format_json
        records = parse_jsonl(session_burn)
        report = analyze(records)
        with patch("socket.socket") as mock_sock:
            format_text(report)
            format_json(report)
            mock_sock.assert_not_called()
