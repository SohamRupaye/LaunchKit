"""Tests for stack detectors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from launchkit.detectors.base import (
    PythonDetector,
    NodeDetector,
    GoDetector,
    detect_services,
)


class TestPythonDetector:
    def test_detects_fastapi(self, python_fastapi_project: Path) -> None:
        d = PythonDetector()
        result = d.detect(python_fastapi_project, "api")
        assert result is not None
        assert result.lang == "python"
        assert result.framework == "fastapi"
        assert result.port == 8000

    def test_detects_flask(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("flask>=3.0\n")
        d = PythonDetector()
        result = d.detect(tmp_path, "web")
        assert result is not None
        assert result.framework == "flask"
        assert result.port == 5000

    def test_detects_django(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("django>=5.0\n")
        d = PythonDetector()
        result = d.detect(tmp_path, "web")
        assert result is not None
        assert result.framework == "django"

    def test_detects_worker(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("celery>=5.0\nredis>=5.0\n")
        d = PythonDetector()
        result = d.detect(tmp_path, "bg")
        assert result is not None
        assert result.service_type == "worker"
        assert result.port is None

    def test_no_python(self, tmp_path: Path) -> None:
        d = PythonDetector()
        result = d.detect(tmp_path, "none")
        assert result is None


class TestNodeDetector:
    def test_detects_nextjs(self, node_nextjs_project: Path) -> None:
        d = NodeDetector()
        result = d.detect(node_nextjs_project, "frontend")
        assert result is not None
        assert result.lang == "node"
        assert result.framework == "nextjs"
        assert result.port == 3000

    def test_detects_express(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"express": "^4.18.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        d = NodeDetector()
        result = d.detect(tmp_path, "api")
        assert result is not None
        assert result.framework == "express"

    def test_no_package_json(self, tmp_path: Path) -> None:
        d = NodeDetector()
        result = d.detect(tmp_path, "none")
        assert result is None

    def test_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text("not json {{{")
        d = NodeDetector()
        result = d.detect(tmp_path, "bad")
        assert result is None


class TestGoDetector:
    def test_detects_go(self, go_project: Path) -> None:
        d = GoDetector()
        result = d.detect(go_project, "server")
        assert result is not None
        assert result.lang == "go"
        assert result.port == 8080

    def test_detects_gin(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text(
            "module test\n\ngo 1.22\n\nrequire github.com/gin-gonic/gin v1.9\n"
        )
        d = GoDetector()
        result = d.detect(tmp_path, "api")
        assert result is not None
        assert result.framework == "gin"

    def test_no_go_mod(self, tmp_path: Path) -> None:
        d = GoDetector()
        result = d.detect(tmp_path, "none")
        assert result is None


class TestDetectServices:
    def test_flat_project(self, python_fastapi_project: Path) -> None:
        services = detect_services(python_fastapi_project)
        assert len(services) == 1
        assert services[0].lang == "python"

    def test_monorepo(self, monorepo_project: Path) -> None:
        services = detect_services(monorepo_project)
        assert len(services) == 2
        langs = {s.lang for s in services}
        assert "python" in langs
        assert "node" in langs

    def test_empty_project(self, tmp_path: Path) -> None:
        services = detect_services(tmp_path)
        assert len(services) == 0
