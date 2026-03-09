"""Rust Dockerfile generator — multi-stage with cargo-chef caching."""

from __future__ import annotations

from launchkit.core.config import ServiceConfig
from launchkit.utils.templates import render_template


def generate_rust_dockerfile(name: str, service: ServiceConfig) -> str:
    """Generate a Rust Dockerfile with cargo-chef layer caching."""
    return render_template(
        "docker/rust.dockerfile.j2",
        name=name,
        port=service.port,
        framework=service.framework,
    )
