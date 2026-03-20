"""Tests for Docker generators."""

from __future__ import annotations

import pytest

from launchkit.core.config import ServiceConfig, Lang, ServiceType
from launchkit.generators.docker.python import generate_python_dockerfile
from launchkit.generators.docker.node import generate_node_dockerfile
from launchkit.generators.docker.go import generate_go_dockerfile


class TestPythonDockerfile:
    def test_fastapi(self) -> None:
        svc = ServiceConfig(lang=Lang.PYTHON, framework="fastapi", port=8000)
        result = generate_python_dockerfile("api", svc)
        assert "FROM python:3.12-slim" in result
        assert "uvicorn" in result
        assert "EXPOSE 8000" in result
        assert "appuser" in result

    def test_flask(self) -> None:
        svc = ServiceConfig(lang=Lang.PYTHON, framework="flask", port=5000)
        result = generate_python_dockerfile("web", svc)
        assert "gunicorn" in result
        assert "EXPOSE 5000" in result

    def test_django(self) -> None:
        svc = ServiceConfig(lang=Lang.PYTHON, framework="django", port=8000)
        result = generate_python_dockerfile("web", svc)
        assert "gunicorn" in result
        assert "config.wsgi" in result

    def test_worker(self) -> None:
        svc = ServiceConfig(lang=Lang.PYTHON, type=ServiceType.WORKER)
        result = generate_python_dockerfile("bg", svc)
        assert "worker.py" in result
        assert "EXPOSE" not in result or "EXPOSE 8000" in result

    def test_generic(self) -> None:
        svc = ServiceConfig(lang=Lang.PYTHON, port=9000)
        result = generate_python_dockerfile("svc", svc)
        assert "main.py" in result
        assert "EXPOSE 9000" in result


class TestNodeDockerfile:
    def test_nextjs(self) -> None:
        svc = ServiceConfig(lang=Lang.NODE, framework="nextjs", port=3000)
        result = generate_node_dockerfile("frontend", svc)
        assert "node:20-alpine" in result
        assert "standalone" in result
        assert "EXPOSE 3000" in result

    def test_express(self) -> None:
        svc = ServiceConfig(lang=Lang.NODE, framework="express", port=4000)
        result = generate_node_dockerfile("api", svc)
        assert "node:20-alpine" in result
        assert "EXPOSE 4000" in result
        assert "index.js" in result


class TestGoDockerfile:
    def test_go_service(self) -> None:
        svc = ServiceConfig(lang=Lang.GO, port=8080)
        result = generate_go_dockerfile("server", svc)
        assert "golang:1.22-alpine" in result
        assert "FROM scratch" in result
        assert "CGO_ENABLED=0" in result
        assert "EXPOSE 8080" in result
        assert "ca-certificates" in result
