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


class TestCITestMatrix:
    """The generated CI must emit a test step for every supported language,
    and the result must be valid YAML."""

    LANG_TEST_CMDS = {
        "python": "pytest",
        "node": "npm test",
        "go": "go test",
        "java": "mvn -B test",
        "rust": "cargo test",
        "ruby": "bundle exec rake",
        "php": "vendor/bin/phpunit",
        "dotnet": "dotnet test",
    }

    def _cfg(self, tmp_path, lang: str, provider: str):
        import yaml
        cfg_dict = {
            "version": "1",
            "project": {"name": "app", "registry": "ghcr.io/x/app"},
            "services": {"svc": {"lang": lang, "port": 8080}},
            "ci": {"provider": provider, "affected_only": False,
                   "steps": ["test", "build", "push"]},
            "deploy": {"target": "kubernetes", "namespace": "production"},
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(cfg_dict))
        return load_and_validate(str(path))

    @pytest.mark.parametrize("lang,cmd", list(LANG_TEST_CMDS.items()))
    def test_github_matrix(self, tmp_path, lang, cmd) -> None:
        import yaml
        cfg = self._cfg(tmp_path, lang, "github")
        result = generate_github_actions(cfg)
        yaml.safe_load(result)  # must parse
        assert cmd in result

    @pytest.mark.parametrize("lang,cmd", list(LANG_TEST_CMDS.items()))
    def test_gitlab_matrix(self, tmp_path, lang, cmd) -> None:
        import yaml
        cfg = self._cfg(tmp_path, lang, "gitlab")
        result = generate_gitlab_ci(cfg)
        yaml.safe_load(result)  # must parse
        assert cmd in result


class TestVerifyGate:
    """The `verify` step should inject a launchkit-verify gate before build."""

    def _cfg(self, tmp_path, provider: str):
        import yaml
        cfg_dict = {
            "version": "1",
            "project": {"name": "app", "registry": "ghcr.io/x/app"},
            "services": {"api": {"lang": "python", "framework": "fastapi", "port": 8000}},
            "ci": {"provider": provider, "affected_only": False,
                   "steps": ["verify", "build", "push"]},
            "deploy": {"target": "kubernetes", "namespace": "production"},
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(cfg_dict))
        return load_and_validate(str(path))

    def test_github_has_verify_step(self, tmp_path) -> None:
        import yaml
        cfg = self._cfg(tmp_path, "github")
        result = generate_github_actions(cfg)
        yaml.safe_load(result)
        assert "launchkit verify --level static" in result

    def test_gitlab_has_verify_stage_and_job(self, tmp_path) -> None:
        import yaml
        cfg = self._cfg(tmp_path, "gitlab")
        result = generate_gitlab_ci(cfg)
        parsed = yaml.safe_load(result)
        assert "verify" in parsed["stages"]
        assert parsed["verify-config"]["stage"] == "verify"
        assert "launchkit verify --level static" in result

    def test_no_verify_step_when_absent(self, tmp_path) -> None:
        import yaml
        cfg_dict = {
            "version": "1",
            "project": {"name": "app", "registry": "ghcr.io/x/app"},
            "services": {"api": {"lang": "python", "port": 8000}},
            "ci": {"provider": "github", "affected_only": False, "steps": ["build", "push"]},
            "deploy": {"target": "kubernetes", "namespace": "production"},
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(cfg_dict))
        cfg = load_and_validate(str(path))
        result = generate_github_actions(cfg)
        assert "launchkit verify" not in result


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
