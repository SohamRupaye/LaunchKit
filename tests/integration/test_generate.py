"""Integration tests — full generate pipeline: config → files on disk."""

from __future__ import annotations

from pathlib import Path

import yaml
import pytest

from launchkit.core.config import load_and_validate
from launchkit.core.engine import GenerateEngine, InitEngine
from launchkit.detectors.base import detect_services
from rich.console import Console


@pytest.fixture
def quiet_console() -> Console:
    """A console that doesn't print to stdout during tests."""
    return Console(quiet=True)


class TestInitEngine:
    def test_init_python_project(self, python_fastapi_project: Path, quiet_console: Console) -> None:
        engine = InitEngine(
            root=str(python_fastapi_project),
            force=False,
            console=quiet_console,
        )
        engine.run()

        config_path = python_fastapi_project / "launchkit.yaml"
        assert config_path.exists()

        # Should be valid YAML
        content = yaml.safe_load(config_path.read_text())
        assert "services" in content
        assert content["version"] == "1"

    def test_init_monorepo(self, monorepo_project: Path, quiet_console: Console) -> None:
        engine = InitEngine(
            root=str(monorepo_project),
            force=False,
            console=quiet_console,
        )
        engine.run()

        config_path = monorepo_project / "launchkit.yaml"
        assert config_path.exists()

        content = yaml.safe_load(config_path.read_text())
        assert len(content["services"]) == 2
        assert content["ci"]["affected_only"] is True

    def test_init_no_overwrite(self, python_fastapi_project: Path, quiet_console: Console) -> None:
        # Create existing config
        (python_fastapi_project / "launchkit.yaml").write_text("existing: true\n")

        engine = InitEngine(
            root=str(python_fastapi_project),
            force=False,
            console=quiet_console,
        )
        engine.run()

        # Should not overwrite
        content = (python_fastapi_project / "launchkit.yaml").read_text()
        assert "existing: true" in content

    def test_init_force_overwrite(self, python_fastapi_project: Path, quiet_console: Console) -> None:
        (python_fastapi_project / "launchkit.yaml").write_text("existing: true\n")

        engine = InitEngine(
            root=str(python_fastapi_project),
            force=True,
            console=quiet_console,
        )
        engine.run()

        content = yaml.safe_load((python_fastapi_project / "launchkit.yaml").read_text())
        assert "services" in content


class TestGenerateEngine:
    def test_generate_all(self, sample_config_yaml: Path, quiet_console: Console) -> None:
        engine = GenerateEngine(
            config_path=str(sample_config_yaml),
            only=None,
            dry_run=False,
            console=quiet_console,
        )
        engine.run()

        root = sample_config_yaml.parent
        # Dockerfile should be created (single service → flat)
        assert (root / "Dockerfile").exists()
        # CI pipeline
        assert (root / ".github" / "workflows" / "ci.yml").exists()
        # K8s manifests
        assert (root / "k8s" / "api" / "deployment.yaml").exists()
        assert (root / "k8s" / "api" / "service.yaml").exists()
        assert (root / "k8s" / "api" / "hpa.yaml").exists()

    def test_generate_only_docker(self, sample_config_yaml: Path, quiet_console: Console) -> None:
        engine = GenerateEngine(
            config_path=str(sample_config_yaml),
            only="docker",
            dry_run=False,
            console=quiet_console,
        )
        engine.run()

        root = sample_config_yaml.parent
        assert (root / "Dockerfile").exists()
        # CI and K8s should NOT be created
        assert not (root / ".github").exists()
        assert not (root / "k8s").exists()

    def test_dry_run(self, sample_config_yaml: Path, quiet_console: Console) -> None:
        engine = GenerateEngine(
            config_path=str(sample_config_yaml),
            only="docker",
            dry_run=True,
            console=quiet_console,
        )
        engine.run()

        root = sample_config_yaml.parent
        # Should NOT create files in dry-run mode
        assert not (root / "Dockerfile").exists()

    def test_generate_compose(self, tmp_path: Path, sample_config_dict, quiet_console: Console) -> None:
        sample_config_dict["deploy"]["target"] = "both"
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(sample_config_dict))

        engine = GenerateEngine(
            config_path=str(path),
            only="compose",
            dry_run=False,
            console=quiet_console,
        )
        engine.run()

        assert (tmp_path / "docker-compose.yml").exists()
