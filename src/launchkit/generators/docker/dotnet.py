""".NET Dockerfile generator — SDK/runtime multi-stage with ASP.NET support."""

from __future__ import annotations

from launchkit.core.config import ServiceConfig
from launchkit.utils.templates import render_template


def generate_dotnet_dockerfile(name: str, service: ServiceConfig) -> str:
    """Generate a .NET Dockerfile with SDK build and Alpine runtime."""
    return render_template(
        "docker/dotnet.dockerfile.j2",
        name=name,
        port=service.port,
        framework=service.framework,
    )
