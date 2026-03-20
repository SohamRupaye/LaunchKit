"""Tests for docker-compose generator."""

from __future__ import annotations

import yaml as pyyaml
import pytest

from launchkit.core.config import load_and_validate
from launchkit.generators.compose import generate_compose


class TestComposeGenerator:
    def test_single_service(self, sample_config_yaml) -> None:
        cfg = load_and_validate(str(sample_config_yaml))
        result = generate_compose(cfg)
        # Strip header comments and parse
        yaml_part = "\n".join(
            line for line in result.split("\n") if not line.startswith("#")
        )
        parsed = pyyaml.safe_load(yaml_part)
        assert "services" in parsed
        assert "api" in parsed["services"]

    def test_service_ports(self, sample_config_yaml) -> None:
        cfg = load_and_validate(str(sample_config_yaml))
        result = generate_compose(cfg)
        assert "8000:8000" in result

    def test_service_image(self, sample_config_yaml) -> None:
        cfg = load_and_validate(str(sample_config_yaml))
        result = generate_compose(cfg)
        assert "ghcr.io/test/testapp/api" in result

    def test_healthcheck(self, sample_config_yaml) -> None:
        cfg = load_and_validate(str(sample_config_yaml))
        result = generate_compose(cfg)
        assert "healthcheck:" in result
        assert "/health" in result

    def test_infrastructure_redis(self, tmp_path, sample_config_dict) -> None:
        import yaml as _yaml
        sample_config_dict["infrastructure"] = {
            "redis": {"type": "redis", "version": "7"}
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(_yaml.dump(sample_config_dict))
        cfg = load_and_validate(str(path))
        result = generate_compose(cfg)
        assert "redis:7" in result

    def test_infrastructure_postgres(self, tmp_path, sample_config_dict) -> None:
        import yaml as _yaml
        sample_config_dict["infrastructure"] = {
            "postgres": {"type": "postgres", "version": "16"}
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(_yaml.dump(sample_config_dict))
        cfg = load_and_validate(str(path))
        result = generate_compose(cfg)
        assert "postgres:16" in result
        assert "POSTGRES_USER" in result
        assert "volumes:" in result

    def test_depends_on(self, tmp_path, sample_config_dict) -> None:
        import yaml as _yaml
        sample_config_dict["services"]["api"]["depends_on"] = ["redis"]
        sample_config_dict["infrastructure"] = {
            "redis": {"type": "redis", "version": "7"}
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(_yaml.dump(sample_config_dict))
        cfg = load_and_validate(str(path))
        result = generate_compose(cfg)
        assert "depends_on:" in result

    def test_restart_policy(self, sample_config_yaml) -> None:
        cfg = load_and_validate(str(sample_config_yaml))
        result = generate_compose(cfg)
        assert "unless-stopped" in result
