"""Upgrade — re-run intelligence and suggest config updates."""

from __future__ import annotations

from pathlib import Path

import yaml
from rich.console import Console

from launchkit.core.config import LaunchKitConfig, load_and_validate
from launchkit.detectors.environment import detect_environment
from launchkit.detectors.resources import infer_resource_profile
from launchkit.utils.printer import print_header, print_info, print_success, print_warning


def run_upgrade(config_path: str, yes: bool, console: Console) -> None:
    """
    Re-run the intelligence layer and suggest config updates.

    Compares current launchkit.yaml against what the detectors would
    produce now, and offers to apply the diff.
    """
    try:
        cfg = load_and_validate(config_path)
    except Exception as e:
        console.print(f"[red]✘[/red] Failed to load config: {e}")
        raise SystemExit(1)

    root = Path(config_path).resolve().parent
    print_header(console, "LaunchKit Upgrade")
    print_info(console, "Re-analyzing your project for changes...")

    suggestions: list[str] = []
    updates: dict = {}

    # ── Re-detect environment ────────────────────────────────────────────
    env = detect_environment(root)

    # Check CI provider
    if env.ci_provider != cfg.ci.provider.value:
        suggestions.append(
            f"  [yellow]~[/yellow] ci.provider: "
            f"[dim]{cfg.ci.provider.value}[/dim] → [bold]{env.ci_provider}[/bold]\n"
            f"    (detected from project files)"
        )
        updates.setdefault("ci", {})["provider"] = env.ci_provider

    # Check branches
    if set(env.branches) != set(cfg.ci.branches):
        new_branches = [b for b in env.branches if b not in cfg.ci.branches]
        if new_branches:
            suggestions.append(
                f"  [yellow]~[/yellow] ci.branches: detected new branch(es) "
                f"[bold]{', '.join(new_branches)}[/bold]\n"
                f"    suggested: add to branch triggers"
            )
            updates.setdefault("ci", {})["branches"] = env.branches

    # Check registry
    if env.registry_hint and env.registry_hint != cfg.project.registry:
        if "yourname" in cfg.project.registry:
            suggestions.append(
                f"  [yellow]~[/yellow] project.registry: "
                f"[dim]{cfg.project.registry}[/dim] → [bold]{env.registry_hint}[/bold]\n"
                f"    (inferred from git remote)"
            )
            updates.setdefault("project", {})["registry"] = env.registry_hint

    # ── Re-profile each service ──────────────────────────────────────────
    multi = len(cfg.services) > 1

    for name, service in cfg.services.items():
        if multi:
            service_path = root / "services" / name
        else:
            service_path = root

        if not service_path.exists():
            continue

        new_profile = infer_resource_profile(
            lang=service.lang.value,
            framework=service.framework,
            service_type=service.type.value,
            service_path=service_path,
        )

        current_profile = service.resources.profile
        if current_profile and current_profile != new_profile.profile_name:
            suggestions.append(
                f"  [yellow]~[/yellow] {name}: resource profile changed "
                f"[dim]{current_profile}[/dim] → [bold]{new_profile.profile_name}[/bold]\n"
                f"    (dependency changes detected)"
            )
            updates.setdefault("services", {}).setdefault(name, {})["resources"] = {
                "profile": new_profile.profile_name,
                "cpu_request": new_profile.cpu_request,
                "cpu_limit": new_profile.cpu_limit,
                "memory_request": new_profile.memory_request,
                "memory_limit": new_profile.memory_limit,
            }

        # Check if tests were added
        if env.has_tests and "test" not in cfg.ci.steps:
            suggestions.append(
                f"  [green]+[/green] ci.steps: tests detected — suggest adding 'test' step"
            )
            updates.setdefault("ci", {})["steps"] = ["lint", "test", "build", "push"]

    # ── Present suggestions ──────────────────────────────────────────────
    if not suggestions:
        print_success(console, "Your config is up to date — no suggestions.")
        return

    console.print()
    for s in suggestions:
        console.print(s)
    console.print()

    if not yes:
        confirm = console.input("[bold]Apply changes? [y/N][/bold] ")
        if confirm.lower() not in ("y", "yes"):
            print_info(console, "No changes applied.")
            return

    # ── Apply updates ────────────────────────────────────────────────────
    _apply_updates(config_path, updates)
    print_success(console, f"Updated {config_path}")
    print_info(console, "Run `launchkit generate` to regenerate files with new config.")


def _apply_updates(config_path: str, updates: dict) -> None:
    """Merge updates into the existing YAML config file."""
    path = Path(config_path)
    raw = yaml.safe_load(path.read_text())

    _deep_merge(raw, updates)

    # Preserve header comments
    content = (
        "# LaunchKit config — updated by `launchkit upgrade`\n"
        "# Edit this file, then run `launchkit generate`\n\n"
        + yaml.dump(raw, default_flow_style=False, sort_keys=False)
    )
    path.write_text(content)


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override into base dict."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
