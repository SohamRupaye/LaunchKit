"""Python Dockerfile generator — renders Jinja2 template."""

from __future__ import annotations

from launchkit.core.config import ServiceConfig
from launchkit.utils.templates import render_template


def generate_python_dockerfile(name: str, service: ServiceConfig) -> str:
    """Generate a multi-stage Dockerfile for a Python service."""
    return render_template(
        "docker/python.dockerfile.j2",
        name=name,
        framework=service.framework,
        port=service.port or 8000,
        service_type=service.type.value,
    )
