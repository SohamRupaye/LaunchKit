"""File system utilities — safe write, backup, directory creation."""

from __future__ import annotations

import difflib
from pathlib import Path


def safe_write(path: str | Path, content: str, *, dry_run: bool = False) -> bool:
    """
    Write content to a file, creating parent directories if needed.

    Returns True if the file was written (or would be in dry-run mode),
    False if the file already exists with identical content.
    """
    target = Path(path)

    # Check if content is already identical
    if target.exists() and target.read_text() == content:
        return False

    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    return True


def compute_diff(existing_path: Path, new_content: str) -> str | None:
    """
    Compute a unified diff between an existing file and new content.

    Returns the diff string, or None if the files are identical.
    """
    if not existing_path.exists():
        # Entire file is new
        lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            [],
            lines,
            fromfile="/dev/null",
            tofile=str(existing_path),
        )
        result = "".join(diff)
        return result if result else None

    existing = existing_path.read_text().splitlines(keepends=True)
    new = new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        existing,
        new,
        fromfile=f"a/{existing_path}",
        tofile=f"b/{existing_path}",
    )
    result = "".join(diff)
    return result if result else None


def ensure_dir(path: str | Path) -> Path:
    """Create a directory and all parents, returning the Path object."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
