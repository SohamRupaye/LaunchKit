"""Python Dockerfile generator — renders Jinja2 template."""

from __future__ import annotations

from pathlib import Path

from launchkit.core.config import ServiceConfig
from launchkit.utils.templates import render_template


def detect_dep_manager(service_dir: Path | None) -> str:
    """
    Detect which dependency manager a Python service uses, so the Dockerfile
    copies and installs the right file.

    Priority mirrors PythonDetector: requirements.txt (simplest, most reliable
    install) → pyproject.toml → Pipfile. Defaults to "requirements" when the
    directory is unknown, matching the historical behaviour.
    """
    if service_dir is None:
        return "requirements"
    if (service_dir / "requirements.txt").exists():
        return "requirements"
    if (service_dir / "pyproject.toml").exists():
        return "pyproject"
    if (service_dir / "Pipfile").exists():
        return "pipfile"
    return "requirements"


def generate_python_dockerfile(
    name: str,
    service: ServiceConfig,
    service_dir: Path | None = None,
) -> str:
    """Generate a multi-stage Dockerfile for a Python service."""
    return render_template(
        "docker/python.dockerfile.j2",
        name=name,
        framework=service.framework,
        port=service.port or 8000,
        service_type=service.type.value,
        command=service.command,
        dep_manager=detect_dep_manager(service_dir),
    )
