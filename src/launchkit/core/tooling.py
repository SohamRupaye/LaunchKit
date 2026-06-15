"""Tool-presence registry — shared by `doctor`, `verify`, and `measure`.

Everything that needs to know "is docker/kubectl/hadolint available?" goes through
here, so graceful degradation is consistent: a missing tool downgrades a check to a
skip with an actionable hint, it never crashes.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    """A CLI tool LaunchKit can make use of."""

    cmd: str
    display_name: str
    purpose: str
    required: bool = False
    version_args: list[str] | None = None


# Tools used for generation/deployment (surfaced by `doctor`).
CORE_TOOLS: list[Tool] = [
    Tool("docker", "Docker", "Required for building container images"),
    Tool("docker-compose", "Docker Compose",
         "Required for docker-compose output (or use `docker compose`)"),
    Tool("kubectl", "kubectl", "Required for Kubernetes deployments",
         version_args=["kubectl", "version", "--client", "--short"]),
    Tool("python3", "Python 3", "Used by LaunchKit itself"),
    Tool("node", "Node.js", "Needed for Node.js service builds",
         version_args=["node", "--version"]),
    Tool("go", "Go", "Needed for Go service builds", version_args=["go", "version"]),
    Tool("git", "Git", "Used for version detection and CI"),
]

# Tools that unlock deeper `launchkit verify` checks. All optional — verify
# degrades to a skip (or a weaker fallback) when they're absent.
VERIFY_TOOLS: list[Tool] = [
    Tool("hadolint", "hadolint", "Lints generated Dockerfiles (`launchkit verify`)"),
    Tool("kubeconform", "kubeconform", "Validates K8s manifests offline (`launchkit verify`)"),
    Tool("actionlint", "actionlint", "Lints generated GitHub Actions (`launchkit verify`)"),
]


def find_tool(cmd: str) -> str | None:
    """Return the resolved path to a tool, or None if it isn't installed."""
    return shutil.which(cmd)


def has_tool(cmd: str) -> bool:
    """True when the tool is on PATH."""
    return shutil.which(cmd) is not None


def docker_compose_cmd() -> list[str] | None:
    """
    Resolve the docker-compose invocation, preferring the standalone binary and
    falling back to the `docker compose` subcommand. Returns None if neither exists.
    """
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    if shutil.which("docker"):
        # Confirm the compose subcommand actually exists.
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return ["docker", "compose"]
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
    return None


def tool_version(cmd: str, version_args: list[str] | None = None) -> str:
    """Best-effort version string (first line, truncated). Never raises."""
    args = version_args or [cmd, "--version"]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=5)
        output = result.stdout.strip() or result.stderr.strip()
        first_line = output.split("\n")[0] if output else ""
        return first_line[:80] if first_line else "installed"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "installed"
