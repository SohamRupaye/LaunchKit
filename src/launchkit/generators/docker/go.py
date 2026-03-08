"""Go Dockerfile generator — renders Jinja2 template."""

from __future__ import annotations

from launchkit.core.config import ServiceConfig
from launchkit.utils.templates import render_template


def generate_go_dockerfile(name: str, service: ServiceConfig) -> str:
    """Generate a multi-stage Dockerfile for a Go service."""
    return render_template(
        "docker/go.dockerfile.j2",
        name=name,
        port=service.port or 8080,
    )
