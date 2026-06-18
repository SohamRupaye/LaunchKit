"""GitLab CI generator — renders Jinja2 template."""

from __future__ import annotations

from launchkit.core.config import LaunchKitConfig
from launchkit.utils.templates import render_template


def generate_gitlab_ci(cfg: LaunchKitConfig) -> str:
    """Generate a .gitlab-ci.yml pipeline from LaunchKit config."""
    services = list(cfg.services.keys())
    registry = cfg.project.registry
    branches = cfg.ci.branches or ["main"]

    # Layout mirrors the engine: a single service lives at the repo root ("."),
    # multiple services live under services/<name>/.
    monorepo = len(services) > 1
    contexts = {name: (f"services/{name}" if monorepo else ".") for name in services}

    return render_template(
        "ci/gitlab_ci.yml.j2",
        services=services,
        service_configs=cfg.services,
        registry=registry,
        secret=cfg.ci.registry_secret,
        affected_only=cfg.ci.affected_only,
        steps=cfg.ci.steps,
        branches=branches,
        monorepo=monorepo,
        contexts=contexts,
    )
