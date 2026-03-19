"""Tests for config loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from launchkit.core.config import (
    LaunchKitConfig,
    Lang,
    ServiceType,
    CIProvider,
    DeployTarget,
    load_and_validate,
)


class TestLoadAndValidate:
    def test_loads_valid_config(self, sample_config_yaml: Path) -> None:
        cfg = load_and_validate(str(sample_config_yaml))
        assert cfg.project.name == "testapp"
        assert cfg.project.registry == "ghcr.io/test/testapp"
        assert "api" in cfg.services

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            load_and_validate(str(tmp_path / "nonexistent.yaml"))

    def test_invalid_lang(self, tmp_path: Path) -> None:
        config = {
            "version": "1",
            "project": {"name": "test", "registry": "r"},
            "services": {"api": {"lang": "cobol"}},
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(config))
        with pytest.raises(Exception):
            load_and_validate(str(path))

    def test_worker_with_port_fails(self, tmp_path: Path) -> None:
        config = {
            "version": "1",
            "project": {"name": "test", "registry": "r"},
            "services": {
                "worker": {"lang": "python", "type": "worker", "port": 8000}
            },
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(config))
        with pytest.raises(Exception, match="Worker"):
            load_and_validate(str(path))


class TestServiceConfig:
    def test_defaults(self, sample_config_yaml: Path) -> None:
        cfg = load_and_validate(str(sample_config_yaml))
        api = cfg.services["api"]
        assert api.lang == Lang.PYTHON
        assert api.type == ServiceType.WEB
        assert api.scale.min == 1
        assert api.scale.max == 5
        assert api.scale.cpu_threshold == 70
        assert api.scale.memory_threshold is None

    def test_worker_type(self, tmp_path: Path) -> None:
        config = {
            "version": "1",
            "project": {"name": "test", "registry": "r"},
            "services": {
                "bg": {"lang": "python", "type": "worker"}
            },
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(config))
        cfg = load_and_validate(str(path))
        assert cfg.services["bg"].type == ServiceType.WORKER
        assert cfg.services["bg"].port is None


class TestCIConfig:
    def test_defaults(self, sample_config_yaml: Path) -> None:
        cfg = load_and_validate(str(sample_config_yaml))
        assert cfg.ci.provider == CIProvider.GITHUB
        assert cfg.ci.registry_secret == "REGISTRY_TOKEN"

    def test_gitlab_provider(self, tmp_path: Path) -> None:
        config = {
            "version": "1",
            "project": {"name": "test", "registry": "r"},
            "services": {"api": {"lang": "python"}},
            "ci": {"provider": "gitlab"},
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(config))
        cfg = load_and_validate(str(path))
        assert cfg.ci.provider == CIProvider.GITLAB


class TestDeployConfig:
    def test_defaults(self) -> None:
        cfg = LaunchKitConfig(
            version="1",
            project={"name": "t", "registry": "r"},  # type: ignore
            services={"api": {"lang": "python"}},  # type: ignore
        )
        assert cfg.deploy.target == DeployTarget.KUBERNETES
        assert cfg.deploy.namespace == "default"
        assert cfg.deploy.ingress.enabled is False
