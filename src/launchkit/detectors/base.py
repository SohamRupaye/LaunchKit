"""Stack detectors — infer language, framework, and version from project files."""

from __future__ import annotations

import json
import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class DetectedService:
    name: str
    lang: str
    framework: str | None = None
    port: int | None = None
    service_type: str = "web"
    path: str = "."


class BaseDetector:
    def detect(self, root: Path, name: str) -> DetectedService | None:
        raise NotImplementedError


class PythonDetector(BaseDetector):
    FRAMEWORK_SIGNALS = {
        "fastapi": ("fastapi", 8000),
        "flask": ("flask", 5000),
        "django": ("django", 8000),
        "starlette": ("starlette", 8000),
    }

    def detect(self, root: Path, name: str) -> DetectedService | None:
        has_requirements = (root / "requirements.txt").exists()
        has_pyproject = (root / "pyproject.toml").exists()
        has_pipfile = (root / "Pipfile").exists()

        if not any([has_requirements, has_pyproject, has_pipfile]):
            return None

        framework, port = self._detect_framework(root)
        service_type = "worker" if self._looks_like_worker(root) else "web"

        return DetectedService(
            name=name,
            lang="python",
            framework=framework,
            port=port if service_type == "web" else None,
            service_type=service_type,
        )

    def _detect_framework(self, root: Path) -> tuple[str | None, int | None]:
        content = ""
        for fname in ["requirements.txt", "pyproject.toml"]:
            f = root / fname
            if f.exists():
                content += f.read_text().lower()

        for key, (framework, port) in self.FRAMEWORK_SIGNALS.items():
            if key in content:
                return framework, port

        return None, 8000

    def _looks_like_worker(self, root: Path) -> bool:
        signals = ["celery", "dramatiq", "arq", "rq", "worker"]
        for fname in ["requirements.txt", "pyproject.toml"]:
            f = root / fname
            if f.exists():
                content = f.read_text().lower()
                if any(s in content for s in signals):
                    return True
        return False


class NodeDetector(BaseDetector):
    FRAMEWORK_SIGNALS = {
        "next": ("nextjs", 3000),
        "express": ("express", 3000),
        "fastify": ("fastify", 3000),
        "koa": ("koa", 3000),
        "hono": ("hono", 3000),
        "nestjs": ("nestjs", 3000),
    }

    def detect(self, root: Path, name: str) -> DetectedService | None:
        pkg = root / "package.json"
        if not pkg.exists():
            return None

        try:
            data = json.loads(pkg.read_text())
        except json.JSONDecodeError:
            return None

        all_deps = {
            **data.get("dependencies", {}),
            **data.get("devDependencies", {}),
        }

        framework, port = None, 3000
        for key, (fw, p) in self.FRAMEWORK_SIGNALS.items():
            if key in all_deps or f"@{key}" in " ".join(all_deps.keys()):
                framework, port = fw, p
                break

        return DetectedService(name=name, lang="node", framework=framework, port=port)


class GoDetector(BaseDetector):
    def detect(self, root: Path, name: str) -> DetectedService | None:
        gomod = root / "go.mod"
        if not gomod.exists():
            return None

        framework = self._detect_framework(root)
        return DetectedService(name=name, lang="go", framework=framework, port=8080)

    def _detect_framework(self, root: Path) -> str | None:
        gomod = root / "go.mod"
        content = gomod.read_text()
        if "gin-gonic/gin" in content:
            return "gin"
        if "labstack/echo" in content:
            return "echo"
        if "gofiber/fiber" in content:
            return "fiber"
        if "go-chi/chi" in content:
            return "chi"
        return None


class JavaDetector(BaseDetector):
    FRAMEWORK_SIGNALS = {
        "spring-boot": ("spring-boot", 8080),
        "quarkus": ("quarkus", 8080),
        "micronaut": ("micronaut", 8080),
        "dropwizard": ("dropwizard", 8080),
        "vert.x": ("vertx", 8080),
    }

    def detect(self, root: Path, name: str) -> DetectedService | None:
        has_pom = (root / "pom.xml").exists()
        has_gradle = (root / "build.gradle").exists()
        has_gradle_kts = (root / "build.gradle.kts").exists()

        if not any([has_pom, has_gradle, has_gradle_kts]):
            return None

        framework, port = self._detect_framework(root)
        build_tool = "maven" if has_pom else "gradle"

        return DetectedService(
            name=name,
            lang="java",
            framework=framework or build_tool,
            port=port,
        )

    def _detect_framework(self, root: Path) -> tuple[str | None, int]:
        content = ""
        for fname in ["pom.xml", "build.gradle", "build.gradle.kts"]:
            f = root / fname
            if f.exists():
                content += f.read_text().lower()

        for key, (framework, port) in self.FRAMEWORK_SIGNALS.items():
            if key in content:
                return framework, port

        return None, 8080


class RustDetector(BaseDetector):
    FRAMEWORK_SIGNALS = {
        "actix-web": ("actix", 8080),
        "rocket": ("rocket", 8000),
        "axum": ("axum", 3000),
        "warp": ("warp", 3030),
        "tide": ("tide", 8080),
    }

    def detect(self, root: Path, name: str) -> DetectedService | None:
        cargo = root / "Cargo.toml"
        if not cargo.exists():
            return None

        framework, port = self._detect_framework(root)
        return DetectedService(name=name, lang="rust", framework=framework, port=port)

    def _detect_framework(self, root: Path) -> tuple[str | None, int]:
        cargo = root / "Cargo.toml"
        content = cargo.read_text().lower()

        for key, (framework, port) in self.FRAMEWORK_SIGNALS.items():
            if key in content:
                return framework, port

        return None, 8080


class RubyDetector(BaseDetector):
    FRAMEWORK_SIGNALS = {
        "rails": ("rails", 3000),
        "sinatra": ("sinatra", 4567),
        "hanami": ("hanami", 2300),
    }

    def detect(self, root: Path, name: str) -> DetectedService | None:
        gemfile = root / "Gemfile"
        if not gemfile.exists():
            return None

        framework, port = self._detect_framework(root)
        service_type = "worker" if self._looks_like_worker(root) else "web"

        return DetectedService(
            name=name,
            lang="ruby",
            framework=framework,
            port=port if service_type == "web" else None,
            service_type=service_type,
        )

    def _detect_framework(self, root: Path) -> tuple[str | None, int]:
        gemfile = root / "Gemfile"
        content = gemfile.read_text().lower()

        for key, (framework, port) in self.FRAMEWORK_SIGNALS.items():
            if key in content:
                return framework, port

        return None, 3000

    def _looks_like_worker(self, root: Path) -> bool:
        gemfile = root / "Gemfile"
        if gemfile.exists():
            content = gemfile.read_text().lower()
            if any(s in content for s in ["sidekiq", "resque", "good_job", "delayed_job"]):
                return True
        return False


class PHPDetector(BaseDetector):
    FRAMEWORK_SIGNALS = {
        "laravel": ("laravel", 8000),
        "symfony": ("symfony", 8000),
        "slim": ("slim", 8080),
        "lumen": ("lumen", 8000),
    }

    def detect(self, root: Path, name: str) -> DetectedService | None:
        composer = root / "composer.json"
        if not composer.exists():
            return None

        framework, port = self._detect_framework(root)
        return DetectedService(name=name, lang="php", framework=framework, port=port)

    def _detect_framework(self, root: Path) -> tuple[str | None, int]:
        composer = root / "composer.json"
        try:
            data = json.loads(composer.read_text())
            all_deps = {**data.get("require", {}), **data.get("require-dev", {})}
            deps_str = " ".join(all_deps.keys()).lower()

            for key, (framework, port) in self.FRAMEWORK_SIGNALS.items():
                if key in deps_str:
                    return framework, port
        except (json.JSONDecodeError, KeyError):
            pass

        return None, 8080


class DotNetDetector(BaseDetector):
    def detect(self, root: Path, name: str) -> DetectedService | None:
        # Look for .csproj or .fsproj files
        csproj = list(root.glob("*.csproj")) + list(root.glob("*.fsproj"))
        has_sln = any(root.glob("*.sln"))

        if not csproj and not has_sln:
            return None

        framework = self._detect_framework(root, csproj)
        return DetectedService(name=name, lang="dotnet", framework=framework, port=5000)

    def _detect_framework(self, root: Path, csproj_files: list[Path]) -> str | None:
        for f in csproj_files:
            content = f.read_text().lower()
            if "microsoft.aspnetcore" in content or "microsoft.net.sdk.web" in content:
                return "aspnet"
            if "microsoft.net.sdk.worker" in content:
                return "worker"
        return None


DETECTORS: list[BaseDetector] = [
    PythonDetector(),
    NodeDetector(),
    GoDetector(),
    JavaDetector(),
    RustDetector(),
    RubyDetector(),
    PHPDetector(),
    DotNetDetector(),
]


def detect_services(root: Path) -> list[DetectedService]:
    """
    Detect services in a project root.

    Handles both flat projects (single service) and monorepos
    (services/ or apps/ subdirectories).
    """
    detected: list[DetectedService] = []

    # Try monorepo layout first
    for parent_dir in ["services", "apps", "packages"]:
        parent = root / parent_dir
        if parent.is_dir():
            for service_dir in sorted(parent.iterdir()):
                if not service_dir.is_dir():
                    continue
                for detector in DETECTORS:
                    result = detector.detect(service_dir, service_dir.name)
                    if result:
                        result.path = str(service_dir.relative_to(root))
                        detected.append(result)
                        break

    # Fall back to flat layout
    if not detected:
        for detector in DETECTORS:
            result = detector.detect(root, root.name)
            if result:
                detected.append(result)
                break

    return detected

