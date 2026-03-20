"""Tests for Kubernetes manifest generators."""

from __future__ import annotations

import yaml as pyyaml
import pytest

from launchkit.core.config import (
    LaunchKitConfig,
    ServiceConfig,
    Lang,
    ServiceType,
    ScaleConfig,
    load_and_validate,
)
from launchkit.generators.kubernetes.deployment import generate_deployment
from launchkit.generators.kubernetes.service import generate_service
from launchkit.generators.kubernetes.hpa import generate_hpa
from launchkit.generators.kubernetes.ingress import generate_ingress


@pytest.fixture
def k8s_config(sample_config_yaml) -> LaunchKitConfig:
    return load_and_validate(str(sample_config_yaml))


class TestDeployment:
    def test_generates_valid_yaml(self, k8s_config: LaunchKitConfig) -> None:
        result = generate_deployment("api", k8s_config.services["api"], k8s_config)
        # Strip header comments and parse
        yaml_part = "\n".join(
            line for line in result.split("\n") if not line.startswith("#")
        )
        parsed = pyyaml.safe_load(yaml_part)
        assert parsed["kind"] == "Deployment"
        assert parsed["metadata"]["name"] == "api"
        assert parsed["metadata"]["namespace"] == "production"

    def test_has_health_probes(self, k8s_config: LaunchKitConfig) -> None:
        result = generate_deployment("api", k8s_config.services["api"], k8s_config)
        assert "livenessProbe" in result
        assert "readinessProbe" in result
        assert "/health" in result

    def test_has_labels(self, k8s_config: LaunchKitConfig) -> None:
        result = generate_deployment("api", k8s_config.services["api"], k8s_config)
        assert "managed-by: launchkit" in result
        assert "app: api" in result

    def test_has_resources(self, k8s_config: LaunchKitConfig) -> None:
        result = generate_deployment("api", k8s_config.services["api"], k8s_config)
        assert "requests:" in result
        assert "limits:" in result

    def test_worker_no_port(self, tmp_path, sample_config_dict) -> None:
        import yaml
        sample_config_dict["services"]["worker"] = {
            "lang": "python",
            "type": "worker",
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(sample_config_dict))
        cfg = load_and_validate(str(path))
        result = generate_deployment("worker", cfg.services["worker"], cfg)
        assert "containerPort" not in result


class TestService:
    def test_generates_clusterip(self, k8s_config: LaunchKitConfig) -> None:
        result = generate_service("api", k8s_config.services["api"], k8s_config)
        yaml_part = "\n".join(
            line for line in result.split("\n") if not line.startswith("#")
        )
        parsed = pyyaml.safe_load(yaml_part)
        assert parsed["kind"] == "Service"
        assert parsed["spec"]["type"] == "ClusterIP"
        assert parsed["spec"]["ports"][0]["targetPort"] == 8000


class TestHPA:
    def test_generates_hpa(self, k8s_config: LaunchKitConfig) -> None:
        result = generate_hpa("api", k8s_config.services["api"], k8s_config)
        yaml_part = "\n".join(
            line for line in result.split("\n") if not line.startswith("#")
        )
        parsed = pyyaml.safe_load(yaml_part)
        assert parsed["kind"] == "HorizontalPodAutoscaler"
        assert parsed["spec"]["minReplicas"] == 1
        assert parsed["spec"]["maxReplicas"] == 5

    def test_cpu_metric(self, k8s_config: LaunchKitConfig) -> None:
        result = generate_hpa("api", k8s_config.services["api"], k8s_config)
        assert "cpu" in result
        assert "70" in result

    def test_memory_metric_optional(self, tmp_path, sample_config_dict) -> None:
        import yaml
        sample_config_dict["services"]["api"]["scale"]["memory_threshold"] = 80
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(sample_config_dict))
        cfg = load_and_validate(str(path))
        result = generate_hpa("api", cfg.services["api"], cfg)
        assert "memory" in result


class TestIngress:
    def test_generates_ingress(self, tmp_path, sample_config_dict) -> None:
        import yaml
        sample_config_dict["deploy"]["ingress"] = {
            "enabled": True,
            "host": "test.example.com",
            "tls": False,
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(sample_config_dict))
        cfg = load_and_validate(str(path))

        result = generate_ingress(cfg)
        yaml_part = "\n".join(
            line for line in result.split("\n") if not line.startswith("#")
        )
        parsed = pyyaml.safe_load(yaml_part)
        assert parsed["kind"] == "Ingress"
        assert parsed["spec"]["rules"][0]["host"] == "test.example.com"

    def test_tls_cert_manager(self, tmp_path, sample_config_dict) -> None:
        import yaml
        sample_config_dict["deploy"]["ingress"] = {
            "enabled": True,
            "host": "test.example.com",
            "tls": True,
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(sample_config_dict))
        cfg = load_and_validate(str(path))

        result = generate_ingress(cfg)
        assert "cert-manager" in result
        assert "tls:" in result
