"""Doctor — checks the local environment for required tools."""

from __future__ import annotations

import shutil

from rich.console import Console
from rich.table import Table

from launchkit.core.tooling import (
    CORE_TOOLS,
    VERIFY_TOOLS,
    Tool,
    docker_compose_cmd,
    tool_version,
)
from launchkit.utils.printer import print_header, print_info, print_success, print_warning


def run_doctor(console: Console) -> None:
    """Check the local environment for required and optional tools."""
    print_header(console, "LaunchKit Doctor")

    table = Table(show_lines=False)
    table.add_column("Tool", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Version")
    table.add_column("Purpose", style="dim")

    all_ok = True
    for tool in CORE_TOOLS:
        if not _add_tool_row(table, tool):
            all_ok = False

    console.print()
    console.print(table)

    # Verification tools get their own section — all optional, they unlock
    # deeper `launchkit verify` checks.
    verify_table = Table(show_lines=False, title="Verification tools (optional)")
    verify_table.add_column("Tool", style="bold")
    verify_table.add_column("Status", justify="center")
    verify_table.add_column("Version")
    verify_table.add_column("Unlocks", style="dim")
    for tool in VERIFY_TOOLS:
        _add_tool_row(verify_table, tool)

    console.print()
    console.print(verify_table)
    console.print()

    if all_ok:
        print_success(console, "All core tools found — you're ready to go!")
    else:
        print_warning(
            console,
            "Some tools are missing. LaunchKit can still generate files, "
            "but you'll need the relevant tools to build/deploy.",
        )
    print_info(
        console,
        "Install hadolint / kubeconform / actionlint to unlock `launchkit verify`.",
    )


def _add_tool_row(table: Table, tool: Tool) -> bool:
    """Add a status row for one tool. Returns True when the tool is available."""
    if shutil.which(tool.cmd):
        version = tool_version(tool.cmd, tool.version_args)
        table.add_row(tool.display_name, "[green]✔ found[/green]", version, tool.purpose)
        return True

    # docker-compose might be available as a docker subcommand.
    if tool.cmd == "docker-compose":
        compose = docker_compose_cmd()
        if compose:
            version = tool_version(compose[0], compose + ["version"])
            table.add_row(
                tool.display_name,
                "[green]✔ found[/green]",
                f"(docker compose) {version}",
                tool.purpose,
            )
            return True

    table.add_row(tool.display_name, "[yellow]✘ not found[/yellow]", "—", tool.purpose)
    return False
