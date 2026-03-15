"""CLI output formatting — Rich-based pretty printing for LaunchKit."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table


def print_success(console: Console, message: str) -> None:
    """Print a green success message with a checkmark."""
    console.print(f"[green]✔[/green] {message}")


def print_error(console: Console, message: str) -> None:
    """Print a red error message with an X."""
    console.print(f"[red]✘[/red] {message}")


def print_warning(console: Console, message: str) -> None:
    """Print a yellow warning message."""
    console.print(f"[yellow]⚠[/yellow] {message}")


def print_info(console: Console, message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def print_generated(console: Console, filepath: str) -> None:
    """Print a file-generated confirmation."""
    console.print(f"[green]✔[/green] Generated [bold]{filepath}[/bold]")


def print_skipped(console: Console, filepath: str, reason: str = "unchanged") -> None:
    """Print a skipped-file notice."""
    console.print(f"[dim]  Skipped {filepath} ({reason})[/dim]")


def print_header(console: Console, title: str) -> None:
    """Print a section header."""
    console.print(f"\n[bold cyan]── {title} ──[/bold cyan]")


def print_summary_table(console: Console, results: list[tuple[str, str]]) -> None:
    """
    Print a summary table of generated files.

    Each result is a (filepath, status) tuple where status is
    'generated', 'skipped', or 'error'.
    """
    table = Table(title="Generation Summary", show_lines=False)
    table.add_column("File", style="bold")
    table.add_column("Status", justify="center")

    status_styles = {
        "generated": "[green]✔ generated[/green]",
        "skipped": "[dim]– skipped[/dim]",
        "error": "[red]✘ error[/red]",
        "dry-run": "[yellow]○ dry-run[/yellow]",
    }

    for filepath, status in results:
        styled = status_styles.get(status, status)
        table.add_row(filepath, styled)

    console.print()
    console.print(table)


def print_detected_services(console: Console, services: list[dict[str, str]]) -> None:
    """Print a table of detected services."""
    table = Table(title="Detected Services", show_lines=False)
    table.add_column("Service", style="bold")
    table.add_column("Language")
    table.add_column("Framework")
    table.add_column("Port")
    table.add_column("Type")

    for svc in services:
        table.add_row(
            svc.get("name", "—"),
            svc.get("lang", "—"),
            svc.get("framework", "—"),
            str(svc.get("port", "—")),
            svc.get("type", "web"),
        )

    console.print()
    console.print(table)
