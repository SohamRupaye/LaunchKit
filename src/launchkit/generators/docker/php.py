"""PHP Dockerfile generator — nginx + php-fpm with Laravel/Symfony support."""

from __future__ import annotations

from launchkit.core.config import ServiceConfig
from launchkit.utils.templates import render_template


def generate_php_dockerfile(name: str, service: ServiceConfig) -> str:
    """Generate a PHP Dockerfile with php-fpm and framework-specific optimizations."""
    return render_template(
        "docker/php.dockerfile.j2",
        name=name,
        port=service.port,
        framework=service.framework,
    )
