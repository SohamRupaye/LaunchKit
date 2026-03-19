"""Tests for linter rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from launchkit.core.config import LaunchKitConfig
from launchkit.core.linter import run_lint, Severity, _parse_memory_mi


class TestLintRules:
    def test_no_healthcheck(self, sample_config_dict: dict) -> None:
        """Web service without healthcheck should trigger error."""
        cfg = dict(sample_config_dict)
        cfg["services"]["api"].pop("healthcheck", None)
        config = LaunchKitConfig.model_validate(cfg)
        results = run_lint(config)
        rules = [r.rule for r in results]
        assert "no-healthcheck" in rules
        assert any(r.severity == Severity.ERROR for r in results if r.rule == "no-healthcheck")

    def test_latest_tag_in_production(self, sample_config_dict: dict) -> None:
        config = LaunchKitConfig.model_validate(sample_config_dict)
        results = run_lint(config)
        rules = [r.rule for r in results]
        assert "latest-tag" in rules

    def test_no_latest_warning_in_staging(self, sample_config_dict: dict) -> None:
        cfg = dict(sample_config_dict)
        cfg["deploy"]["namespace"] = "staging"
        config = LaunchKitConfig.model_validate(cfg)
        results = run_lint(config)
        rules = [r.rule for r in results]
        assert "latest-tag" not in rules

    def test_single_replica_production(self, sample_config_dict: dict) -> None:
        config = LaunchKitConfig.model_validate(sample_config_dict)
        results = run_lint(config)
        rules = [r.rule for r in results]
        assert "no-replicas" in rules

    def test_cpu_scaling_io_python(self, sample_config_dict: dict) -> None:
        config = LaunchKitConfig.model_validate(sample_config_dict)
        results = run_lint(config)
        rules = [r.rule for r in results]
        assert "cpu-scaling-io" in rules

    def test_worker_with_healthcheck(self, sample_config_dict: dict) -> None:
        cfg = dict(sample_config_dict)
        cfg["services"]["worker"] = {
            "lang": "python",
            "type": "worker",
            "healthcheck": "/health",
        }
        config = LaunchKitConfig.model_validate(cfg)
        results = run_lint(config)
        rules = [r.rule for r in results]
        assert "worker-has-probe" in rules

    def test_memory_mismatch(self, sample_config_dict: dict) -> None:
        cfg = dict(sample_config_dict)
        cfg["services"]["api"]["resources"] = {
            "profile": "heavy-api",
            "cpu_request": "250m",
            "cpu_limit": "1000m",
            "memory_request": "512Mi",
            "memory_limit": "1Gi",
        }
        config = LaunchKitConfig.model_validate(cfg)
        results = run_lint(config)
        rules = [r.rule for r in results]
        assert "memory-mismatch" in rules

    def test_no_environments_hint(self, sample_config_dict: dict) -> None:
        config = LaunchKitConfig.model_validate(sample_config_dict)
        results = run_lint(config)
        rules = [r.rule for r in results]
        assert "no-environments" in rules

    def test_missing_env_file(self, sample_config_dict: dict, tmp_path: Path) -> None:
        cfg = dict(sample_config_dict)
        cfg["services"]["api"]["env_file"] = ".env"
        config = LaunchKitConfig.model_validate(cfg)
        results = run_lint(config, tmp_path)
        rules = [r.rule for r in results]
        assert "missing-env" in rules

    def test_clean_config(self, sample_config_dict: dict) -> None:
        """A well-configured service should produce minimal issues."""
        cfg = dict(sample_config_dict)
        cfg["deploy"]["namespace"] = "staging"
        cfg["services"]["api"]["healthcheck"] = "/health"
        cfg["services"]["api"]["scale"] = {"min": 2, "max": 5, "cpu_threshold": 70}
        cfg["environments"] = {"staging": {"namespace": "staging"}}
        config = LaunchKitConfig.model_validate(cfg)
        results = run_lint(config)
        errors = [r for r in results if r.severity == Severity.ERROR]
        assert len(errors) == 0


class TestParseMemory:
    def test_mi(self) -> None:
        assert _parse_memory_mi("512Mi") == 512

    def test_gi(self) -> None:
        assert _parse_memory_mi("2Gi") == 2048

    def test_invalid(self) -> None:
        assert _parse_memory_mi("invalid") == 0
