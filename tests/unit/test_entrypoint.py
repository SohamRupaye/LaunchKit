"""Tests for real entrypoint detection."""

from __future__ import annotations

from pathlib import Path

from launchkit.detectors.entrypoint import detect_command


class TestPythonEntrypoint:
    def test_fastapi_nonstandard_names(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n")
        (tmp_path / "server.py").write_text("from fastapi import FastAPI\napi = FastAPI()\n")
        cmd = detect_command(tmp_path, "python", "fastapi", "web", 8000)
        assert cmd == ["uvicorn", "server:api", "--host", "0.0.0.0", "--port", "8000"]

    def test_flask_gunicorn(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("flask\ngunicorn\n")
        (tmp_path / "wsgi.py").write_text("from flask import Flask\nsrv = Flask(__name__)\n")
        cmd = detect_command(tmp_path, "python", "flask", "web", 5000)
        assert cmd == ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "wsgi:srv"]

    def test_django_package_detection(self, tmp_path: Path) -> None:
        pkg = tmp_path / "mysite"
        pkg.mkdir()
        (tmp_path / "requirements.txt").write_text("django\ngunicorn\n")
        (tmp_path / "manage.py").write_text("")
        (pkg / "wsgi.py").write_text("application = None\n")
        (pkg / "settings.py").write_text("DEBUG = True\n")
        cmd = detect_command(tmp_path, "python", "django", "web", 8000)
        assert cmd == [
            "gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4",
            "mysite.wsgi:application",
        ]

    def test_celery_worker(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("celery\n")
        (tmp_path / "tasks.py").write_text("from celery import Celery\napp = Celery('t')\n")
        cmd = detect_command(tmp_path, "python", None, "worker", None)
        assert cmd == ["celery", "-A", "tasks", "worker", "--loglevel=info"]

    def test_worker_script_fallback(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("requests\n")
        (tmp_path / "worker.py").write_text("print('working')\n")
        cmd = detect_command(tmp_path, "python", None, "worker", None)
        assert cmd == ["python", "worker.py"]

    def test_nested_module_path(self, tmp_path: Path) -> None:
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        (tmp_path / "requirements.txt").write_text("fastapi\n")
        (app_dir / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
        cmd = detect_command(tmp_path, "python", "fastapi", "web", 8080)
        assert cmd == ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

    def test_no_app_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("requests\n")
        # No recognizable app object or script → None (template falls back).
        assert detect_command(tmp_path, "python", None, "web", 8000) is None


class TestNodeEntrypoint:
    def test_start_script_is_authoritative(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            '{"name":"x","scripts":{"start":"node dist/main.js"}}'
        )
        cmd = detect_command(tmp_path, "node", "express", "web", 3000)
        assert cmd == ["npm", "start"]

    def test_main_field(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"name":"x","main":"lib/entry.js"}')
        cmd = detect_command(tmp_path, "node", None, "web", 3000)
        assert cmd == ["node", "lib/entry.js"]

    def test_server_js_fallback(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"name":"x"}')
        (tmp_path / "server.js").write_text("console.log(1)\n")
        cmd = detect_command(tmp_path, "node", None, "web", 3000)
        assert cmd == ["node", "server.js"]

    def test_nextjs_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"name":"x","scripts":{"start":"next start"}}')
        # Next.js uses its dedicated standalone template — no command override.
        assert detect_command(tmp_path, "node", "nextjs", "web", 3000) is None


class TestProcfile:
    def test_procfile_web_is_authoritative(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("flask\n")
        (tmp_path / "app.py").write_text("from flask import Flask\napp=Flask(__name__)\n")
        (tmp_path / "Procfile").write_text("web: gunicorn app:app --workers 2\n")
        cmd = detect_command(tmp_path, "python", "flask", "web", 5000)
        assert cmd == ["gunicorn", "app:app", "--workers", "2"]

    def test_procfile_worker_process(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("celery\n")
        (tmp_path / "Procfile").write_text(
            "web: gunicorn app:app\nworker: celery -A tasks worker\n"
        )
        cmd = detect_command(tmp_path, "python", None, "worker", None)
        assert cmd == ["celery", "-A", "tasks", "worker"]
