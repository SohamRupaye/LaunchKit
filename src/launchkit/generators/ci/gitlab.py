"""GitLab CI generator — renders Jinja2 template."""

from __future__ import annotations

from launchkit.core.config import LaunchKitConfig
from launchkit.utils.templates import render_template


def generate_gitlab_ci(cfg: LaunchKitConfig) -> str:
    """Generate a .gitlab-ci.yml pipeline from LaunchKit config."""
    services = list(cfg.services.keys())
    registry = cfg.project.registry
    branches = cfg.ci.branches or ["main"]

    return render_template(
        "ci/gitlab_ci.yml.j2",
        services=services,
        service_configs=cfg.services,
        registry=registry,
        secret=cfg.ci.registry_secret,
        affected_only=cfg.ci.affected_only,
        steps=cfg.ci.steps,
        branches=branches,
    )
