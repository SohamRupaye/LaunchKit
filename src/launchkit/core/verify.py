"""Verify — prove the generated output, don't just emit it.

This is LaunchKit's differentiator: instead of dumping templated files and hoping,
`launchkit verify` runs a staged ladder of checks against what LaunchKit produces.

Levels (each level includes the ones before it):
  static  — Level 0 (pure Python, always runs) + Level 1 (offline linters/validators)
  build   — Level 2: `docker build` every service          (added in Phase 3)
  smoke   — Level 3: run the container + hit the healthcheck (added in Phase 3)

Every external-tool check self-skips when its tool is absent — a missing tool never
fails the run, it degrades to a `skip` with a hint (see `launchkit doctor`).
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from rich.console import Console

from launchkit.core.config import (
    LaunchKitConfig,
    ServiceConfig,
    ServiceType,
    load_and_validate,
)
from launchkit.core.diff import collect_generated
from launchkit.core.linter import Severity, run_lint
from launchkit.core.tooling import docker_compose_cmd, find_tool
from launchkit.utils.printer import print_error, print_header, print_info

Status = Literal["pass", "fail", "skip"]

LEVELS = ["static", "build", "smoke"]


@dataclass
class VerifyResult:
    check: str
    status: Status
    detail: str
    target: str | None = None
    fix_hint: str | None = None


class VerifyEngine:
    """Runs the verification ladder and reports results."""

    def __init__(
        self,
        config_path: str,
        level: str = "static",
        console: Console | None = None,
        keep: bool = False,
    ) -> None:
        self.config_path = config_path
        self.level = level if level in LEVELS else "static"
        self.console = console or Console()
        self.keep = keep

    # ── Entry point ───────────────────────────────────────────────────────────

    def run(self) -> int:
        """Run verification. Returns a process exit code (0 = ok, 1 = a check failed)."""
        try:
            cfg = load_and_validate(self.config_path)
        except Exception as e:
            print_error(self.console, f"Failed to load config: {e}")
            raise SystemExit(1)

        root = Path(self.config_path).resolve().parent
        results = self.collect_results(cfg, root)
        self._render(results)
        return 1 if any(r.status == "fail" for r in results) else 0

    def collect_results(self, cfg: LaunchKitConfig, root: Path) -> list[VerifyResult]:
        """Run all checks for the configured level and return their results."""
        generated = collect_generated(cfg, root)
        results: list[VerifyResult] = []

        # Level 0 — pure Python, always runs.
        results += self._check_lint(cfg, root)
        results += self._check_manifests_parse(generated)
        results += self._check_ci_context_exists(cfg, root)

        # Everything below works off a materialized copy of the output, and the
        # tempdir must stay alive across build/smoke — so one context spans them.
        with tempfile.TemporaryDirectory(prefix="launchkit-verify-") as tmp:
            materialized = _materialize(generated, root, Path(tmp))

            # Level 1 — offline linters/validators.
            results += self._check_hadolint(materialized)
            results += self._check_kube(materialized)
            results += self._check_compose(cfg, materialized)

            # Level 2/3 — build and boot (need docker).
            if self.level in ("build", "smoke"):
                results += self._check_build_and_smoke(cfg, root, materialized)

        return results

    # ── Level 2/3 checks (docker build + boot) ────────────────────────────────

    def _check_build_and_smoke(
        self, cfg: LaunchKitConfig, root: Path, materialized: dict[Path, Path]
    ) -> list[VerifyResult]:
        if not find_tool("docker"):
            return [VerifyResult(
                "docker-build", "skip",
                detail="Docker not installed — skipping build/smoke.",
                fix_hint="Install Docker to build and smoke-test the generated image.",
            )]

        results: list[VerifyResult] = []
        built: dict[str, str] = {}  # service name → image tag
        multi = len(cfg.services) > 1
        try:
            for name, service in cfg.services.items():
                context = root / "services" / name if multi else root
                docker_path = context / "Dockerfile"
                tmp_dockerfile = materialized.get(docker_path)
                if tmp_dockerfile is None:
                    continue
                if not context.is_dir():
                    results.append(VerifyResult(
                        "docker-build", "fail", target=name,
                        detail=f"Build context '{context}' does not exist.",
                    ))
                    continue

                tag = _image_tag(name)
                ok, detail = _run(
                    ["docker", "build", "-f", str(tmp_dockerfile), "-t", tag, str(context)],
                    timeout=600,
                )
                if ok:
                    built[name] = tag
                    results.append(VerifyResult(
                        "docker-build", "pass", target=name,
                        detail="Image built successfully.",
                    ))
                else:
                    results.append(VerifyResult(
                        "docker-build", "fail", target=name, detail=detail,
                        fix_hint="The generated Dockerfile failed to build — "
                                 "check dependencies / paths.",
                    ))

            if self.level == "smoke":
                for name, service in cfg.services.items():
                    if name in built:
                        results.append(self._smoke_one(name, service, built[name]))
        finally:
            if not self.keep:
                for tag in built.values():
                    _run(["docker", "rmi", "-f", tag], timeout=60)

        return results

    def _smoke_one(self, name: str, service: ServiceConfig, tag: str) -> VerifyResult:
        """Run one built image and confirm it boots and serves."""
        if service.type != ServiceType.WEB or not service.port:
            return VerifyResult(
                "smoke", "skip", target=name,
                detail="Worker/no-port service — nothing to probe over HTTP.",
            )

        port = service.port
        health = service.healthcheck or "/"
        cid = None
        try:
            ok, out = _capture(
                ["docker", "run", "-d", "-p", f"127.0.0.1::{port}", tag],
                timeout=30,
            )
            if not ok:
                return VerifyResult(
                    "smoke", "fail", target=name,
                    detail=f"Container failed to start: {out}",
                )
            cid = out.strip().split("\n")[-1].strip()

            host_port = _published_port(cid, port)
            if not host_port:
                return VerifyResult(
                    "smoke", "fail", target=name,
                    detail="Could not determine published host port.",
                )

            status, booted = _poll_health(host_port, health, timeout_s=30)
            if booted:
                if 200 <= (status or 0) < 300:
                    note = ""
                else:
                    note = (f" (healthcheck '{health}' returned {status} — "
                            f"the app booted, but check the path)")
                return VerifyResult(
                    "smoke", "pass", target=name,
                    detail=f"Container booted and served HTTP{note}.",
                )

            logs = _container_logs(cid)
            return VerifyResult(
                "smoke", "fail", target=name,
                detail=f"Container never served on {health}. Last logs:\n{logs}",
                fix_hint="The start command may be wrong — set `command:` in launchkit.yaml.",
            )
        finally:
            if cid and not self.keep:
                _run(["docker", "rm", "-f", cid], timeout=30)

    # ── Level 0 checks (deterministic, no external tools) ─────────────────────

    def _check_lint(self, cfg: LaunchKitConfig, root: Path) -> list[VerifyResult]:
        """Surface the deployment linter as verification results."""
        out: list[VerifyResult] = []
        lint_results = run_lint(cfg, root)
        for r in lint_results:
            status: Status = "fail" if r.severity == Severity.ERROR else "pass"
            out.append(VerifyResult(
                check=f"lint:{r.rule}",
                status=status,
                target=r.service,
                detail=r.message,
                fix_hint=None,
            ))
        if not lint_results:
            out.append(VerifyResult("lint", "pass", "No deployment lint issues."))
        return out

    def _check_manifests_parse(self, generated: dict[Path, str]) -> list[VerifyResult]:
        """Every generated .yaml must parse and K8s manifests must have kind/apiVersion."""
        out: list[VerifyResult] = []
        for path, content in generated.items():
            if path.suffix not in (".yaml", ".yml"):
                continue
            rel = path.name
            try:
                docs = [d for d in yaml.safe_load_all(content) if d is not None]
            except yaml.YAMLError as e:
                out.append(VerifyResult(
                    "yaml-parse", "fail", target=rel,
                    detail=f"Invalid YAML: {e}",
                    fix_hint="This is a template bug — please report it.",
                ))
                continue
            # K8s manifests live under k8s/ — require kind + apiVersion.
            if "k8s" in path.parts:
                for doc in docs:
                    if not isinstance(doc, dict) or "kind" not in doc or "apiVersion" not in doc:
                        out.append(VerifyResult(
                            "k8s-shape", "fail", target=rel,
                            detail="Manifest is missing 'kind' or 'apiVersion'.",
                        ))
                        break
                else:
                    out.append(VerifyResult("k8s-shape", "pass", target=rel,
                                            detail="Valid K8s manifest shape."))
        return out

    def _check_ci_context_exists(self, cfg: LaunchKitConfig, root: Path) -> list[VerifyResult]:
        """
        The CI pipeline builds each service from a context directory. If that
        directory (or its Dockerfile) doesn't exist, the pipeline is broken by
        construction — this is the class of bug Phase 0 fixed, guarded here.
        """
        out: list[VerifyResult] = []
        multi = len(cfg.services) > 1
        for name in cfg.services:
            context = root / "services" / name if multi else root
            label = f"services/{name}" if multi else "."
            if not context.is_dir():
                out.append(VerifyResult(
                    "ci-context", "fail", target=name,
                    detail=f"CI build context '{label}' does not exist.",
                    fix_hint="Check your monorepo layout matches services/<name>/.",
                ))
            else:
                out.append(VerifyResult(
                    "ci-context", "pass", target=name,
                    detail=f"Build context '{label}' exists.",
                ))
        return out

    # ── Level 1 checks (offline external tools, self-skipping) ────────────────

    def _check_hadolint(self, materialized: dict[Path, Path]) -> list[VerifyResult]:
        dockerfiles = [p for p in materialized.values() if p.name == "Dockerfile"]
        if not dockerfiles:
            return []
        if not find_tool("hadolint"):
            return [VerifyResult(
                "hadolint", "skip",
                detail="hadolint not installed — skipping Dockerfile lint.",
                fix_hint="Install hadolint to lint generated Dockerfiles.",
            )]
        out: list[VerifyResult] = []
        for df in dockerfiles:
            ok, detail = _run(["hadolint", str(df)])
            out.append(VerifyResult(
                "hadolint", "pass" if ok else "fail", target=df.parent.name,
                detail=detail or "Dockerfile passed hadolint.",
            ))
        return out

    def _check_kube(self, materialized: dict[Path, Path]) -> list[VerifyResult]:
        manifests = [p for p in materialized.values()
                     if "k8s" in p.parts and p.suffix in (".yaml", ".yml")]
        if not manifests:
            return []

        if find_tool("kubeconform"):
            out: list[VerifyResult] = []
            for m in manifests:
                ok, detail = _run(["kubeconform", "-strict", "-summary", str(m)])
                out.append(VerifyResult(
                    "kubeconform", "pass" if ok else "fail", target=m.name,
                    detail=detail or "Manifest valid (kubeconform).",
                ))
            return out

        if find_tool("kubectl"):
            out = []
            for m in manifests:
                ok, detail = _run(["kubectl", "apply", "--dry-run=client", "-f", str(m)])
                if not ok and _is_cluster_unreachable(detail):
                    # kubectl client dry-run downloads the OpenAPI schema from the
                    # cluster; with no cluster it can't validate. That's an env
                    # limitation, not a broken manifest — skip, don't fail.
                    out.append(VerifyResult(
                        "kubectl-dry-run", "skip", target=m.name,
                        detail="No reachable cluster for kubectl validation.",
                        fix_hint="Install kubeconform for offline K8s schema validation.",
                    ))
                    continue
                out.append(VerifyResult(
                    "kubectl-dry-run", "pass" if ok else "fail", target=m.name,
                    detail=detail or "Manifest valid (kubectl dry-run).",
                ))
            return out

        return [VerifyResult(
            "kube-validate", "skip",
            detail="Neither kubeconform nor kubectl installed — relying on YAML shape check.",
            fix_hint="Install kubeconform for offline K8s schema validation.",
        )]

    def _check_compose(
        self, cfg: LaunchKitConfig, materialized: dict[Path, Path]
    ) -> list[VerifyResult]:
        compose_files = [p for p in materialized.values() if p.name == "docker-compose.yml"]
        if not compose_files:
            return []
        compose = docker_compose_cmd()
        if not compose:
            return [VerifyResult(
                "compose-config", "skip",
                detail="docker compose not available — skipping compose validation.",
                fix_hint="Install Docker to validate docker-compose.yml.",
            )]
        cf = compose_files[0]
        ok, detail = _run(compose + ["-f", str(cf), "config", "-q"])
        return [VerifyResult(
            "compose-config", "pass" if ok else "fail", target=cf.name,
            detail=detail or "docker-compose.yml is valid.",
        )]

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render(self, results: list[VerifyResult]) -> None:
        print_header(self.console, f"LaunchKit Verify — level: {self.level}")

        icons = {"pass": "[green]✔[/green]", "fail": "[red]✘[/red]", "skip": "[dim]○[/dim]"}
        for r in results:
            target = f"[bold]{r.target}[/bold]: " if r.target else ""
            self.console.print(f"  {icons[r.status]} [dim]{r.check}[/dim] {target}{r.detail}")
            if r.fix_hint and r.status != "pass":
                self.console.print(f"      [dim]↳ {r.fix_hint}[/dim]")

        passed = sum(1 for r in results if r.status == "pass")
        failed = sum(1 for r in results if r.status == "fail")
        skipped = sum(1 for r in results if r.status == "skip")

        self.console.print()
        self.console.print(
            f"[bold]{passed} passed, {failed} failed, {skipped} skipped.[/bold]"
        )
        if failed == 0:
            print_info(self.console, "Verification passed — the generated output checks out.")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _materialize(
    generated: dict[Path, str], root: Path, tmp_root: Path
) -> dict[Path, Path]:
    """
    Write the generated content into a tempdir, preserving relative layout.

    Returns a map of {original path: tempdir path}. Keeping the original layout
    (services/<name>/Dockerfile, k8s/<name>/deployment.yaml) means the tempdir
    paths carry the same `.parts` the checks rely on for labeling.
    """
    materialized: dict[Path, Path] = {}
    for path, content in generated.items():
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = Path(path.name)
        dest = tmp_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        materialized[path] = dest
    return materialized


def _image_tag(name: str) -> str:
    """A safe, lowercase docker tag for a verify build."""
    safe = re.sub(r"[^a-z0-9._-]", "-", name.lower()).strip("-") or "service"
    return f"launchkit-verify-{safe}:latest"


def _published_port(cid: str, container_port: int) -> int | None:
    """Resolve the host port docker mapped a container port to."""
    ok, out = _capture(["docker", "port", cid, f"{container_port}/tcp"], timeout=10)
    if not ok or not out:
        return None
    # Output like "127.0.0.1:54321" (possibly multiple lines).
    for line in out.split("\n"):
        m = re.search(r":(\d+)\s*$", line.strip())
        if m:
            return int(m.group(1))
    return None


def _poll_health(host_port: int, path: str, timeout_s: int = 30) -> tuple[int | None, bool]:
    """
    Poll http://127.0.0.1:<host_port><path> until it responds or times out.

    Returns (last_status, booted). `booted` is True as soon as the server sends
    any HTTP response — that proves the start command booted a serving process.
    """
    if not path.startswith("/"):
        path = "/" + path
    url = f"http://127.0.0.1:{host_port}{path}"
    deadline = time.monotonic() + timeout_s
    last_status: int | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return resp.status, True
        except urllib.error.HTTPError as e:
            # Got an HTTP response (e.g. 404/500) → the app is up and serving.
            last_status = e.code
            return e.code, True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(1)
    return last_status, False


def _container_logs(cid: str, tail: int = 20) -> str:
    # A container writes to both stdout and stderr; `docker logs` preserves that
    # split, so merge the streams or we lose the very error we need to show.
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(tail), cid],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=10,
        )
        out = result.stdout.strip()
        return out if out else "(no logs)"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "(no logs)"


def _is_cluster_unreachable(detail: str) -> bool:
    """True when a kubectl failure is 'no cluster' rather than 'bad manifest'."""
    markers = (
        "failed to download openapi",
        "connection refused",
        "unable to connect to the server",
        "no configuration has been provided",
        "the connection to the server",
    )
    low = detail.lower()
    return any(m in low for m in markers)


def _run(cmd: list[str], timeout: int = 60) -> tuple[bool, str]:
    """
    Run a subprocess, returning (ok, detail). `detail` is the trimmed output on
    failure (for the user), empty on success. Never raises.
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return True, ""
        output = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
        # Keep it short — a few lines is enough to act on.
        lines = [ln for ln in output.split("\n") if ln.strip()][:6]
        return False, " | ".join(lines) if lines else f"exit code {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    except (FileNotFoundError, OSError) as e:
        return False, str(e)


def _capture(cmd: list[str], timeout: int = 30) -> tuple[bool, str]:
    """
    Like `_run`, but returns stdout on success (needed for `docker run`/`port`/
    `logs` where the output is the whole point). Never raises.
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return True, result.stdout.strip()
        combined = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
        return False, combined or f"exit code {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"
    except (FileNotFoundError, OSError) as e:
        return False, str(e)
