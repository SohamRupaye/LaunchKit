"""Tests for measurement logic (deterministic parts — no docker needed)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from rich.console import Console

from launchkit.core.config import load_and_validate
from launchkit.core.linter import run_lint
from launchkit.core.measure import MeasureEngine, _to_mi
from launchkit.detectors.resources import (
    MEM_BUCKETS_MI,
    bucket_up,
    format_memory,
    parse_memory_mi,
)


class TestBucketHelpers:
    def test_bucket_up_rounds_up(self) -> None:
        assert bucket_up(31 * 1.5, MEM_BUCKETS_MI) == 64      # 46.5 → 64
        assert bucket_up(64, MEM_BUCKETS_MI) == 64
        assert bucket_up(65, MEM_BUCKETS_MI) == 128
        assert bucket_up(999999, MEM_BUCKETS_MI) == MEM_BUCKETS_MI[-1]

    def test_bucket_is_deterministic(self) -> None:
        # Jitter within a bucket window collapses to the same bucket.
        assert bucket_up(30 * 1.5, MEM_BUCKETS_MI) == bucket_up(40 * 1.5, MEM_BUCKETS_MI)

    def test_parse_and_format_roundtrip(self) -> None:
        assert parse_memory_mi("512Mi") == 512
        assert parse_memory_mi("1Gi") == 1024
        assert parse_memory_mi("2Gi") == 2048
        assert format_memory(1024) == "1Gi"
        assert format_memory(128) == "128Mi"
        assert format_memory(1536) == "1536Mi"  # not a whole Gi


class TestDockerStatsParsing:
    def test_to_mi(self) -> None:
        assert _to_mi("45.2MiB") == 45
        assert _to_mi("1.2GiB") == 1228
        assert _to_mi("512KiB") == 0  # sub-MiB rounds down
        assert _to_mi("garbage") == 0


class TestMeasurementComputation:
    def _service(self, tmp_path: Path, **res):
        import yaml as y
        cfg = {
            "version": "1",
            "project": {"name": "app", "registry": "ghcr.io/x/app"},
            "services": {"api": {
                "lang": "python", "framework": "fastapi", "port": 8000,
                "resources": {"memory_request": "128Mi", "memory_limit": "512Mi", **res},
            }},
            "ci": {"provider": "github", "affected_only": False, "steps": ["build"]},
            "deploy": {"target": "kubernetes", "namespace": "production"},
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(y.dump(cfg))
        return load_and_validate(str(path)).services["api"], str(path)

    def test_computes_bucketed_request_and_limit(self, tmp_path: Path) -> None:
        svc, path = self._service(tmp_path)
        engine = MeasureEngine(config_path=path, console=Console(quiet=True))
        m = engine._to_measurement("api", svc, peak_mi=31)
        assert m.new_request == "64Mi"    # 31*1.5=46.5 → 64
        assert m.new_limit == "128Mi"     # 64*2 → 128
        assert m.changed is True

    def test_manual_source_not_overwritten(self, tmp_path: Path) -> None:
        svc, path = self._service(tmp_path, source="manual")
        engine = MeasureEngine(config_path=path, console=Console(quiet=True))
        m = engine._to_measurement("api", svc, peak_mi=31)
        assert m.changed is False
        assert m.skipped_reason and "manual" in m.skipped_reason

    def test_already_optimal_not_changed(self, tmp_path: Path) -> None:
        svc, path = self._service(tmp_path, memory_request="64Mi", memory_limit="128Mi")
        engine = MeasureEngine(config_path=path, console=Console(quiet=True))
        m = engine._to_measurement("api", svc, peak_mi=31)
        assert m.changed is False


class TestMeasuredLimitLinterRule:
    def test_fires_when_limit_below_peak(self, tmp_path: Path) -> None:
        cfg_dict = {
            "version": "1",
            "project": {"name": "app", "registry": "ghcr.io/x/app"},
            "services": {"api": {
                "lang": "python", "framework": "fastapi", "port": 8000,
                "healthcheck": "/health",
                "resources": {"memory_limit": "16Mi", "measured_peak_mi": 31},
            }},
            "ci": {"provider": "github", "affected_only": False, "steps": ["build"]},
            "deploy": {"target": "kubernetes", "namespace": "production"},
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(cfg_dict))
        cfg = load_and_validate(str(path))
        results = run_lint(cfg, tmp_path)
        rule = [r for r in results if r.rule == "measured-limit-too-low"]
        assert rule and rule[0].severity.value == "error"

    def test_silent_when_limit_above_peak(self, tmp_path: Path) -> None:
        cfg_dict = {
            "version": "1",
            "project": {"name": "app", "registry": "ghcr.io/x/app"},
            "services": {"api": {
                "lang": "python", "framework": "fastapi", "port": 8000,
                "healthcheck": "/health",
                "resources": {"memory_limit": "128Mi", "measured_peak_mi": 31},
            }},
            "ci": {"provider": "github", "affected_only": False, "steps": ["build"]},
            "deploy": {"target": "kubernetes", "namespace": "production"},
        }
        path = tmp_path / "launchkit.yaml"
        path.write_text(yaml.dump(cfg_dict))
        cfg = load_and_validate(str(path))
        results = run_lint(cfg, tmp_path)
        assert not [r for r in results if r.rule == "measured-limit-too-low"]
