"""GitHub Actions CI generator — renders Jinja2 template."""

from __future__ import annotations

from launchkit.core.config import LaunchKitConfig
from launchkit.utils.templates import render_template


def generate_github_actions(cfg: LaunchKitConfig) -> str:
    """Generate a GitHub Actions CI pipeline from LaunchKit config."""
    services = list(cfg.services.keys())
    registry = cfg.project.registry
    branches = cfg.ci.branches or ["main"]
    default_branch = branches[0] if branches else "main"

    # Layout mirrors the engine: a single service lives at the repo root ("."),
    # multiple services live under services/<name>/. The build context and the
    # `cd` in test steps must match, or the pipeline references paths that don't exist.
    monorepo = len(services) > 1
    contexts = {name: (f"services/{name}" if monorepo else ".") for name in services}

    return render_template(
        "ci/github_actions.yml.j2",
        services=services,
        service_configs=cfg.services,
        registry=registry,
        registry_host=registry.split("/")[0],
        secret=cfg.ci.registry_secret,
        affected_only=cfg.ci.affected_only,
        steps=cfg.ci.steps,
        branches=branches,
        default_branch=default_branch,
        monorepo=monorepo,
        contexts=contexts,
    )
