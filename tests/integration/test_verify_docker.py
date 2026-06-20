"""Docker-gated integration tests for build/smoke verification.

These actually build an image and boot a container, so they're skipped when
Docker isn't available (e.g. most CI runners without a daemon).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from rich.console import Console

from launchkit.core.config import load_and_validate
from launchkit.core.engine import GenerateEngine, InitEngine
from launchkit.core.measure import MeasureEngine
from launchkit.core.verify import VerifyEngine


def _docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10
        ).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not _docker_available(), reason="Docker not available"
)


@pytest.fixture
def quiet_console() -> Console:
    return Console(quiet=True)


def _make_fastapi_app(root: Path) -> None:
    (root / "requirements.txt").write_text("fastapi\nuvicorn\n")
    (root / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n\n"
        "@app.get('/health')\n"
        "def health():\n"
        "    return {'status': 'ok'}\n"
    )


class TestBuildSmokeReal:
    def test_generated_fastapi_builds_and_boots(
        self, tmp_path: Path, quiet_console: Console
    ) -> None:
        _make_fastapi_app(tmp_path)
        InitEngine(root=str(tmp_path), force=False, console=quiet_console).run()
        GenerateEngine(
            config_path=str(tmp_path / "launchkit.yaml"),
            only=None, dry_run=False, console=quiet_console,
        ).run()

        engine = VerifyEngine(
            config_path=str(tmp_path / "launchkit.yaml"),
            level="smoke", console=quiet_console,
        )
        assert engine.run() == 0  # builds, boots, /health returns 2xx

    def test_wrong_command_fails_smoke_with_hint(
        self, tmp_path: Path, quiet_console: Console
    ) -> None:
        _make_fastapi_app(tmp_path)
        InitEngine(root=str(tmp_path), force=False, console=quiet_console).run()

        # Sabotage the detected command so the container can't boot.
        cfg_path = tmp_path / "launchkit.yaml"
        cfg_path.write_text(cfg_path.read_text().replace("main:app", "nonexistent:app"))

        GenerateEngine(
            config_path=str(cfg_path), only=None, dry_run=False, console=quiet_console,
        ).run()

        engine = VerifyEngine(config_path=str(cfg_path), level="smoke", console=quiet_console)
        cfg = __import__("launchkit.core.config", fromlist=["load_and_validate"]).load_and_validate(str(cfg_path))
        results = engine.collect_results(cfg, tmp_path)

        smoke = [r for r in results if r.check == "smoke"]
        assert smoke and smoke[0].status == "fail"
        assert smoke[0].fix_hint and "command" in smoke[0].fix_hint


class TestMeasureReal:
    def test_measure_observes_and_applies(
        self, tmp_path: Path, quiet_console: Console
    ) -> None:
        _make_fastapi_app(tmp_path)
        InitEngine(root=str(tmp_path), force=False, console=quiet_console).run()
        cfg_path = tmp_path / "launchkit.yaml"
        GenerateEngine(
            config_path=str(cfg_path), only=None, dry_run=False, console=quiet_console,
        ).run()

        MeasureEngine(
            config_path=str(cfg_path), console=quiet_console, apply=True,
        ).run()

        cfg = load_and_validate(str(cfg_path))
        res = cfg.services[tmp_path.name].resources
        # A trivial FastAPI app fits well under 512Mi — measurement should have
        # recorded a real peak and marked the source as measured.
        assert res.source == "measured"
        assert res.measured_peak_mi is not None and res.measured_peak_mi > 0

    def test_measure_is_deterministic(
        self, tmp_path: Path, quiet_console: Console
    ) -> None:
        _make_fastapi_app(tmp_path)
        InitEngine(root=str(tmp_path), force=False, console=quiet_console).run()
        cfg_path = tmp_path / "launchkit.yaml"
        GenerateEngine(
            config_path=str(cfg_path), only=None, dry_run=False, console=quiet_console,
        ).run()

        MeasureEngine(config_path=str(cfg_path), console=quiet_console, apply=True).run()
        first = load_and_validate(str(cfg_path)).services[tmp_path.name].resources
        MeasureEngine(config_path=str(cfg_path), console=quiet_console, apply=True).run()
        second = load_and_validate(str(cfg_path)).services[tmp_path.name].resources

        # Bucketing must make repeated runs land on the same request/limit.
        assert first.memory_request == second.memory_request
        assert first.memory_limit == second.memory_limit
