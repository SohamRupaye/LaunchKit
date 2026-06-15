"""Entrypoint detector — find the real start command instead of guessing it.

Hardcoded entrypoints (`main:app`, `app:app`, `config.wsgi`, `worker.py`) are the
single biggest source of Dockerfiles that build but won't boot. This module scans
the actual source to recover the correct command, and returns None when it can't
be confident — in which case the template falls back to its heuristic and the
Phase 3 smoke test surfaces any mismatch loudly.
"""

from __future__ import annotations

import json
import re
import shlex
from collections.abc import Iterator
from pathlib import Path

# Directories that never contain the app entrypoint — skip for speed and accuracy.
_SKIP_DIRS = {
    ".venv", "venv", "env", "node_modules", "__pycache__", ".git",
    "tests", "test", "migrations", "dist", "build", ".mypy_cache", ".pytest_cache",
}

_PY_APP_RE = re.compile(r"^\s*(\w+)\s*=\s*(FastAPI|Flask|Starlette)\s*\(", re.MULTILINE)
_CELERY_RE = re.compile(r"^\s*(\w+)\s*=\s*Celery\s*\(", re.MULTILINE)


def detect_command(
    service_dir: Path,
    lang: str,
    framework: str | None,
    service_type: str,
    port: int | None,
) -> list[str] | None:
    """
    Return the detected start command as an exec-form arg list, or None when it
    can't be determined confidently.
    """
    # Procfile is authoritative across every language.
    proc = _from_procfile(service_dir, service_type)
    if proc:
        return proc

    if lang == "python":
        return _python_command(service_dir, framework, service_type, port)
    if lang == "node":
        return _node_command(service_dir, framework, service_type)
    return None


# ── Procfile ────────────────────────────────────────────────────────────────


def _from_procfile(service_dir: Path, service_type: str) -> list[str] | None:
    procfile = service_dir / "Procfile"
    if not procfile.exists():
        return None
    try:
        lines = procfile.read_text().splitlines()
    except OSError:
        return None

    processes: dict[str, str] = {}
    for line in lines:
        if ":" not in line or line.strip().startswith("#"):
            continue
        name, _, cmd = line.partition(":")
        processes[name.strip()] = cmd.strip()

    # Match the process type to the service type; fall back sensibly.
    if service_type == "worker":
        for key in ("worker", "celery"):
            if key in processes:
                return _split(processes[key])
    if "web" in processes:
        return _split(processes["web"])
    if processes:
        return _split(next(iter(processes.values())))
    return None


# ── Python ────────────────────────────────────────────────────────────────────


def _python_command(
    service_dir: Path,
    framework: str | None,
    service_type: str,
    port: int | None,
) -> list[str] | None:
    port = port or 8000

    # Django: locate the package that owns wsgi.py + settings.py.
    django_pkg = _find_django_package(service_dir)
    if framework == "django" or django_pkg:
        if django_pkg:
            return [
                "gunicorn", "--bind", f"0.0.0.0:{port}", "--workers", "4",
                f"{django_pkg}.wsgi:application",
            ]

    # Worker: prefer a detected Celery app.
    if service_type == "worker":
        celery_mod = _find_module_with(service_dir, _CELERY_RE)
        if celery_mod:
            return ["celery", "-A", celery_mod, "worker", "--loglevel=info"]
        for candidate in ("worker.py", "main.py", "__main__.py", "run.py"):
            if (service_dir / candidate).exists():
                return ["python", candidate]
        return None

    # Web: find the ASGI/WSGI app object (module:callable).
    target = _find_python_app(service_dir)
    if target:
        module, var, kind = target
        if kind in ("FastAPI", "Starlette"):
            return ["uvicorn", f"{module}:{var}", "--host", "0.0.0.0", "--port", str(port)]
        if kind == "Flask":
            return [
                "gunicorn", "--bind", f"0.0.0.0:{port}", "--workers", "4",
                f"{module}:{var}",
            ]

    # Last-resort script fallback.
    for candidate in ("main.py", "app.py", "server.py"):
        if (service_dir / candidate).exists():
            return ["python", candidate]
    return None


def _find_python_app(service_dir: Path) -> tuple[str, str, str] | None:
    """Return (module, variable, framework_kind) for the first app object found."""
    for py_file in _iter_source_files(service_dir, ".py"):
        try:
            content = py_file.read_text()
        except OSError:
            continue
        m = _PY_APP_RE.search(content)
        if m:
            var, kind = m.group(1), m.group(2)
            return _module_path(service_dir, py_file), var, kind
    return None


def _find_module_with(service_dir: Path, pattern: re.Pattern[str]) -> str | None:
    for py_file in _iter_source_files(service_dir, ".py"):
        try:
            content = py_file.read_text()
        except OSError:
            continue
        if pattern.search(content):
            return _module_path(service_dir, py_file)
    return None


def _find_django_package(service_dir: Path) -> str | None:
    """Find the package containing both wsgi.py and settings.py (the Django project)."""
    for wsgi in _iter_source_files(service_dir, ".py"):
        if wsgi.name != "wsgi.py":
            continue
        pkg_dir = wsgi.parent
        if (pkg_dir / "settings.py").exists() or (pkg_dir / "settings").is_dir():
            return _package_path(service_dir, pkg_dir)
    return None


def _module_path(service_dir: Path, py_file: Path) -> str:
    """Convert a .py file path to a dotted module path relative to service_dir."""
    rel = py_file.relative_to(service_dir).with_suffix("")
    return ".".join(rel.parts)


def _package_path(service_dir: Path, pkg_dir: Path) -> str:
    rel = pkg_dir.relative_to(service_dir)
    return ".".join(rel.parts) if rel.parts else pkg_dir.name


# ── Node ────────────────────────────────────────────────────────────────────


def _node_command(
    service_dir: Path,
    framework: str | None,
    service_type: str,
) -> list[str] | None:
    # Next.js has a dedicated multi-stage template that runs the standalone
    # server.js output — its command must not be overridden with `npm start`.
    if framework == "nextjs":
        return None

    pkg = service_dir / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text())
        except (OSError, ValueError):
            data = {}
        scripts = data.get("scripts", {})
        # A real start script is authoritative (covers next start, nest start, etc.).
        if isinstance(scripts, dict) and scripts.get("start"):
            return ["npm", "start"]
        main = data.get("main")
        if isinstance(main, str) and main:
            return ["node", main]

    for candidate in ("server.js", "index.js", "app.js", "src/index.js", "src/server.js"):
        if (service_dir / candidate).exists():
            return ["node", candidate]
    return None


# ── Helpers ────────────────────────────────────────────────────────────────


def _iter_source_files(
    service_dir: Path, suffix: str, max_depth: int = 3
) -> Iterator[Path]:
    """Yield source files up to max_depth, skipping vendored/irrelevant dirs."""
    if not service_dir.is_dir():
        return
    base_depth = len(service_dir.parts)
    for path in sorted(service_dir.rglob(f"*{suffix}")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if len(path.parts) - base_depth > max_depth:
            continue
        yield path


def _split(cmd: str) -> list[str]:
    """Split a shell command string into an arg list, tolerating oddities."""
    try:
        parts = shlex.split(cmd)
        return parts if parts else [cmd]
    except ValueError:
        return cmd.split()
