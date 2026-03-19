"""Tests for CLI output formatting."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from launchkit.utils.printer import (
    print_success,
    print_error,
    print_warning,
    print_info,
    print_generated,
    print_skipped,
    print_header,
    print_summary_table,
    print_detected_services,
)


@pytest.fixture
def captured_console() -> tuple[Console, StringIO]:
    """Console that captures output to a string buffer."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    return console, buf


class TestPrinterFunctions:
    def test_print_success(self, captured_console: tuple) -> None:
        console, buf = captured_console
        print_success(console, "it worked")
        output = buf.getvalue()
        assert "it worked" in output

    def test_print_error(self, captured_console: tuple) -> None:
        console, buf = captured_console
        print_error(console, "something failed")
        output = buf.getvalue()
        assert "something failed" in output

    def test_print_warning(self, captured_console: tuple) -> None:
        console, buf = captured_console
        print_warning(console, "watch out")
        output = buf.getvalue()
        assert "watch out" in output

    def test_print_info(self, captured_console: tuple) -> None:
        console, buf = captured_console
        print_info(console, "just info")
        output = buf.getvalue()
        assert "just info" in output

    def test_print_generated(self, captured_console: tuple) -> None:
        console, buf = captured_console
        print_generated(console, "Dockerfile")
        output = buf.getvalue()
        assert "Dockerfile" in output

    def test_print_skipped(self, captured_console: tuple) -> None:
        console, buf = captured_console
        print_skipped(console, "Dockerfile", reason="unchanged")
        output = buf.getvalue()
        assert "Dockerfile" in output
        assert "unchanged" in output

    def test_print_header(self, captured_console: tuple) -> None:
        console, buf = captured_console
        print_header(console, "Test Header")
        output = buf.getvalue()
        assert "Test Header" in output


class TestSummaryTable:
    def test_summary_table(self, captured_console: tuple) -> None:
        console, buf = captured_console
        results = [
            ("Dockerfile", "generated"),
            ("ci.yml", "skipped"),
            ("deployment.yaml", "error"),
        ]
        print_summary_table(console, results)
        output = buf.getvalue()
        assert "Dockerfile" in output
        assert "ci.yml" in output


class TestDetectedServicesTable:
    def test_services_table(self, captured_console: tuple) -> None:
        console, buf = captured_console
        services = [
            {"name": "api", "lang": "python", "framework": "fastapi", "port": "8000", "type": "web"},
            {"name": "worker", "lang": "python", "framework": "—", "port": "—", "type": "worker"},
        ]
        print_detected_services(console, services)
        output = buf.getvalue()
        assert "api" in output
        assert "python" in output
        assert "worker" in output
