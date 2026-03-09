"""Ruby Dockerfile generator — Rails asset pipeline + Puma support."""

from __future__ import annotations

from launchkit.core.config import ServiceConfig
from launchkit.utils.templates import render_template


def generate_ruby_dockerfile(name: str, service: ServiceConfig) -> str:
    """Generate a Ruby Dockerfile with Rails/Sinatra support."""
    return render_template(
        "docker/ruby.dockerfile.j2",
        name=name,
        port=service.port,
        framework=service.framework,
    )
