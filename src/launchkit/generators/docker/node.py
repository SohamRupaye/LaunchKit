"""Node.js Dockerfile generator — renders Jinja2 templates."""

from __future__ import annotations

from launchkit.core.config import ServiceConfig
from launchkit.utils.templates import render_template


def generate_node_dockerfile(name: str, service: ServiceConfig) -> str:
    """Generate a multi-stage Dockerfile for a Node.js service."""
    framework = service.framework
    port = service.port or 3000

    if framework == "nextjs":
        template = "docker/node_nextjs.dockerfile.j2"
    else:
        template = "docker/node.dockerfile.j2"

    return render_template(
        template, name=name, framework=framework, port=port, command=service.command
    )
