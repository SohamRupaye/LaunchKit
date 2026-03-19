"""Tests for CLI entrypoint via Click's CliRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from launchkit.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestCLIHelp:
    def test_main_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "LaunchKit" in result.output
        assert "generate" in result.output
        assert "init" in result.output
        assert "lint" in result.output
        assert "eject" in result.output
        assert "upgrade" in result.output

    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_generate_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["generate", "--help"])
        assert result.exit_code == 0
        assert "--only" in result.output
        assert "--dry-run" in result.output
        assert "--env" in result.output
        assert "nginx" in result.output

    def test_init_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["init", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output
        assert "--path" in result.output

    def test_validate_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["validate", "--help"])
        assert result.exit_code == 0

    def test_diff_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["diff", "--help"])
        assert result.exit_code == 0

    def test_doctor_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["doctor", "--help"])
        assert result.exit_code == 0

    def test_lint_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["lint", "--help"])
        assert result.exit_code == 0
        assert "--config" in result.output

    def test_eject_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["eject", "--help"])
        assert result.exit_code == 0
        assert "--yes" in result.output

    def test_upgrade_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["upgrade", "--help"])
        assert result.exit_code == 0
        assert "--yes" in result.output


class TestCLIInit:
    def test_init_creates_config(self, runner: CliRunner, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("fastapi>=0.110\n")
        result = runner.invoke(main, ["init", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "launchkit.yaml").exists()

    def test_init_scaffolds_environments(self, runner: CliRunner, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("fastapi>=0.110\n")
        runner.invoke(main, ["init", "--path", str(tmp_path)])
        config = yaml.safe_load((tmp_path / "launchkit.yaml").read_text())
        assert "environments" in config
        assert "staging" in config["environments"]
        assert "production" in config["environments"]

    def test_init_no_project(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["init", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert "No services detected" in result.output


class TestCLIValidate:
    def test_validate_valid(self, runner: CliRunner, sample_config_yaml: Path) -> None:
        result = runner.invoke(main, ["validate", "--config", str(sample_config_yaml)])
        assert result.exit_code == 0
        assert "valid" in result.output

    def test_validate_missing(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["validate", "--config", str(tmp_path / "nope.yaml")])
        assert result.exit_code == 1


class TestCLIGenerate:
    def test_generate_dry_run(self, runner: CliRunner, sample_config_yaml: Path) -> None:
        result = runner.invoke(main, [
            "generate", "--config", str(sample_config_yaml), "--dry-run",
        ])
        assert result.exit_code == 0
        assert "dry-run" in result.output

    def test_generate_only_docker(self, runner: CliRunner, sample_config_yaml: Path) -> None:
        result = runner.invoke(main, [
            "generate", "--config", str(sample_config_yaml), "--only", "docker",
        ])
        assert result.exit_code == 0
        assert (sample_config_yaml.parent / "Dockerfile").exists()

    def test_generate_with_env(self, runner: CliRunner, tmp_path: Path) -> None:
        cfg = {
            "version": "1",
            "project": {"name": "test", "registry": "ghcr.io/test/test"},
            "services": {"api": {"lang": "python", "port": 8000, "healthcheck": "/health"}},
            "environments": {
                "staging": {"namespace": "staging", "scale": {"max": 2}},
            },
            "deploy": {"target": "kubernetes"},
        }
        config_path = tmp_path / "launchkit.yaml"
        config_path.write_text(yaml.dump(cfg))
        result = runner.invoke(main, [
            "generate", "--config", str(config_path), "--env", "staging", "--only", "k8s",
        ])
        assert result.exit_code == 0
        assert "staging" in result.output
        assert (tmp_path / "k8s" / "staging" / "api" / "deployment.yaml").exists()

    def test_generate_invalid_env(self, runner: CliRunner, sample_config_yaml: Path) -> None:
        result = runner.invoke(main, [
            "generate", "--config", str(sample_config_yaml), "--env", "nonexistent",
        ])
        assert result.exit_code == 1

    def test_generate_missing_config(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, [
            "generate", "--config", str(tmp_path / "nope.yaml"),
        ])
        assert result.exit_code == 1


class TestCLIDoctor:
    def test_doctor_runs(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["doctor"])
        assert result.exit_code == 0
        assert "Docker" in result.output


class TestCLILint:
    def test_lint_finds_issues(self, runner: CliRunner, sample_config_yaml: Path) -> None:
        result = runner.invoke(main, ["lint", "--config", str(sample_config_yaml)])
        assert result.exit_code == 0  # warnings don't cause exit 1
        assert "issue(s)" in result.output

    def test_lint_missing_config(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["lint", "--config", str(tmp_path / "nope.yaml")])
        assert result.exit_code == 1

    def test_lint_error_exits_1(self, runner: CliRunner, tmp_path: Path) -> None:
        """A web service without healthcheck triggers an error → exit 1."""
        cfg = {
            "version": "1",
            "project": {"name": "test", "registry": "test"},
            "services": {"api": {"lang": "python", "port": 8000}},
            "deploy": {"namespace": "staging"},
        }
        config_path = tmp_path / "launchkit.yaml"
        config_path.write_text(yaml.dump(cfg))
        result = runner.invoke(main, ["lint", "--config", str(config_path)])
        assert result.exit_code == 1
        assert "no-healthcheck" in result.output or "healthcheck" in result.output


class TestCLIEject:
    def test_eject_no_config(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["eject", "--path", str(tmp_path), "--yes"])
        assert result.exit_code == 0
        assert "nothing to eject" in result.output.lower() or "No launchkit" in result.output
