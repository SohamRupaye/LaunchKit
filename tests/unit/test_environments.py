"""Tests for environment profiles — config merging and --env generation."""

from __future__ import annotations

from pathlib import Path

import yaml
import pytest

from launchkit.core.config import (
    LaunchKitConfig,
    apply_environment,
    EnvironmentOverride,
)


@pytest.fixture
def config_with_envs(sample_config_dict: dict) -> LaunchKitConfig:
    cfg = dict(sample_config_dict)
    cfg["environments"] = {
        "staging": {
            "namespace": "staging",
            "domain": "staging.myapp.dev",
            "scale": {"max": 2},
        },
        "production": {
            "namespace": "production",
            "domain": "myapp.dev",
            "tls": True,
            "replicas": 2,
        },
    }
    return LaunchKitConfig.model_validate(cfg)


class TestApplyEnvironment:
    def test_staging_namespace(self, config_with_envs: LaunchKitConfig) -> None:
        result = apply_environment(config_with_envs, "staging")
        assert result.deploy.namespace == "staging"

    def test_staging_domain(self, config_with_envs: LaunchKitConfig) -> None:
        result = apply_environment(config_with_envs, "staging")
        assert result.deploy.ingress.host == "staging.myapp.dev"
        assert result.deploy.ingress.enabled is True

    def test_staging_scale(self, config_with_envs: LaunchKitConfig) -> None:
        result = apply_environment(config_with_envs, "staging")
        for svc in result.services.values():
            assert svc.scale.max == 2

    def test_production_tls(self, config_with_envs: LaunchKitConfig) -> None:
        result = apply_environment(config_with_envs, "production")
        assert result.deploy.ingress.tls is True

    def test_production_replicas(self, config_with_envs: LaunchKitConfig) -> None:
        result = apply_environment(config_with_envs, "production")
        for svc in result.services.values():
            assert svc.scale.min == 2

    def test_unknown_environment(self, config_with_envs: LaunchKitConfig) -> None:
        with pytest.raises(ValueError, match="not found"):
            apply_environment(config_with_envs, "nonexistent")

    def test_no_environments(self, sample_config_dict: dict) -> None:
        config = LaunchKitConfig.model_validate(sample_config_dict)
        with pytest.raises(ValueError, match="not found"):
            apply_environment(config, "staging")

    def test_base_config_unchanged(self, config_with_envs: LaunchKitConfig) -> None:
        """Applying an env should not mutate the original config."""
        original_ns = config_with_envs.deploy.namespace
        _ = apply_environment(config_with_envs, "staging")
        assert config_with_envs.deploy.namespace == original_ns
