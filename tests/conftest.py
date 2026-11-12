"""Shared fixtures for the test suite."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def session_simple() -> Path:
    return FIXTURES / "session_simple.jsonl"


@pytest.fixture
def session_all_survive() -> Path:
    return FIXTURES / "session_all_survive.jsonl"


@pytest.fixture
def session_burn() -> Path:
    return FIXTURES / "session_burn.jsonl"


@pytest.fixture
def session_malformed() -> Path:
    return FIXTURES / "session_malformed.jsonl"


@pytest.fixture
def session_empty() -> Path:
    return FIXTURES / "session_empty.jsonl"
