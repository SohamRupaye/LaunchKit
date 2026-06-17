"""Measure — set resource requests from OBSERVED usage, not a lookup table.

This turns LaunchKit's "resource profiling" from a static guess into a real
measurement: it builds each web service, boots it, applies a light synthetic
load against the healthcheck, and records peak memory. Those numbers are rounded
UP to deterministic buckets with headroom before they touch your config.

Honest scope: the measured value is a *floor* for catching under-provisioning
(a memory_limit below the boot peak will OOMKill on startup). It is NOT
authoritative production sizing — real right-sizing needs production traffic and
tools like VPA. `launchkit measure` never runs automatically, and never
overwrites a `source: manual` resource block.
"""

from __future__ import annotations

import re
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

from launchkit.core.config import (
    LaunchKitConfig,
    ServiceConfig,
    ServiceType,
    load_and_validate,
)
from launchkit.core.diff import collect_generated
from launchkit.core.tooling import find_tool
from launchkit.core.verify import (
    _capture,
    _container_logs,
    _image_tag,
    _materialize,
    _poll_health,
    _published_port,
    _run,
)
from launchkit.detectors.resources import (
    MEM_BUCKETS_MI,
    bucket_up,
    format_memory,
)
from launchkit.utils.printer import (
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
)


@dataclass
class Measurement:
    service: str
    peak_mi: int
    new_request: str
    new_limit: str
    old_request: str
    old_limit: str
    changed: bool
    skipped_reason: str | None = None


class MeasureEngine:
    """Builds, boots, and measures services, then optionally writes back buckets."""

    def __init__(
        self,
        config_path: str,
        console: Console,
        apply: bool = False,
        keep: bool = False,
    ) -> None:
        self.config_path = config_path
        self.console = console
        self.apply = apply
        self.keep = keep

    def run(self) -> int:
        try:
            cfg = load_and_validate(self.config_path)
        except Exception as e:
            print_error(self.console, f"Failed to load config: {e}")
            raise SystemExit(1)

        if not find_tool("docker"):
            print_error(self.console, "Docker is required for `launchkit measure`.")
            raise SystemExit(1)

        root = Path(self.config_path).resolve().parent
        print_header(self.console, "LaunchKit Measure")
        print_info(
            self.console,
            "Building and booting services to observe real memory usage "
            "(light synthetic load — a floor, not production sizing).",
        )

        measurements = self._measure_all(cfg, root)
        if not measurements:
            print_warning(self.console, "No web services with a port to measure.")
            return 0

        self._render(measurements)

        if self.apply:
            self._write_back(root, measurements)
        else:
            any_change = any(m.changed for m in measurements)
            if any_change:
                print_info(
                    self.console,
                    "Re-run with `--apply` to write these buckets into launchkit.yaml.",
                )

        return 0

    # ── Measurement ───────────────────────────────────────────────────────────

    def _measure_all(self, cfg: LaunchKitConfig, root: Path) -> list[Measurement]:
        generated = collect_generated(cfg, root)
        results: list[Measurement] = []
        multi = len(cfg.services) > 1

        with tempfile.TemporaryDirectory(prefix="launchkit-measure-") as tmp:
            materialized = _materialize(generated, root, Path(tmp))

            for name, service in cfg.services.items():
                if service.type != ServiceType.WEB or not service.port:
                    continue
                context = root / "services" / name if multi else root
                tmp_dockerfile = materialized.get(context / "Dockerfile")
                if tmp_dockerfile is None or not context.is_dir():
                    continue

                peak = self._measure_one(name, service, tmp_dockerfile, context)
                if peak is None:
                    continue

                m = self._to_measurement(name, service, peak)
                results.append(m)

        return results

    def _measure_one(
        self, name: str, service: ServiceConfig, tmp_dockerfile: Path, context: Path
    ) -> int | None:
        if service.port is None:
            return None  # only web services with a port reach here
        port = service.port

        tag = _image_tag(name)
        cid = None
        try:
            ok, detail = _run(
                ["docker", "build", "-f", str(tmp_dockerfile), "-t", tag, str(context)],
                timeout=600,
            )
            if not ok:
                print_warning(self.console, f"{name}: build failed — {detail}")
                return None

            ok, out = _capture(
                ["docker", "run", "-d", "-p", f"127.0.0.1::{port}", tag],
                timeout=30,
            )
            if not ok:
                print_warning(self.console, f"{name}: container failed to start — {out}")
                return None
            cid = out.strip().split("\n")[-1].strip()

            host_port = _published_port(cid, port)
            health = service.healthcheck or "/"
            booted = False
            if host_port:
                _, booted = _poll_health(host_port, health, timeout_s=30)
            if not booted:
                logs = _container_logs(cid)
                print_warning(self.console, f"{name}: never served on {health}. Logs:\n{logs}")
                return None

            peak = self._observe_peak(cid, host_port, health)
            return peak
        finally:
            if cid:
                _run(["docker", "rm", "-f", cid], timeout=30)
            if not self.keep:
                _run(["docker", "rmi", "-f", tag], timeout=60)

    def _observe_peak(self, cid: str, host_port: int | None, health: str) -> int:
        """Sample memory at idle and under a light load; return the peak in MiB."""
        peak = _sample_mem_mi(cid)

        # Light synthetic load: a burst of requests to the healthcheck, sampling
        # memory between bursts. Deterministic count, clearly labeled as light.
        if host_port:
            url = _health_url(host_port, health)
            for _ in range(6):
                for _ in range(25):
                    _hit(url)
                peak = max(peak, _sample_mem_mi(cid))
        return peak

    def _to_measurement(
        self, name: str, service: ServiceConfig, peak_mi: int
    ) -> Measurement:
        res = service.resources
        old_request, old_limit = res.memory_request, res.memory_limit

        if res.source == "manual":
            return Measurement(
                service=name, peak_mi=peak_mi,
                new_request=old_request, new_limit=old_limit,
                old_request=old_request, old_limit=old_limit,
                changed=False, skipped_reason="source: manual (not overwritten)",
            )

        # Request = peak + 50% headroom, bucketed. Limit = 2× request, bucketed.
        req_mi = bucket_up(peak_mi * 1.5, MEM_BUCKETS_MI)
        limit_mi = bucket_up(req_mi * 2, MEM_BUCKETS_MI)
        new_request, new_limit = format_memory(req_mi), format_memory(limit_mi)
        changed = (new_request != old_request) or (new_limit != old_limit)
        return Measurement(
            service=name, peak_mi=peak_mi,
            new_request=new_request, new_limit=new_limit,
            old_request=old_request, old_limit=old_limit,
            changed=changed,
        )

    # ── Output & write-back ────────────────────────────────────────────────────

    def _render(self, measurements: list[Measurement]) -> None:
        table = Table(title="Measured memory (peak RSS under light load)")
        table.add_column("Service", style="bold")
        table.add_column("Peak", justify="right")
        table.add_column("Request", justify="right")
        table.add_column("Limit", justify="right")
        table.add_column("Note", style="dim")

        for m in measurements:
            if m.skipped_reason:
                note = m.skipped_reason
                req, limit = m.old_request, m.old_limit
            elif m.changed:
                note = f"changed from {m.old_request}/{m.old_limit}"
                req = f"[green]{m.new_request}[/green]"
                limit = f"[green]{m.new_limit}[/green]"
            else:
                note = "already optimal"
                req, limit = m.new_request, m.new_limit
            table.add_row(m.service, f"{m.peak_mi}Mi", req, limit, note)

        self.console.print()
        self.console.print(table)
        self.console.print()

    def _write_back(self, root: Path, measurements: list[Measurement]) -> None:
        to_apply = [m for m in measurements if m.changed and not m.skipped_reason]
        if not to_apply:
            print_info(self.console, "No changes to apply — config already reflects measurements.")
            return

        path = Path(self.config_path)
        raw = yaml.safe_load(path.read_text())
        for m in measurements:
            if m.skipped_reason:
                continue
            svc = raw.get("services", {}).get(m.service)
            if svc is None:
                continue
            res = svc.setdefault("resources", {})
            res["memory_request"] = m.new_request
            res["memory_limit"] = m.new_limit
            res["source"] = "measured"
            res["measured_peak_mi"] = m.peak_mi

        header = (
            "# LaunchKit config — resource values updated by `launchkit measure`\n"
            "# Measured memory is a floor for catching under-provisioning, not "
            "authoritative production sizing.\n\n"
        )
        path.write_text(header + yaml.dump(raw, default_flow_style=False, sort_keys=False))
        print_success(
            self.console,
            f"Applied measured resources for {len(to_apply)} service(s) to {path.name}.",
        )


# ── Helpers ────────────────────────────────────────────────────────────────


def _sample_mem_mi(cid: str) -> int:
    """Sample current container memory usage in MiB (0 on failure)."""
    ok, out = _capture(
        ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", cid],
        timeout=15,
    )
    if not ok or not out:
        return 0
    # "45.2MiB / 7.65GiB" → take the used side.
    used = out.split("/")[0].strip()
    return _to_mi(used)


def _to_mi(value: str) -> int:
    """Parse a docker-stats memory token (e.g. '45.2MiB', '1.2GiB') to MiB."""
    m = re.match(r"([\d.]+)\s*([KMG]i?B)", value.strip(), re.IGNORECASE)
    if not m:
        return 0
    num = float(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("g"):
        return int(num * 1024)
    if unit.startswith("m"):
        return int(num)
    if unit.startswith("k"):
        return int(num / 1024)
    return int(num / (1024 * 1024))  # bytes


def _health_url(host_port: int, path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return f"http://127.0.0.1:{host_port}{path}"


def _hit(url: str) -> None:
    """Fire one request, ignoring the result (load generation only)."""
    try:
        urllib.request.urlopen(url, timeout=5).close()
    except (urllib.error.URLError, OSError):
        pass
