"""Tests for CI generators."""

from __future__ import annotations

import pytest

from launchkit.core.config import load_and_validate, LaunchKitConfig
from launchkit.generators.ci.github import generate_github_actions
from launchkit.generators.ci.gitlab import generate_gitlab_ci


class TestGitHubActions:
    def test_single_service(self, sample_config_yaml) -> None:
        cfg = load_and_validate(str(sample_config_yaml))
        result = generate_github_actions(cfg)
        assert "name: CI" in result
        assert "build-api:" in result
        assert "actions/checkout@v4" in result
        assert "docker/build-push-action@v5" in result

    def test_monorepo_affected_only(self, tmp_path, sample_config_dict) -> None:
        import yaml

        sample_config_dict["services"]["frontend"] = {
            "lang": "node",
            "framework": "nextjs",
            "port": 3000,
        }
        sample_config_dict["ci"]["affected_only"] = True

        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(sample_config_dict))
        cfg = load_and_validate(str(path))

        result = generate_github_actions(cfg)
        assert "detect-changes:" in result
        assert "dorny/paths-filter" in result
        assert "needs: detect-changes" in result

    def test_no_affected_only_single(self, sample_config_yaml) -> None:
        cfg = load_and_validate(str(sample_config_yaml))
        result = generate_github_actions(cfg)
        assert "detect-changes" not in result

    def test_registry_in_output(self, sample_config_yaml) -> None:
        cfg = load_and_validate(str(sample_config_yaml))
        result = generate_github_actions(cfg)
        assert "ghcr.io/test/testapp" in result


class TestGitLabCI:
    def test_single_service(self, tmp_path, sample_config_dict) -> None:
        import yaml

        sample_config_dict["ci"]["provider"] = "gitlab"
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(sample_config_dict))
        cfg = load_and_validate(str(path))

        result = generate_gitlab_ci(cfg)
        assert "stages:" in result
        assert "test-api:" in result
        assert "build-api:" in result
        assert "docker:" in result

    def test_affected_only_changes(self, tmp_path, sample_config_dict) -> None:
        import yaml

        sample_config_dict["ci"]["provider"] = "gitlab"
        sample_config_dict["ci"]["affected_only"] = True
        sample_config_dict["services"]["frontend"] = {
            "lang": "node",
            "port": 3000,
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(sample_config_dict))
        cfg = load_and_validate(str(path))

        result = generate_gitlab_ci(cfg)
        assert "rules:" in result
        assert "changes:" in result
