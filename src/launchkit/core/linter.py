"""Linter — catches real deployment problems before they hit production."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml

from launchkit.core.config import LaunchKitConfig, ServiceConfig, ServiceType


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class LintResult:
    rule: str
    severity: Severity
    service: str | None
    message: str


def run_lint(cfg: LaunchKitConfig, root: Path | None = None) -> list[LintResult]:
    """
    Run all lint rules against a LaunchKit config.

    Returns a list of LintResult — empty list means all clear.
    """
    results: list[LintResult] = []

    for name, service in cfg.services.items():
        results += _check_no_resource_limits(name, service)
        results += _check_latest_tag(name, service, cfg)
        results += _check_no_healthcheck(name, service)
        results += _check_measured_limit_too_low(name, service)
        results += _check_memory_mismatch(name, service)
        results += _check_worker_has_probe(name, service)
        results += _check_single_replica_production(name, service, cfg)
        results += _check_cpu_scaling_io(name, service)
        results += _check_missing_env_file(name, service, root)

    # Project-level checks
    results += _check_no_nginx(cfg)
    results += _check_no_environments(cfg)

    return results


# ── Per-service rules ────────────────────────────────────────────────────────


def _check_no_resource_limits(name: str, svc: ServiceConfig) -> list[LintResult]:
    """All K8s services should have explicit resource limits."""
    res = svc.resources
    if res.cpu_limit == "500m" and res.memory_limit == "512Mi" and res.profile is None:
        return [LintResult(
            rule="no-resource-limits",
            severity=Severity.WARNING,
            service=name,
            message="Using default resource limits (500m CPU / 512Mi). "
                    "Run `launchkit upgrade` to get inferred limits based on your dependencies.",
        )]
    return []


def _check_latest_tag(name: str, svc: ServiceConfig, cfg: LaunchKitConfig) -> list[LintResult]:
    """Image tags should never be 'latest' in production."""
    # Check if the registry reference would use :latest by default
    # This is always the case for generated manifests, so flag it as a reminder
    if cfg.deploy.namespace == "production":
        return [LintResult(
            rule="latest-tag",
            severity=Severity.WARNING,
            service=name,
            message="Generated manifests use ':latest' tag. "
                    "For production, pin tags to commit SHA or semver in your CI pipeline.",
        )]
    return []


def _check_no_healthcheck(name: str, svc: ServiceConfig) -> list[LintResult]:
    """Web services should have a health endpoint for readiness probes."""
    if svc.type == ServiceType.WEB and not svc.healthcheck:
        return [LintResult(
            rule="no-healthcheck",
            severity=Severity.ERROR,
            service=name,
            message="No healthcheck endpoint defined. "
                    "K8s readiness probe will fail silently — pods may receive traffic before the app is ready. "
                    "Add `healthcheck: /health` to your service config.",
        )]
    return []


def _check_measured_limit_too_low(name: str, svc: ServiceConfig) -> list[LintResult]:
    """If a service was measured, its memory_limit must clear the observed peak."""
    peak = svc.resources.measured_peak_mi
    if peak is None:
        return []
    limit_mi = _parse_memory_mi(svc.resources.memory_limit)
    if limit_mi and limit_mi < peak:
        return [LintResult(
            rule="measured-limit-too-low",
            severity=Severity.ERROR,
            service=name,
            message=f"memory_limit is {svc.resources.memory_limit} but `launchkit measure` "
                    f"observed a peak of {peak}Mi. This container will OOMKill on startup — "
                    f"raise memory_limit above {peak}Mi.",
        )]
    return []


def _check_memory_mismatch(name: str, svc: ServiceConfig) -> list[LintResult]:
    """If memory request is high, HPA should include memory metrics."""
    mem = svc.resources.memory_request
    # Parse memory value (simple: just check if >= 512Mi / 1Gi)
    mem_mi = _parse_memory_mi(mem)
    if mem_mi >= 512 and svc.scale.memory_threshold is None and svc.scale.max > 1:
        return [LintResult(
            rule="memory-mismatch",
            severity=Severity.WARNING,
            service=name,
            message=f"Memory request is {mem} but HPA has no memory metric. "
                    f"This service may OOMKill under burst load without memory-based scaling. "
                    f"Add `memory_threshold: 80` to scale config.",
        )]
    return []


def _check_worker_has_probe(name: str, svc: ServiceConfig) -> list[LintResult]:
    """Workers shouldn't have HTTP health probes (they have no ports)."""
    if svc.type == ServiceType.WORKER and svc.healthcheck:
        return [LintResult(
            rule="worker-has-probe",
            severity=Severity.WARNING,
            service=name,
            message="Worker services should not have HTTP healthchecks (no port exposed). "
                    "Remove `healthcheck` or change type to `web`.",
        )]
    return []


def _check_single_replica_production(name: str, svc: ServiceConfig, cfg: LaunchKitConfig) -> list[LintResult]:
    """Production web services should have min replicas > 1 for availability."""
    if (
        svc.type == ServiceType.WEB
        and cfg.deploy.namespace == "production"
        and svc.scale.min <= 1
    ):
        return [LintResult(
            rule="no-replicas",
            severity=Severity.WARNING,
            service=name,
            message="scale.min is 1 in production — no redundancy. "
                    "A single pod failure will cause downtime. Set min: 2 for high availability.",
        )]
    return []


def _check_cpu_scaling_io(name: str, svc: ServiceConfig) -> list[LintResult]:
    """Python WSGI/ASGI apps may not trigger CPU-based autoscaling correctly."""
    if (
        svc.lang.value == "python"
        and svc.framework in ("fastapi", "flask", "starlette")
        and svc.scale.max > 1
        and svc.scale.memory_threshold is None
    ):
        return [LintResult(
            rule="cpu-scaling-io",
            severity=Severity.INFO,
            service=name,
            message=f"{svc.framework} is async/I/O-bound — CPU-based autoscaling may not trigger correctly. "
                    f"Consider adding `memory_threshold` or using connection-based custom metrics.",
        )]
    return []


def _check_missing_env_file(name: str, svc: ServiceConfig, root: Path | None) -> list[LintResult]:
    """Check if referenced env_file actually exists."""
    if svc.env_file and root:
        env_path = root / svc.env_file
        if not env_path.exists():
            return [LintResult(
                rule="missing-env",
                severity=Severity.INFO,
                service=name,
                message=f"env_file '{svc.env_file}' is referenced but doesn't exist. "
                        f"Create it or remove the reference.",
            )]
    return []


# ── Project-level rules ──────────────────────────────────────────────────────


def _check_no_nginx(cfg: LaunchKitConfig) -> list[LintResult]:
    """Projects with multiple web services should consider nginx."""
    web_count = sum(1 for s in cfg.services.values() if s.type == ServiceType.WEB)
    if web_count > 1 and not cfg.deploy.nginx.enabled:
        return [LintResult(
            rule="no-nginx",
            severity=Severity.INFO,
            service=None,
            message=f"{web_count} web services detected but nginx is disabled. "
                    f"Consider enabling nginx as a reverse proxy for unified routing.",
        )]
    return []


def _check_no_environments(cfg: LaunchKitConfig) -> list[LintResult]:
    """Production projects should define environment profiles."""
    if not cfg.environments:
        return [LintResult(
            rule="no-environments",
            severity=Severity.INFO,
            service=None,
            message="No environments defined. Consider adding staging/production profiles "
                    "with `environments:` in launchkit.yaml for environment-specific configs.",
        )]
    return []


# ── Helpers ──────────────────────────────────────────────────────────────────


def _parse_memory_mi(mem: str) -> int:
    """Parse a K8s memory string to MiB. Returns 0 on parse failure."""
    try:
        mem = mem.strip()
        if mem.endswith("Gi"):
            return int(float(mem[:-2]) * 1024)
        elif mem.endswith("Mi"):
            return int(mem[:-2])
        elif mem.endswith("Ki"):
            return int(float(mem[:-2]) / 1024)
        return 0
    except (ValueError, IndexError):
        return 0
