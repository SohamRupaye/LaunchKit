"""LaunchKit CLI — One config file. Production-ready output. No vendor lock-in."""

import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(package_name="launchkit-cli")
def main() -> None:
    """LaunchKit — generate Dockerfiles, CI pipelines, and Kubernetes manifests from one config."""


@main.command()
@click.option("--force", is_flag=True, help="Overwrite existing launchkit.yaml")
@click.option("--path", default=".", show_default=True, help="Project root to scan")
@click.option(
    "--target",
    type=click.Choice(["auto", "compose", "kubernetes", "both"], case_sensitive=False),
    default="auto",
    show_default=True,
    help="Deployment target (auto = compose for 1 service, k8s for monorepo)",
)
def init(force: bool, path: str, target: str) -> None:
    """Detect your stack and scaffold launchkit.yaml."""
    from launchkit.core.engine import InitEngine
    engine = InitEngine(root=path, force=force, console=console, target=target)
    engine.run()


@main.command()
@click.option(
    "--only",
    type=click.Choice(["docker", "ci", "k8s", "compose", "nginx"], case_sensitive=False),
    default=None,
    help="Generate only a specific output type",
)
@click.option("--dry-run", is_flag=True, help="Print output without writing files")
@click.option("--config", default="launchkit.yaml", show_default=True, help="Config file path")
@click.option("--env", default=None, help="Environment to generate for (e.g. staging, production)")
@click.option("--verify", "do_verify", is_flag=True, help="Run static verification after generating")
def generate(only: str | None, dry_run: bool, config: str, env: str | None, do_verify: bool) -> None:
    """Generate Dockerfiles, CI pipelines, and Kubernetes manifests."""
    from launchkit.core.engine import GenerateEngine
    engine = GenerateEngine(config_path=config, only=only, dry_run=dry_run, console=console, env=env)
    engine.run()

    if do_verify and not dry_run:
        from launchkit.core.verify import VerifyEngine
        console.print()
        code = VerifyEngine(config_path=config, level="static", console=console).run()
        if code != 0:
            raise SystemExit(code)


@main.command()
@click.option("--config", default="launchkit.yaml", show_default=True)
def diff(config: str) -> None:
    """Show what would change on the next generate."""
    from launchkit.core.diff import DiffEngine
    engine = DiffEngine(config_path=config, console=console)
    engine.run()


@main.command()
@click.option("--config", default="launchkit.yaml", show_default=True)
def validate(config: str) -> None:
    """Validate launchkit.yaml without generating any files."""
    from launchkit.core.config import load_and_validate
    try:
        cfg = load_and_validate(config)
        console.print(f"[green]✔[/green] {config} is valid — {len(cfg.services)} service(s) defined")
    except Exception as e:
        console.print(f"[red]✘[/red] Validation failed: {e}")
        raise SystemExit(1)


@main.command()
def doctor() -> None:
    """Check your environment for required tools (docker, kubectl, etc.)."""
    from launchkit.core.doctor import run_doctor
    run_doctor(console=console)


@main.command()
@click.option("--config", default="launchkit.yaml", show_default=True)
def lint(config: str) -> None:
    """Lint your config for deployment issues before they hit production."""
    from launchkit.core.config import load_and_validate
    from launchkit.core.linter import run_lint, Severity
    from pathlib import Path

    try:
        cfg = load_and_validate(config)
    except Exception as e:
        console.print(f"[red]✘[/red] {e}")
        raise SystemExit(1)

    root = Path(config).resolve().parent
    results = run_lint(cfg, root)

    if not results:
        console.print("[green]✔[/green] All checks passed — no issues found.")
        return

    severity_styles = {
        Severity.ERROR: "[red]✘[/red]",
        Severity.WARNING: "[yellow]⚠[/yellow]",
        Severity.INFO: "[blue]ℹ[/blue]",
    }

    errors = 0
    for r in results:
        icon = severity_styles.get(r.severity, "")
        target = f"[bold]{r.service}[/bold]: " if r.service else ""
        console.print(f"  {icon} {target}{r.message}")
        if r.severity == Severity.ERROR:
            errors += 1

    console.print()
    total = len(results)
    console.print(
        f"[bold]{total} issue(s)[/bold] found "
        f"({errors} error, {total - errors} warning/info)."
    )

    if errors > 0:
        raise SystemExit(1)


@main.command()
@click.option("--config", default="launchkit.yaml", show_default=True)
@click.option(
    "--level",
    type=click.Choice(["static", "build", "smoke"], case_sensitive=False),
    default="static",
    show_default=True,
    help="How deep to verify: static (lint+validate), build (docker build), smoke (build+boot+healthcheck)",
)
@click.option("--keep", is_flag=True, help="Keep built images/containers for debugging")
def verify(config: str, level: str, keep: bool) -> None:
    """Prove the generated output: lint, validate, build, and smoke-test it."""
    from launchkit.core.verify import VerifyEngine
    engine = VerifyEngine(config_path=config, level=level, console=console, keep=keep)
    code = engine.run()
    if code != 0:
        raise SystemExit(code)


@main.command()
@click.option("--config", default="launchkit.yaml", show_default=True)
@click.option("--apply", is_flag=True, help="Write measured resource buckets into launchkit.yaml")
@click.option("--keep", is_flag=True, help="Keep built images for debugging")
def measure(config: str, apply: bool, keep: bool) -> None:
    """Measure real memory usage and set resource requests from observed data."""
    from launchkit.core.measure import MeasureEngine
    engine = MeasureEngine(config_path=config, console=console, apply=apply, keep=keep)
    code = engine.run()
    if code != 0:
        raise SystemExit(code)


@main.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--path", default=".", show_default=True, help="Project root")
def eject(yes: bool, path: str) -> None:
    """Remove LaunchKit markers and leave clean standalone files."""
    from launchkit.core.eject import run_eject
    run_eject(root=path, yes=yes, console=console)


@main.command()
@click.option("--config", default="launchkit.yaml", show_default=True)
@click.option("--yes", "-y", is_flag=True, help="Apply changes without confirmation")
def upgrade(config: str, yes: bool) -> None:
    """Re-run intelligence and suggest config updates."""
    from launchkit.core.upgrade import run_upgrade
    run_upgrade(config_path=config, yes=yes, console=console)
