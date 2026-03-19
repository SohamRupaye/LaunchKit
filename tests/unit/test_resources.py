"""Tests for resource profiler — inferred resource limits and scaling."""

from __future__ import annotations

from pathlib import Path

from launchkit.detectors.resources import (
    PROFILES,
    ResourceProfile,
    infer_resource_profile,
    _scan_dependencies,
)


class TestResourceProfiles:
    def test_profiles_exist(self) -> None:
        assert "lightweight-api" in PROFILES
        assert "standard-api" in PROFILES
        assert "heavy-api" in PROFILES
        assert "worker" in PROFILES
        assert "ml-worker" in PROFILES
        assert "data-processor" in PROFILES
        assert "frontend" in PROFILES

    def test_ml_worker_has_memory_threshold(self) -> None:
        assert PROFILES["ml-worker"].memory_threshold is not None

    def test_lightweight_has_lower_limits(self) -> None:
        light = int(PROFILES["lightweight-api"].cpu_limit.replace("m", ""))
        heavy = int(PROFILES["heavy-api"].cpu_limit.replace("m", ""))
        assert light < heavy


class TestInferResourceProfile:
    def test_go_api_lightweight(self) -> None:
        profile = infer_resource_profile("go", None, "web")
        assert profile.profile_name == "lightweight-api"

    def test_python_api_standard(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("fastapi>=0.110\nuvicorn>=0.27\n")
        profile = infer_resource_profile("python", "fastapi", "web", tmp_path)
        assert profile.profile_name == "standard-api"

    def test_python_ml_worker(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("celery>=5.0\ntorch>=2.0\ntransformers\n")
        profile = infer_resource_profile("python", None, "worker", tmp_path)
        assert profile.profile_name == "ml-worker"
        assert profile.memory_threshold is not None

    def test_python_data_worker(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("celery>=5.0\npandas>=2.0\nnumpy\n")
        profile = infer_resource_profile("python", None, "worker", tmp_path)
        assert profile.profile_name == "data-processor"

    def test_plain_worker(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("celery>=5.0\nredis>=5\n")
        profile = infer_resource_profile("python", None, "worker", tmp_path)
        assert profile.profile_name == "worker"

    def test_nextjs_frontend(self) -> None:
        profile = infer_resource_profile("node", "nextjs", "web")
        assert profile.profile_name == "frontend"

    def test_react_frontend(self) -> None:
        profile = infer_resource_profile("node", "react", "web")
        assert profile.profile_name == "frontend"

    def test_python_heavy_api(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("fastapi\ntensorflow>=2.0\npillow\n")
        profile = infer_resource_profile("python", "fastapi", "web", tmp_path)
        assert profile.profile_name == "heavy-api"

    def test_node_api_standard(self) -> None:
        profile = infer_resource_profile("node", "express", "web")
        assert profile.profile_name == "standard-api"

    def test_no_path_defaults(self) -> None:
        profile = infer_resource_profile("python", "fastapi", "web")
        assert profile.profile_name == "standard-api"


class TestScanDependencies:
    def test_python_requirements(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text(
            "fastapi>=0.110\n"
            "tensorflow>=2.0\n"
            "# comment line\n"
            "\n"
            "pandas>=2.0\n"
        )
        deps = _scan_dependencies(tmp_path, "python")
        assert "fastapi" in deps
        assert "tensorflow" in deps
        assert "pandas" in deps

    def test_python_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\ndependencies = ["torch>=2.0"]\n'
        )
        deps = _scan_dependencies(tmp_path, "python")
        assert "torch" in deps

    def test_node_package_json(self, tmp_path: Path) -> None:
        import json
        pkg = {"dependencies": {"express": "^4.18", "@tensorflow/tfjs": "^4.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg))
        deps = _scan_dependencies(tmp_path, "node")
        assert "express" in deps
        assert "@tensorflow/tfjs" in deps

    def test_no_files(self, tmp_path: Path) -> None:
        deps = _scan_dependencies(tmp_path, "python")
        assert len(deps) == 0

    def test_handles_extras(self, tmp_path: Path) -> None:
        """Should strip extras like [ml] from package names."""
        (tmp_path / "requirements.txt").write_text("scikit-learn[all]>=1.3\n")
        deps = _scan_dependencies(tmp_path, "python")
        assert "scikit-learn" in deps
