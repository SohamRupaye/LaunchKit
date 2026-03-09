"""Java Dockerfile generator — Maven and Gradle variants."""

from __future__ import annotations

from pathlib import Path

from launchkit.core.config import ServiceConfig
from launchkit.utils.templates import render_template


def generate_java_dockerfile(name: str, service: ServiceConfig) -> str:
    """Generate a Java Dockerfile, choosing Maven or Gradle template."""
    # Detect build tool from framework hint
    framework = service.framework or "maven"
    is_gradle = framework in ("gradle", "spring-boot")

    # For spring-boot, need to check if it's really gradle
    # The framework field will be "spring-boot", "maven", or "gradle"
    template = "docker/java_gradle.dockerfile.j2" if is_gradle else "docker/java_maven.dockerfile.j2"

    return render_template(
        template,
        name=name,
        port=service.port,
        framework=framework,
        has_kotlin="kts" in framework if framework else False,
    )
