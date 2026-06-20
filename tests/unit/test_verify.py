"""Tests for the verify engine — deterministic Level 0 checks and graceful skips."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from rich.console import Console

from launchkit.core.config import load_and_validate
from launchkit.core.verify import (
    VerifyEngine,
    _image_tag,
    _is_cluster_unreachable,
    _materialize,
    _published_port,
)


@pytest.fixture
def quiet_console() -> Console:
    return Console(quiet=True)


def _write_config(tmp_path: Path, cfg: dict) -> Path:
    path = tmp_path / "launchkit.yaml"
    path.write_text(yaml.dump(cfg))
    return path


def _base_config(**service_overrides) -> dict:
    service = {
        "lang": "python",
        "framework": "fastapi",
        "port": 8000,
        "healthcheck": "/health",
        "scale": {"min": 1, "max": 5, "cpu_threshold": 70},
    }
    service.update(service_overrides)
    return {
        "version": "1",
        "project": {"name": "testapp", "registry": "ghcr.io/test/testapp"},
        "services": {"api": service},
        "ci": {"provider": "github", "affected_only": False, "steps": ["build", "push"]},
        "deploy": {"target": "kubernetes", "namespace": "production"},
    }


class TestLevel0Deterministic:
    def test_clean_config_has_no_failures(self, tmp_path: Path, quiet_console: Console) -> None:
        path = _write_config(tmp_path, _base_config())
        engine = VerifyEngine(config_path=str(path), console=quiet_console)
        cfg = load_and_validate(str(path))
        results = engine.collect_results(cfg, tmp_path)
        assert not any(r.status == "fail" for r in results)

    def test_missing_healthcheck_web_service_fails(
        self, tmp_path: Path, quiet_console: Console
    ) -> None:
        cfg_dict = _base_config()
        del cfg_dict["services"]["api"]["healthcheck"]
        path = _write_config(tmp_path, cfg_dict)
        engine = VerifyEngine(config_path=str(path), console=quiet_console)
        cfg = load_and_validate(str(path))
        results = engine.collect_results(cfg, tmp_path)
        # The linter's no-healthcheck rule is an ERROR → surfaces as a verify fail.
        assert any(r.check == "lint:no-healthcheck" and r.status == "fail" for r in results)
        # And the run exits non-zero.
        assert engine.run() == 1

    def test_k8s_manifests_have_valid_shape(self, tmp_path: Path, quiet_console: Console) -> None:
        path = _write_config(tmp_path, _base_config())
        engine = VerifyEngine(config_path=str(path), console=quiet_console)
        cfg = load_and_validate(str(path))
        results = engine.collect_results(cfg, tmp_path)
        shape = [r for r in results if r.check == "k8s-shape"]
        assert shape and all(r.status == "pass" for r in shape)

    def test_ci_context_exists_flat(self, tmp_path: Path, quiet_console: Console) -> None:
        path = _write_config(tmp_path, _base_config())
        engine = VerifyEngine(config_path=str(path), console=quiet_console)
        cfg = load_and_validate(str(path))
        results = engine.collect_results(cfg, tmp_path)
        ctx = [r for r in results if r.check == "ci-context"]
        assert ctx and all(r.status == "pass" for r in ctx)

    def test_ci_context_missing_monorepo_dir_fails(
        self, tmp_path: Path, quiet_console: Console
    ) -> None:
        # Two services → monorepo layout expected under services/<name>, but we
        # never create those dirs, so the context check must fail.
        cfg_dict = _base_config()
        cfg_dict["services"]["worker"] = {"lang": "python", "type": "worker"}
        cfg_dict["ci"]["affected_only"] = True
        path = _write_config(tmp_path, cfg_dict)
        engine = VerifyEngine(config_path=str(path), console=quiet_console)
        cfg = load_and_validate(str(path))
        results = engine.collect_results(cfg, tmp_path)
        ctx = [r for r in results if r.check == "ci-context"]
        assert ctx and all(r.status == "fail" for r in ctx)


class TestGracefulSkips:
    def test_hadolint_skips_when_absent(self, tmp_path: Path, quiet_console: Console, monkeypatch) -> None:
        import launchkit.core.verify as verify_mod
        # Force all external tools to look absent.
        monkeypatch.setattr(verify_mod, "find_tool", lambda cmd: None)
        monkeypatch.setattr(verify_mod, "docker_compose_cmd", lambda: None)

        path = _write_config(tmp_path, _base_config())
        engine = VerifyEngine(config_path=str(path), console=quiet_console)
        cfg = load_and_validate(str(path))
        results = engine.collect_results(cfg, tmp_path)

        hadolint = [r for r in results if r.check == "hadolint"]
        assert hadolint and hadolint[0].status == "skip"
        # No external-tool check should hard-fail when the tool is missing.
        assert not any(r.status == "fail" for r in results)


class TestBuildSmokeGating:
    def test_build_level_skips_without_docker(
        self, tmp_path: Path, quiet_console: Console, monkeypatch
    ) -> None:
        import launchkit.core.verify as verify_mod
        monkeypatch.setattr(verify_mod, "find_tool", lambda cmd: None)
        monkeypatch.setattr(verify_mod, "docker_compose_cmd", lambda: None)

        path = _write_config(tmp_path, _base_config())
        engine = VerifyEngine(config_path=str(path), level="build", console=quiet_console)
        cfg = load_and_validate(str(path))
        results = engine.collect_results(cfg, tmp_path)

        build = [r for r in results if r.check == "docker-build"]
        assert build and build[0].status == "skip"
        assert not any(r.status == "fail" for r in results)

    def test_static_level_never_builds(
        self, tmp_path: Path, quiet_console: Console, monkeypatch
    ) -> None:
        # At static level, the build/smoke path must not run at all.
        import launchkit.core.verify as verify_mod
        called = {"build": False}

        def _boom(*a, **k):
            called["build"] = True
            return []

        monkeypatch.setattr(VerifyEngine, "_check_build_and_smoke", lambda self, *a, **k: _boom())
        path = _write_config(tmp_path, _base_config())
        engine = VerifyEngine(config_path=str(path), level="static", console=quiet_console)
        cfg = load_and_validate(str(path))
        engine.collect_results(cfg, tmp_path)
        assert called["build"] is False


class TestHelpers:
    def test_image_tag_is_safe_and_lowercase(self) -> None:
        assert _image_tag("My Service!") == "launchkit-verify-my-service:latest"
        assert _image_tag("api") == "launchkit-verify-api:latest"

    def test_published_port_parsing(self, monkeypatch) -> None:
        import launchkit.core.verify as verify_mod
        monkeypatch.setattr(verify_mod, "_capture", lambda cmd, timeout=10: (True, "127.0.0.1:54321"))
        assert _published_port("abc", 8000) == 54321

    def test_published_port_none_on_failure(self, monkeypatch) -> None:
        import launchkit.core.verify as verify_mod
        monkeypatch.setattr(verify_mod, "_capture", lambda cmd, timeout=10: (False, ""))
        assert _published_port("abc", 8000) is None

    def test_is_cluster_unreachable(self) -> None:
        assert _is_cluster_unreachable("failed to download openapi: ...")
        assert _is_cluster_unreachable("The connection to the server localhost:8080 was refused")
        assert not _is_cluster_unreachable("spec.replicas: Invalid value: -1")

    def test_materialize_preserves_layout(self, tmp_path: Path) -> None:
        root = tmp_path / "proj"
        root.mkdir()
        generated = {
            root / "Dockerfile": "FROM python\n",
            root / "k8s" / "api" / "deployment.yaml": "kind: Deployment\n",
        }
        out = tmp_path / "out"
        out.mkdir()
        materialized = _materialize(generated, root, out)
        assert (out / "Dockerfile").read_text() == "FROM python\n"
        assert (out / "k8s" / "api" / "deployment.yaml").exists()
        # Original keys preserved for labeling.
        assert set(materialized.keys()) == set(generated.keys())
