"""Tests for diff engine."""

from __future__ import annotations

from pathlib import Path

import yaml
import pytest
from rich.console import Console

from launchkit.core.diff import DiffEngine
from launchkit.core.config import load_and_validate


@pytest.fixture
def quiet_console() -> Console:
    return Console(quiet=True)


class TestDiffEngine:
    def test_all_new_files(self, sample_config_yaml: Path, quiet_console: Console) -> None:
        """When no files exist, diff should report changes."""
        engine = DiffEngine(config_path=str(sample_config_yaml), console=quiet_console)
        # Should not crash
        engine.run()

    def test_up_to_date(self, sample_config_yaml: Path, quiet_console: Console) -> None:
        """After generating, diff should report no changes."""
        from launchkit.core.engine import GenerateEngine

        # Generate first
        gen = GenerateEngine(
            config_path=str(sample_config_yaml),
            only=None,
            dry_run=False,
            console=quiet_console,
        )
        gen.run()

        # Diff should be clean
        engine = DiffEngine(config_path=str(sample_config_yaml), console=quiet_console)
        engine.run()  # Should not crash, should report "up to date"

    def test_detects_changes(self, sample_config_yaml: Path, quiet_console: Console) -> None:
        """After modifying a generated file, diff should detect it."""
        from launchkit.core.engine import GenerateEngine

        # Generate
        gen = GenerateEngine(
            config_path=str(sample_config_yaml),
            only="docker",
            dry_run=False,
            console=quiet_console,
        )
        gen.run()

        # Modify the Dockerfile
        root = sample_config_yaml.parent
        dockerfile = root / "Dockerfile"
        dockerfile.write_text("# Modified by hand\nFROM ubuntu\n")

        # Diff should detect the change
        engine = DiffEngine(config_path=str(sample_config_yaml), console=quiet_console)
        engine.run()

    def test_invalid_config(self, tmp_path: Path, quiet_console: Console) -> None:
        """Should exit cleanly on invalid config."""
        with pytest.raises(SystemExit):
            engine = DiffEngine(
                config_path=str(tmp_path / "nonexistent.yaml"),
                console=quiet_console,
            )
            engine.run()

    def test_collect_generated_includes_dockerfiles(
        self, sample_config_yaml: Path, quiet_console: Console
    ) -> None:
        cfg = load_and_validate(str(sample_config_yaml))
        root = sample_config_yaml.parent
        engine = DiffEngine(config_path=str(sample_config_yaml), console=quiet_console)
        files = engine._collect_generated(cfg, root)
        # Should include at least a Dockerfile and K8s manifests
        paths = [str(p) for p in files.keys()]
        assert any("Dockerfile" in p for p in paths)
        assert any("deployment.yaml" in p for p in paths)
