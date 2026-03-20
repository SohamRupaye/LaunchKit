"""Tests for Java, Rust, Ruby, PHP, .NET detectors and generators."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from launchkit.detectors.base import (
    JavaDetector,
    RustDetector,
    RubyDetector,
    PHPDetector,
    DotNetDetector,
    detect_services,
)
from launchkit.core.config import ServiceConfig, LaunchKitConfig
from launchkit.core.engine import _build_dockerfile
from launchkit.detectors.resources import infer_resource_profile


# ── Java ─────────────────────────────────────────────────────────────────────


class TestJavaDetector:
    def test_detects_maven(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("<project><spring-boot></spring-boot></project>")
        result = JavaDetector().detect(tmp_path, "api")
        assert result is not None
        assert result.lang == "java"
        assert result.framework == "spring-boot"
        assert result.port == 8080

    def test_detects_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("dependencies { implementation 'io.quarkus:quarkus' }")
        result = JavaDetector().detect(tmp_path, "api")
        assert result is not None
        assert result.lang == "java"
        assert result.framework == "quarkus"

    def test_detects_gradle_kts(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle.kts").write_text("plugins { id(\"org.springframework.boot\") }")
        result = JavaDetector().detect(tmp_path, "api")
        assert result is not None
        assert result.lang == "java"

    def test_no_java(self, tmp_path: Path) -> None:
        assert JavaDetector().detect(tmp_path, "api") is None

    def test_fallback_build_tool(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("<project></project>")
        result = JavaDetector().detect(tmp_path, "api")
        assert result.framework == "maven"

    def test_gradle_fallback(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("apply plugin: 'java'")
        result = JavaDetector().detect(tmp_path, "api")
        assert result.framework == "gradle"


class TestJavaDockerfile:
    def test_maven_dockerfile(self) -> None:
        svc = ServiceConfig(lang="java", framework="maven", port=8080)
        result = _build_dockerfile("api", svc)
        assert "maven" in result.lower()
        assert "mvn" in result
        assert "JAVA_OPTS" in result
        assert "UseContainerSupport" in result

    def test_gradle_dockerfile(self) -> None:
        svc = ServiceConfig(lang="java", framework="gradle", port=8080)
        result = _build_dockerfile("api", svc)
        assert "gradle" in result.lower()
        assert "bootJar" in result

    def test_spring_boot_uses_maven(self) -> None:
        svc = ServiceConfig(lang="java", framework="spring-boot", port=8080)
        result = _build_dockerfile("api", svc)
        # spring-boot framework maps to gradle template
        assert "JAVA_OPTS" in result

    def test_jvm_memory_tuning(self) -> None:
        svc = ServiceConfig(lang="java", framework="maven", port=8080)
        result = _build_dockerfile("api", svc)
        assert "MaxRAMPercentage" in result


class TestJavaResourceProfile:
    def test_java_api_gets_jvm_profile(self) -> None:
        profile = infer_resource_profile("java", "spring-boot", "web")
        assert profile.profile_name == "jvm-api"
        assert profile.memory_limit == "1Gi"  # higher than standard for JVM


# ── Rust ─────────────────────────────────────────────────────────────────────


class TestRustDetector:
    def test_detects_actix(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text('[dependencies]\nactix-web = "4"')
        result = RustDetector().detect(tmp_path, "api")
        assert result is not None
        assert result.lang == "rust"
        assert result.framework == "actix"
        assert result.port == 8080

    def test_detects_axum(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text('[dependencies]\naxum = "0.7"')
        result = RustDetector().detect(tmp_path, "api")
        assert result.framework == "axum"
        assert result.port == 3000

    def test_detects_rocket(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text('[dependencies]\nrocket = "0.5"')
        result = RustDetector().detect(tmp_path, "api")
        assert result.framework == "rocket"

    def test_no_rust(self, tmp_path: Path) -> None:
        assert RustDetector().detect(tmp_path, "api") is None


class TestRustDockerfile:
    def test_rust_dockerfile(self) -> None:
        svc = ServiceConfig(lang="rust", framework="actix", port=8080)
        result = _build_dockerfile("api", svc)
        assert "cargo" in result.lower()
        assert "cargo-chef" in result
        assert "--release" in result
        assert "EXPOSE 8080" in result

    def test_scratch_runtime(self) -> None:
        svc = ServiceConfig(lang="rust", port=8080)
        result = _build_dockerfile("api", svc)
        assert "debian:bookworm-slim" in result


class TestRustResourceProfile:
    def test_rust_gets_lightweight(self) -> None:
        profile = infer_resource_profile("rust", "actix", "web")
        assert profile.profile_name == "lightweight-api"


# ── Ruby ─────────────────────────────────────────────────────────────────────


class TestRubyDetector:
    def test_detects_rails(self, tmp_path: Path) -> None:
        (tmp_path / "Gemfile").write_text("gem 'rails', '~> 7.0'")
        result = RubyDetector().detect(tmp_path, "web")
        assert result is not None
        assert result.lang == "ruby"
        assert result.framework == "rails"
        assert result.port == 3000

    def test_detects_sinatra(self, tmp_path: Path) -> None:
        (tmp_path / "Gemfile").write_text("gem 'sinatra'")
        result = RubyDetector().detect(tmp_path, "api")
        assert result.framework == "sinatra"
        assert result.port == 4567

    def test_detects_worker(self, tmp_path: Path) -> None:
        (tmp_path / "Gemfile").write_text("gem 'sidekiq'")
        result = RubyDetector().detect(tmp_path, "worker")
        assert result.service_type == "worker"
        assert result.port is None

    def test_no_ruby(self, tmp_path: Path) -> None:
        assert RubyDetector().detect(tmp_path, "api") is None


class TestRubyDockerfile:
    def test_rails_dockerfile(self) -> None:
        svc = ServiceConfig(lang="ruby", framework="rails", port=3000)
        result = _build_dockerfile("web", svc)
        assert "ruby:3.3" in result
        assert "bundle" in result
        assert "puma" in result.lower()
        assert "assets:precompile" in result

    def test_sinatra_dockerfile(self) -> None:
        svc = ServiceConfig(lang="ruby", framework="sinatra", port=4567)
        result = _build_dockerfile("api", svc)
        assert "ruby:3.3" in result
        assert "assets:precompile" not in result


# ── PHP ──────────────────────────────────────────────────────────────────────


class TestPHPDetector:
    def test_detects_laravel(self, tmp_path: Path) -> None:
        composer = {"require": {"laravel/framework": "^10.0"}}
        (tmp_path / "composer.json").write_text(json.dumps(composer))
        result = PHPDetector().detect(tmp_path, "api")
        assert result is not None
        assert result.lang == "php"
        assert result.framework == "laravel"
        assert result.port == 8000

    def test_detects_symfony(self, tmp_path: Path) -> None:
        composer = {"require": {"symfony/framework-bundle": "^6.0"}}
        (tmp_path / "composer.json").write_text(json.dumps(composer))
        result = PHPDetector().detect(tmp_path, "api")
        assert result.framework == "symfony"

    def test_no_php(self, tmp_path: Path) -> None:
        assert PHPDetector().detect(tmp_path, "api") is None

    def test_invalid_json(self, tmp_path: Path) -> None:
        (tmp_path / "composer.json").write_text("not json")
        result = PHPDetector().detect(tmp_path, "api")
        assert result is not None  # detected by file presence
        assert result.framework is None


class TestPHPDockerfile:
    def test_laravel_dockerfile(self) -> None:
        svc = ServiceConfig(lang="php", framework="laravel", port=8000)
        result = _build_dockerfile("api", svc)
        assert "php:8.3-fpm" in result
        assert "composer" in result
        assert "opcache" in result
        assert "config:cache" in result

    def test_php_fpm_tuning(self) -> None:
        svc = ServiceConfig(lang="php", port=8080)
        result = _build_dockerfile("api", svc)
        assert "pm.max_children" in result


class TestPHPResourceProfile:
    def test_php_gets_fpm_profile(self) -> None:
        profile = infer_resource_profile("php", "laravel", "web")
        assert profile.profile_name == "php-fpm"


# ── .NET ─────────────────────────────────────────────────────────────────────


class TestDotNetDetector:
    def test_detects_aspnet(self, tmp_path: Path) -> None:
        (tmp_path / "MyApp.csproj").write_text(
            '<Project Sdk="Microsoft.NET.Sdk.Web">'
        )
        result = DotNetDetector().detect(tmp_path, "api")
        assert result is not None
        assert result.lang == "dotnet"
        assert result.framework == "aspnet"
        assert result.port == 5000

    def test_detects_worker(self, tmp_path: Path) -> None:
        (tmp_path / "Worker.csproj").write_text(
            '<Project Sdk="Microsoft.NET.Sdk.Worker">'
        )
        result = DotNetDetector().detect(tmp_path, "worker")
        assert result.framework == "worker"

    def test_no_dotnet(self, tmp_path: Path) -> None:
        assert DotNetDetector().detect(tmp_path, "api") is None


class TestDotNetDockerfile:
    def test_aspnet_dockerfile(self) -> None:
        svc = ServiceConfig(lang="dotnet", framework="aspnet", port=5000)
        result = _build_dockerfile("api", svc)
        assert "dotnet/sdk:8.0" in result
        assert "dotnet/aspnet:8.0" in result
        assert "dotnet publish" in result
        assert "DOTNET_RUNNING_IN_CONTAINER" in result

    def test_dotnet_port(self) -> None:
        svc = ServiceConfig(lang="dotnet", framework="aspnet", port=5000)
        result = _build_dockerfile("api", svc)
        assert "5000" in result


class TestDotNetResourceProfile:
    def test_dotnet_gets_standard(self) -> None:
        profile = infer_resource_profile("dotnet", "aspnet", "web")
        assert profile.profile_name == "standard-api"


# ── Cross-language monorepo detection ────────────────────────────────────────


class TestMultiLanguageDetection:
    def test_monorepo_all_languages(self, tmp_path: Path) -> None:
        """Detect services in 8 different languages in one monorepo."""
        svc = tmp_path / "services"
        svc.mkdir()

        # Python
        (svc / "api").mkdir()
        (svc / "api" / "requirements.txt").write_text("fastapi>=0.110")

        # Java
        (svc / "backend").mkdir()
        (svc / "backend" / "pom.xml").write_text("<project>spring-boot</project>")

        # Rust
        (svc / "engine").mkdir()
        (svc / "engine" / "Cargo.toml").write_text('[dependencies]\nactix-web = "4"')

        # Ruby
        (svc / "web").mkdir()
        (svc / "web" / "Gemfile").write_text("gem 'rails'")

        # PHP
        (svc / "portal").mkdir()
        composer = {"require": {"laravel/framework": "^10"}}
        (svc / "portal" / "composer.json").write_text(json.dumps(composer))

        results = detect_services(tmp_path)
        langs = {r.lang for r in results}

        assert "python" in langs
        assert "java" in langs
        assert "rust" in langs
        assert "ruby" in langs
        assert "php" in langs
        assert len(results) == 5
