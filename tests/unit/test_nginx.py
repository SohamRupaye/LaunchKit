"""Tests for nginx generator."""

from __future__ import annotations

import yaml
import pytest

from launchkit.core.config import LaunchKitConfig
from launchkit.generators.nginx import generate_nginx_conf, generate_nginx_k8s


@pytest.fixture
def multi_service_config(sample_config_dict: dict) -> LaunchKitConfig:
    """Config with two web services for nginx testing."""
    cfg = dict(sample_config_dict)
    cfg["services"] = {
        "api": {
            "lang": "python",
            "framework": "fastapi",
            "port": 8000,
            "healthcheck": "/health",
        },
        "frontend": {
            "lang": "node",
            "framework": "nextjs",
            "port": 3000,
        },
    }
    return LaunchKitConfig.model_validate(cfg)


class TestNginxConf:
    def test_generates_config(self, multi_service_config: LaunchKitConfig) -> None:
        result = generate_nginx_conf(multi_service_config)
        assert "upstream api_backend" in result
        assert "upstream frontend_backend" in result
        assert "proxy_pass http://api_backend" in result

    def test_rate_limiting(self, multi_service_config: LaunchKitConfig) -> None:
        result = generate_nginx_conf(multi_service_config)
        assert "limit_req_zone" in result
        assert "10r/s" in result

    def test_gzip_enabled(self, multi_service_config: LaunchKitConfig) -> None:
        result = generate_nginx_conf(multi_service_config)
        assert "gzip on" in result

    def test_security_headers(self, multi_service_config: LaunchKitConfig) -> None:
        result = generate_nginx_conf(multi_service_config)
        assert "X-Frame-Options" in result
        assert "X-Content-Type-Options" in result

    def test_health_endpoint(self, multi_service_config: LaunchKitConfig) -> None:
        result = generate_nginx_conf(multi_service_config)
        assert "/nginx-health" in result

    def test_websocket_support(self, multi_service_config: LaunchKitConfig) -> None:
        result = generate_nginx_conf(multi_service_config)
        assert "Upgrade" in result

    def test_no_web_services(self, sample_config_dict: dict) -> None:
        """Should return empty string when no web services exist."""
        cfg = dict(sample_config_dict)
        cfg["services"]["api"]["type"] = "worker"
        cfg["services"]["api"].pop("port", None)
        config = LaunchKitConfig.model_validate(cfg)
        result = generate_nginx_conf(config)
        assert result == ""


class TestNginxK8s:
    def test_generates_deployment(self, multi_service_config: LaunchKitConfig) -> None:
        result = generate_nginx_k8s(multi_service_config)
        assert "kind: Deployment" in result
        assert "kind: Service" in result
        assert "kind: ConfigMap" in result
        assert "nginx:1.27-alpine" in result

    def test_loadbalancer_service(self, multi_service_config: LaunchKitConfig) -> None:
        result = generate_nginx_k8s(multi_service_config)
        assert "type: LoadBalancer" in result

    def test_health_probes(self, multi_service_config: LaunchKitConfig) -> None:
        result = generate_nginx_k8s(multi_service_config)
        assert "livenessProbe" in result
        assert "/nginx-health" in result
