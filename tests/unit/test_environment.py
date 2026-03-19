"""Tests for environment detector — CI provider, branches, project context."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from launchkit.detectors.environment import (
    EnvironmentContext,
    detect_ci_provider,
    detect_default_branch,
    detect_branch_strategy,
    detect_environment,
    _detect_has_tests,
    _detect_registry,
)


class TestDetectCIProvider:
    def test_detects_github_workflows(self, tmp_path: Path) -> None:
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        assert detect_ci_provider(tmp_path) == "github"

    def test_detects_gitlab_ci(self, tmp_path: Path) -> None:
        (tmp_path / ".gitlab-ci.yml").touch()
        assert detect_ci_provider(tmp_path) == "gitlab"

    def test_detects_jenkinsfile(self, tmp_path: Path) -> None:
        (tmp_path / "Jenkinsfile").touch()
        assert detect_ci_provider(tmp_path) == "jenkins"

    def test_detects_circleci(self, tmp_path: Path) -> None:
        (tmp_path / ".circleci").mkdir()
        assert detect_ci_provider(tmp_path) == "circleci"

    def test_detects_bitbucket(self, tmp_path: Path) -> None:
        (tmp_path / "bitbucket-pipelines.yml").touch()
        assert detect_ci_provider(tmp_path) == "bitbucket"

    def test_detects_travis(self, tmp_path: Path) -> None:
        (tmp_path / ".travis.yml").touch()
        assert detect_ci_provider(tmp_path) == "travis"

    def test_detects_azure(self, tmp_path: Path) -> None:
        (tmp_path / "azure-pipelines.yml").touch()
        assert detect_ci_provider(tmp_path) == "azure"

    def test_defaults_to_github(self, tmp_path: Path) -> None:
        assert detect_ci_provider(tmp_path) == "github"

    def test_priority_github_over_gitlab(self, tmp_path: Path) -> None:
        """GitHub wins when both exist (first in priority order)."""
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        (tmp_path / ".gitlab-ci.yml").touch()
        assert detect_ci_provider(tmp_path) == "github"


class TestDetectDefaultBranch:
    @patch("launchkit.detectors.environment._git_remote_head", return_value="main")
    def test_from_remote_head(self, mock_head: object, tmp_path: Path) -> None:
        assert detect_default_branch(tmp_path) == "main"

    @patch("launchkit.detectors.environment._git_remote_head", return_value="develop")
    def test_custom_default(self, mock_head: object, tmp_path: Path) -> None:
        assert detect_default_branch(tmp_path) == "develop"

    @patch("launchkit.detectors.environment._git_remote_head", return_value=None)
    @patch("launchkit.detectors.environment._git_local_branches", return_value=["main", "feature/x"])
    def test_fallback_to_main(self, mock_branches: object, mock_head: object, tmp_path: Path) -> None:
        assert detect_default_branch(tmp_path) == "main"

    @patch("launchkit.detectors.environment._git_remote_head", return_value=None)
    @patch("launchkit.detectors.environment._git_local_branches", return_value=["master", "feature/x"])
    def test_fallback_to_master(self, mock_branches: object, mock_head: object, tmp_path: Path) -> None:
        assert detect_default_branch(tmp_path) == "master"

    @patch("launchkit.detectors.environment._git_remote_head", return_value=None)
    @patch("launchkit.detectors.environment._git_local_branches", return_value=[])
    def test_ultimate_fallback(self, mock_branches: object, mock_head: object, tmp_path: Path) -> None:
        assert detect_default_branch(tmp_path) == "main"


class TestDetectBranchStrategy:
    @patch("launchkit.detectors.environment._git_remote_head", return_value="main")
    @patch("launchkit.detectors.environment._git_local_branches", return_value=["main", "feature/x"])
    def test_trunk_based(self, mock_b: object, mock_h: object, tmp_path: Path) -> None:
        branches = detect_branch_strategy(tmp_path)
        assert branches == ["main"]

    @patch("launchkit.detectors.environment._git_remote_head", return_value="main")
    @patch("launchkit.detectors.environment._git_local_branches", return_value=["main", "develop", "feature/x"])
    def test_gitflow_detects_develop(self, mock_b: object, mock_h: object, tmp_path: Path) -> None:
        branches = detect_branch_strategy(tmp_path)
        assert "main" in branches
        assert "develop" in branches

    @patch("launchkit.detectors.environment._git_remote_head", return_value="main")
    @patch("launchkit.detectors.environment._git_local_branches", return_value=["main", "release/1.0", "release/2.0"])
    def test_release_branches(self, mock_b: object, mock_h: object, tmp_path: Path) -> None:
        branches = detect_branch_strategy(tmp_path)
        assert "release/*" in branches


class TestDetectHasTests:
    def test_python_tests_dir(self, tmp_path: Path) -> None:
        (tmp_path / "tests").mkdir()
        assert _detect_has_tests(tmp_path) is True

    def test_node_test_script(self, tmp_path: Path) -> None:
        pkg = {"scripts": {"test": "jest"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert _detect_has_tests(tmp_path) is True

    def test_node_no_real_test(self, tmp_path: Path) -> None:
        """The npm default test script shouldn't count."""
        pkg = {"scripts": {"test": 'echo "Error: no test specified" && exit 1'}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        assert _detect_has_tests(tmp_path) is False

    def test_empty_project(self, tmp_path: Path) -> None:
        assert _detect_has_tests(tmp_path) is False


class TestDetectRegistry:
    @patch("launchkit.detectors.environment._git_remote_url", return_value="git@github.com:myorg/myrepo.git")
    def test_github_ssh(self, mock_url: object, tmp_path: Path) -> None:
        result = _detect_registry(tmp_path)
        assert result == "ghcr.io/myorg/myrepo"

    @patch("launchkit.detectors.environment._git_remote_url", return_value="https://github.com/myorg/myrepo.git")
    def test_github_https(self, mock_url: object, tmp_path: Path) -> None:
        result = _detect_registry(tmp_path)
        assert result == "ghcr.io/myorg/myrepo"

    @patch("launchkit.detectors.environment._git_remote_url", return_value="git@gitlab.com:team/project.git")
    def test_gitlab(self, mock_url: object, tmp_path: Path) -> None:
        result = _detect_registry(tmp_path)
        assert result == "registry.gitlab.com/team/project"

    @patch("launchkit.detectors.environment._git_remote_url", return_value=None)
    def test_no_remote(self, mock_url: object, tmp_path: Path) -> None:
        result = _detect_registry(tmp_path)
        assert result is None


class TestDetectEnvironment:
    @patch("launchkit.detectors.environment._git_remote_head", return_value="main")
    @patch("launchkit.detectors.environment._git_local_branches", return_value=["main"])
    @patch("launchkit.detectors.environment._git_remote_url", return_value=None)
    def test_full_context(self, mock_url: object, mock_b: object, mock_h: object, tmp_path: Path) -> None:
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        (tmp_path / "tests").mkdir()

        ctx = detect_environment(tmp_path)
        assert ctx.ci_provider == "github"
        assert ctx.default_branch == "main"
        assert ctx.has_tests is True
        assert ctx.branches == ["main"]
