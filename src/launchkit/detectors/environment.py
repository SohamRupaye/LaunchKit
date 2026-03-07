"""Environment detector — infers CI provider, branches, and project context from the repo."""

from __future__ import annotations

import subprocess
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class EnvironmentContext:
    """Everything LaunchKit can infer about the project environment."""

    ci_provider: str = "github"
    default_branch: str = "main"
    branches: list[str] = field(default_factory=lambda: ["main"])
    has_tests: bool = False
    has_docker: bool = False
    has_k8s: bool = False
    has_compose: bool = False
    registry_hint: str | None = None


# ── CI Provider Detection ────────────────────────────────────────────────────


def detect_ci_provider(root: Path) -> str:
    """
    Detect CI provider from existing project files.

    Checks for CI config files in priority order. Returns the first match,
    or "github" as a sensible default.
    """
    checks = [
        (root / ".github" / "workflows", "github"),
        (root / ".gitlab-ci.yml", "gitlab"),
        (root / "Jenkinsfile", "jenkins"),
        (root / ".circleci", "circleci"),
        (root / "bitbucket-pipelines.yml", "bitbucket"),
        (root / ".travis.yml", "travis"),
        (root / "azure-pipelines.yml", "azure"),
    ]

    for path, provider in checks:
        if path.exists():
            return provider

    return "github"  # sensible default


# ── Branch Strategy Detection ────────────────────────────────────────────────


def detect_default_branch(root: Path) -> str:
    """
    Detect the default branch from git.

    Tries (in order):
    1. git symbolic-ref for the remote HEAD
    2. git branch to find main/master
    3. Falls back to "main"
    """
    # Try remote HEAD reference
    branch = _git_remote_head(root)
    if branch:
        return branch

    # Try local branches
    branches = _git_local_branches(root)
    for candidate in ["main", "master"]:
        if candidate in branches:
            return candidate

    return "main"


def detect_branch_strategy(root: Path) -> list[str]:
    """
    Detect which branches should trigger CI.

    Examines git branches to determine the branching strategy:
    - If 'develop' exists → GitFlow: trigger on main + develop
    - If 'release/*' branches exist → release branches too
    - Otherwise → trunk-based: just the default branch
    """
    default = detect_default_branch(root)
    branches = _git_local_branches(root)
    trigger_branches = [default]

    # GitFlow detection: develop branch
    if "develop" in branches and "develop" != default:
        trigger_branches.append("develop")

    # Release branch pattern
    has_release = any(b.startswith("release/") for b in branches)
    if has_release:
        trigger_branches.append("release/*")

    return trigger_branches


# ── Project Context Detection ────────────────────────────────────────────────


def detect_environment(root: Path) -> EnvironmentContext:
    """
    Build a full environment context by scanning the project.

    This is the main entry point — it combines all detection methods
    into a single result.
    """
    ctx = EnvironmentContext()

    ctx.ci_provider = detect_ci_provider(root)
    ctx.default_branch = detect_default_branch(root)
    ctx.branches = detect_branch_strategy(root)
    ctx.has_tests = _detect_has_tests(root)
    ctx.has_docker = (root / "Dockerfile").exists() or (root / "docker-compose.yml").exists()
    ctx.has_k8s = (root / "k8s").is_dir() or (root / "kubernetes").is_dir()
    ctx.has_compose = (root / "docker-compose.yml").exists() or (root / "compose.yml").exists()
    ctx.registry_hint = _detect_registry(root)

    return ctx


def _detect_has_tests(root: Path) -> bool:
    """Check if the project has test files."""
    # Python tests
    if (root / "tests").is_dir() or (root / "test").is_dir():
        return True
    # Node tests
    pkg = root / "package.json"
    if pkg.exists():
        try:
            import json
            data = json.loads(pkg.read_text())
            scripts = data.get("scripts", {})
            if "test" in scripts and scripts["test"] != 'echo "Error: no test specified" && exit 1':
                return True
        except Exception:
            pass
    # Go tests
    for f in root.rglob("*_test.go"):
        return True
    # pytest.ini / setup.cfg with [tool:pytest]
    if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists():
        return True
    return False


def _detect_registry(root: Path) -> str | None:
    """Try to infer the container registry from existing project context."""
    # Check for GitHub origin → ghcr.io
    remote = _git_remote_url(root)
    if remote:
        if "github.com" in remote:
            # Extract org/repo from git URL
            parts = remote.replace("git@github.com:", "").replace("https://github.com/", "")
            parts = parts.replace(".git", "").strip("/")
            return f"ghcr.io/{parts}"
        elif "gitlab.com" in remote:
            parts = remote.replace("git@gitlab.com:", "").replace("https://gitlab.com/", "")
            parts = parts.replace(".git", "").strip("/")
            return f"registry.gitlab.com/{parts}"
    return None


# ── Git helpers ──────────────────────────────────────────────────────────────


def _git_remote_head(root: Path) -> str | None:
    """Get the default branch from the remote HEAD."""
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True, text=True, timeout=5, cwd=root,
        )
        if result.returncode == 0:
            # "refs/remotes/origin/main" → "main"
            return result.stdout.strip().split("/")[-1]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _git_local_branches(root: Path) -> list[str]:
    """List all local git branches."""
    try:
        result = subprocess.run(
            ["git", "branch", "--format=%(refname:short)"],
            capture_output=True, text=True, timeout=5, cwd=root,
        )
        if result.returncode == 0:
            return [b.strip() for b in result.stdout.strip().split("\n") if b.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return []


def _git_remote_url(root: Path) -> str | None:
    """Get the remote origin URL."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5, cwd=root,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None
