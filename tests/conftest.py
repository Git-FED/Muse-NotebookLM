"""Shared pytest fixtures for the muse-nlm test suite."""

import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> pathlib.Path:
    return FIXTURES


@pytest.fixture
def read_fixture():
    """Return a callable that reads a fixture file by name as text."""

    def _read(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")

    return _read
