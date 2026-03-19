"""Shared test fixtures for LaunchKit tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """Create a minimal temporary project directory."""
    return tmp_path


@pytest.fixture
def python_fastapi_project(tmp_path: Path) -> Path:
    """Create a minimal Python FastAPI project."""
    (tmp_path / "requirements.txt").write_text("fastapi>=0.110\nuvicorn>=0.27\n")
    (tmp_path / "main.py").write_text('from fastapi import FastAPI\napp = FastAPI()\n')
    return tmp_path


@pytest.fixture
def node_nextjs_project(tmp_path: Path) -> Path:
    """Create a minimal Next.js project."""
    pkg = {
        "name": "frontend",
        "dependencies": {"next": "^14.0.0", "react": "^18.2.0"},
    }
    (tmp_path / "package.json").write_text(json_dumps(pkg))
    return tmp_path


@pytest.fixture
def go_project(tmp_path: Path) -> Path:
    """Create a minimal Go project."""
    (tmp_path / "go.mod").write_text("module github.com/test/app\n\ngo 1.22\n")
    (tmp_path / "main.go").write_text("package main\n\nfunc main() {}\n")
    return tmp_path


@pytest.fixture
def monorepo_project(tmp_path: Path) -> Path:
    """Create a monorepo with Python API and Node frontend."""
    # Python API
    api_dir = tmp_path / "services" / "api"
    api_dir.mkdir(parents=True)
    (api_dir / "requirements.txt").write_text("fastapi>=0.110\nuvicorn>=0.27\n")

    # Node frontend
    frontend_dir = tmp_path / "services" / "frontend"
    frontend_dir.mkdir(parents=True)
    pkg = {"name": "frontend", "dependencies": {"next": "^14.0.0", "react": "^18.2.0"}}
    (frontend_dir / "package.json").write_text(json_dumps(pkg))

    return tmp_path


@pytest.fixture
def sample_config_dict() -> dict[str, Any]:
    """A minimal valid LaunchKit config as a dictionary."""
    return {
        "version": "1",
        "project": {
            "name": "testapp",
            "registry": "ghcr.io/test/testapp",
        },
        "services": {
            "api": {
                "lang": "python",
                "framework": "fastapi",
                "port": 8000,
                "healthcheck": "/health",
                "scale": {"min": 1, "max": 5, "cpu_threshold": 70},
            },
        },
        "ci": {
            "provider": "github",
            "affected_only": False,
            "steps": ["lint", "test", "build", "push"],
        },
        "deploy": {
            "target": "kubernetes",
            "namespace": "production",
        },
    }


@pytest.fixture
def sample_config_yaml(tmp_path: Path, sample_config_dict: dict) -> Path:
    """Write a sample launchkit.yaml and return the path."""
    config_path = tmp_path / "launchkit.yaml"
    config_path.write_text(yaml.dump(sample_config_dict, default_flow_style=False))
    return config_path


def json_dumps(obj: Any) -> str:
    """JSON serialize helper."""
    import json
    return json.dumps(obj, indent=2)
