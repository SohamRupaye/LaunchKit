"""Tests for doctor command."""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from launchkit.core.doctor import run_doctor, _get_version, _get_version_args


@pytest.fixture
def quiet_console() -> Console:
    return Console(quiet=True)


@pytest.fixture
def captured_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    return console, buf


class TestRunDoctor:
    def test_runs_without_error(self, quiet_console: Console) -> None:
        """Doctor should not crash regardless of what tools are installed."""
        run_doctor(quiet_console)

    def test_shows_tool_table(self, captured_console: tuple) -> None:
        console, buf = captured_console
        run_doctor(console)
        output = buf.getvalue()
        assert "Docker" in output
        assert "kubectl" in output
        assert "Python" in output
        assert "Git" in output


class TestGetVersion:
    def test_known_command(self) -> None:
        """python3 --version should always work."""
        version = _get_version("python3")
        assert "Python" in version or "python" in version.lower() or version == "installed"

    def test_unknown_command(self) -> None:
        version = _get_version("nonexistent_binary_xyz")
        assert version == "installed"


class TestGetVersionArgs:
    def test_custom_args(self) -> None:
        result = _get_version_args(["python3", "--version"])
        assert len(result) > 0

    def test_bad_command(self) -> None:
        result = _get_version_args(["nonexistent_cmd_xyz", "--version"])
        assert result == "installed"
