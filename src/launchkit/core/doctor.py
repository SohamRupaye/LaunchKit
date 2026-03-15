"""Doctor — checks the local environment for required tools."""

from __future__ import annotations

import shutil
import subprocess

from rich.console import Console
from rich.table import Table

from launchkit.utils.printer import print_header, print_success, print_warning


# (command, display_name, version_args, purpose)
# version_args overrides the default `--version` flag for tools that use different conventions.
TOOLS: list[tuple[str, str, list[str] | None, str]] = [
    ("docker", "Docker", None, "Required for building container images"),
    ("docker-compose", "Docker Compose", None, "Required for docker-compose output (or use `docker compose`)"),
    ("kubectl", "kubectl", ["kubectl", "version", "--client", "--short"], "Required for Kubernetes deployments"),
    ("python3", "Python 3", None, "Used by LaunchKit itself"),
    ("node", "Node.js", ["node", "--version"], "Needed for Node.js service builds"),
    ("go", "Go", ["go", "version"], "Needed for Go service builds"),
    ("git", "Git", None, "Used for version detection and CI"),
]


def run_doctor(console: Console) -> None:
    """Check the local environment for required and optional tools."""
    print_header(console, "LaunchKit Doctor")

    table = Table(show_lines=False)
    table.add_column("Tool", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Version")
    table.add_column("Purpose", style="dim")

    all_ok = True

    for cmd, display_name, version_args, purpose in TOOLS:
        path = shutil.which(cmd)
        if path:
            if version_args:
                version = _get_version_args(version_args)
            else:
                version = _get_version(cmd)
            table.add_row(display_name, "[green]✔ found[/green]", version, purpose)
        else:
            # docker-compose might be a docker subcommand
            if cmd == "docker-compose" and shutil.which("docker"):
                version = _get_version_args(["docker", "compose", "version"])
                if version:
                    table.add_row(
                        display_name,
                        "[green]✔ found[/green]",
                        f"(docker compose) {version}",
                        purpose,
                    )
                    continue

            table.add_row(display_name, "[yellow]✘ not found[/yellow]", "—", purpose)
            all_ok = False

    console.print()
    console.print(table)
    console.print()

    if all_ok:
        print_success(console, "All tools found — you're ready to go!")
    else:
        print_warning(
            console,
            "Some tools are missing. LaunchKit can still generate files, "
            "but you'll need the relevant tools to build/deploy.",
        )


def _get_version(cmd: str) -> str:
    """Try to get a version string from a command using --version."""
    return _get_version_args([cmd, "--version"])


def _get_version_args(args: list[str]) -> str:
    """Run a command with args and return the first line of output."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout.strip() or result.stderr.strip()
        # Return first line, truncated
        first_line = output.split("\n")[0]
        return first_line[:80] if first_line else "installed"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "installed"
