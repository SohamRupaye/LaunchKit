"""Diff engine — re-generates in memory and diffs against files on disk."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.syntax import Syntax

from launchkit.core.config import (
    CIProvider,
    DeployTarget,
    LaunchKitConfig,
    ServiceType,
    load_and_validate,
)
from launchkit.core.engine import _build_dockerfile
from launchkit.generators.ci.github import generate_github_actions
from launchkit.generators.ci.gitlab import generate_gitlab_ci
from launchkit.generators.compose import generate_compose
from launchkit.generators.kubernetes.deployment import generate_deployment
from launchkit.generators.kubernetes.hpa import generate_hpa
from launchkit.generators.kubernetes.ingress import generate_ingress
from launchkit.generators.kubernetes.secrets import generate_secrets_hint
from launchkit.generators.kubernetes.service import generate_service
from launchkit.generators.nginx import generate_nginx_conf, generate_nginx_k8s
from launchkit.utils.fs import compute_diff
from launchkit.utils.printer import print_error, print_header, print_info, print_success


class DiffEngine:
    """Re-generates everything in memory and diffs against existing files."""

    def __init__(self, config_path: str, console: Console) -> None:
        self.config_path = config_path
        self.console = console

    def run(self) -> None:
        try:
            cfg = load_and_validate(self.config_path)
        except Exception as e:
            print_error(self.console, f"Failed to load config: {e}")
            raise SystemExit(1)

        root = Path(self.config_path).resolve().parent
        generated_files = self._collect_generated(cfg, root)

        total_diffs = 0
        for filepath, content in generated_files.items():
            diff = compute_diff(filepath, content)
            if diff:
                total_diffs += 1
                rel = str(filepath.relative_to(root))
                print_header(self.console, rel)
                syntax = Syntax(diff, "diff", theme="monokai", line_numbers=False)
                self.console.print(syntax)

        if total_diffs == 0:
            print_success(self.console, "All files are up to date — no changes needed.")
        else:
            print_info(self.console, f"{total_diffs} file(s) would change. Run `launchkit generate` to apply.")

    def _collect_generated(
        self, cfg: LaunchKitConfig, root: Path
    ) -> dict[Path, str]:
        files: dict[Path, str] = {}
        multi = len(cfg.services) > 1

        # Dockerfiles
        for name, service in cfg.services.items():
            docker_content = _build_dockerfile(name, service)
            if multi:
                files[root / "services" / name / "Dockerfile"] = docker_content
            else:
                files[root / "Dockerfile"] = docker_content

        # docker-compose
        if cfg.deploy.target in (DeployTarget.COMPOSE, DeployTarget.BOTH):
            files[root / "docker-compose.yml"] = generate_compose(cfg)

        # CI
        if cfg.ci.provider == CIProvider.GITHUB:
            files[root / ".github" / "workflows" / "ci.yml"] = generate_github_actions(cfg)
        elif cfg.ci.provider == CIProvider.GITLAB:
            files[root / ".gitlab-ci.yml"] = generate_gitlab_ci(cfg)

        # K8s
        if cfg.deploy.target in (DeployTarget.KUBERNETES, DeployTarget.BOTH):
            for name, service in cfg.services.items():
                files[root / "k8s" / name / "deployment.yaml"] = generate_deployment(name, service, cfg)
                if service.type == ServiceType.WEB and service.port:
                    files[root / "k8s" / name / "service.yaml"] = generate_service(name, service, cfg)
                if service.scale.max > 1:
                    files[root / "k8s" / name / "hpa.yaml"] = generate_hpa(name, service, cfg)
                # Secrets hints
                secrets = generate_secrets_hint(name, service, cfg, root)
                if secrets:
                    files[root / "k8s" / name / "secrets-hint.yaml"] = secrets
            if cfg.deploy.ingress.enabled:
                files[root / "k8s" / "ingress.yaml"] = generate_ingress(cfg)

        # Nginx
        if cfg.deploy.nginx.enabled:
            nginx_conf = generate_nginx_conf(cfg)
            if nginx_conf:
                files[root / "nginx" / "nginx.conf"] = nginx_conf
            if cfg.deploy.target in (DeployTarget.KUBERNETES, DeployTarget.BOTH):
                files[root / "k8s" / "nginx" / "nginx.yaml"] = generate_nginx_k8s(cfg)

        return files
