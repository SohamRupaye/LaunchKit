"""Integration tests for the Phase 0 correctness fixes.

These go beyond substring assertions: they parse the generated YAML structure
and assert on the actual build context / paths, and they exercise the
init → generate round-trip that used to crash on unsupported CI providers.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
import pytest
from rich.console import Console

from launchkit.core.engine import GenerateEngine, InitEngine


@pytest.fixture
def quiet_console() -> Console:
    return Console(quiet=True)


def _build_step(ci: dict, job_name: str) -> dict:
    """Return the docker build-push step from a GitHub Actions job."""
    steps = ci["jobs"][job_name]["steps"]
    for step in steps:
        if step.get("uses", "").startswith("docker/build-push-action"):
            return step
    raise AssertionError(f"No build-push step found in job {job_name}")


class TestFlatRepoCIContext:
    def test_flat_repo_build_context_is_root(
        self, python_fastapi_project: Path, quiet_console: Console
    ) -> None:
        # Give it a tests/ dir so the pipeline includes a test step too.
        (python_fastapi_project / "tests").mkdir()
        (python_fastapi_project / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")

        InitEngine(root=str(python_fastapi_project), force=False, console=quiet_console).run()
        GenerateEngine(
            config_path=str(python_fastapi_project / "launchkit.yaml"),
            only="ci", dry_run=False, console=quiet_console,
        ).run()

        ci_path = python_fastapi_project / ".github" / "workflows" / "ci.yml"
        ci = yaml.safe_load(ci_path.read_text())

        # There is exactly one build job for the single service.
        build_jobs = [j for j in ci["jobs"] if j.startswith("build-")]
        assert len(build_jobs) == 1
        build = _build_step(ci, build_jobs[0])

        # The whole point: context must be the repo root, not services/<name>.
        assert build["with"]["context"] == "."

        # And no test/build step should reference a services/ path that doesn't exist.
        raw = ci_path.read_text()
        assert "services/" not in raw

    def test_monorepo_build_context_is_service_dir(
        self, monorepo_project: Path, quiet_console: Console
    ) -> None:
        InitEngine(root=str(monorepo_project), force=False, console=quiet_console).run()
        GenerateEngine(
            config_path=str(monorepo_project / "launchkit.yaml"),
            only="ci", dry_run=False, console=quiet_console,
        ).run()

        ci = yaml.safe_load((monorepo_project / ".github" / "workflows" / "ci.yml").read_text())
        api_build = _build_step(ci, "build-api")
        assert api_build["with"]["context"] == "services/api"


class TestUnsupportedCIProviderClamp:
    def test_jenkins_repo_init_generate_roundtrip(
        self, python_fastapi_project: Path, quiet_console: Console
    ) -> None:
        # A Jenkinsfile makes detect_ci_provider return "jenkins", which the
        # CIProvider enum rejects — this used to crash on the next generate.
        (python_fastapi_project / "Jenkinsfile").write_text("pipeline {}\n")

        InitEngine(root=str(python_fastapi_project), force=False, console=quiet_console).run()

        cfg = yaml.safe_load((python_fastapi_project / "launchkit.yaml").read_text())
        # Clamped to a supported provider.
        assert cfg["ci"]["provider"] == "github"

        # The round-trip must not raise.
        GenerateEngine(
            config_path=str(python_fastapi_project / "launchkit.yaml"),
            only=None, dry_run=False, console=quiet_console,
        ).run()
        assert (python_fastapi_project / ".github" / "workflows" / "ci.yml").exists()


class TestPythonDepManagerDockerfile:
    def _dockerfile_for(self, project: Path, console: Console) -> str:
        InitEngine(root=str(project), force=False, console=console).run()
        GenerateEngine(
            config_path=str(project / "launchkit.yaml"),
            only="docker", dry_run=False, console=console,
        ).run()
        return (project / "Dockerfile").read_text()

    def test_requirements_project(self, python_fastapi_project: Path, quiet_console: Console) -> None:
        df = self._dockerfile_for(python_fastapi_project, quiet_console)
        assert "COPY requirements.txt" in df
        assert "pip install --no-cache-dir -r requirements.txt" in df

    def test_pyproject_only_project(self, tmp_path: Path, quiet_console: Console) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = \"svc\"\nversion = \"0.1.0\"\ndependencies = [\"fastapi\"]\n"
        )
        (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")

        df = self._dockerfile_for(tmp_path, quiet_console)
        assert "COPY pyproject.toml" in df
        # Must NOT try to copy a requirements.txt that doesn't exist.
        assert "COPY requirements.txt" not in df

    def test_pipfile_only_project(self, tmp_path: Path, quiet_console: Console) -> None:
        (tmp_path / "Pipfile").write_text(
            "[packages]\nfastapi = \"*\"\n"
        )
        (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")

        df = self._dockerfile_for(tmp_path, quiet_console)
        assert "COPY Pipfile" in df
        assert "pipenv install" in df
        assert "COPY requirements.txt" not in df
