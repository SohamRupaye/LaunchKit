"""Tests for secrets hint generator."""

from __future__ import annotations

from pathlib import Path

import yaml
import pytest

from launchkit.core.config import LaunchKitConfig
from launchkit.generators.kubernetes.secrets import generate_secrets_hint, _extract_env_keys


class TestSecretsHint:
    def test_generates_when_env_file(self, sample_config_dict: dict) -> None:
        cfg = dict(sample_config_dict)
        cfg["services"]["api"]["env_file"] = ".env"
        config = LaunchKitConfig.model_validate(cfg)
        svc = config.services["api"]
        result = generate_secrets_hint("api", svc, config)
        assert result is not None
        assert "HINT" in result
        assert "api-secrets" in result
        assert "External Secrets" in result

    def test_none_without_env_file(self, sample_config_dict: dict) -> None:
        config = LaunchKitConfig.model_validate(sample_config_dict)
        svc = config.services["api"]
        result = generate_secrets_hint("api", svc, config)
        assert result is None

    def test_extracts_keys_from_env(self, tmp_path: Path, sample_config_dict: dict) -> None:
        (tmp_path / ".env").write_text(
            "DATABASE_URL=postgres://localhost:5432/db\n"
            "SECRET_KEY=mysecret\n"
            "# This is a comment\n"
            "REDIS_URL=redis://localhost:6379\n"
        )
        cfg = dict(sample_config_dict)
        cfg["services"]["api"]["env_file"] = ".env"
        config = LaunchKitConfig.model_validate(cfg)
        svc = config.services["api"]
        result = generate_secrets_hint("api", svc, config, root=tmp_path)
        assert "DATABASE_URL" in result
        assert "SECRET_KEY" in result
        assert "REDIS_URL" in result


class TestExtractEnvKeys:
    def test_reads_env_file(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("FOO=bar\nBAZ=qux\n")
        keys = _extract_env_keys(".env", tmp_path)
        assert keys == ["FOO", "BAZ"]

    def test_skips_comments(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("# comment\nFOO=bar\n")
        keys = _extract_env_keys(".env", tmp_path)
        assert keys == ["FOO"]

    def test_missing_file(self, tmp_path: Path) -> None:
        keys = _extract_env_keys(".env", tmp_path)
        assert keys == []

    def test_no_root(self) -> None:
        keys = _extract_env_keys(".env", None)
        assert keys == []
