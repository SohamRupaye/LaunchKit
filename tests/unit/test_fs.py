"""Tests for file system utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from launchkit.utils.fs import safe_write, compute_diff, ensure_dir


class TestSafeWrite:
    def test_creates_file(self, tmp_path: Path) -> None:
        target = tmp_path / "out" / "test.txt"
        result = safe_write(target, "hello world")
        assert result is True
        assert target.read_text() == "hello world"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c" / "test.txt"
        safe_write(target, "deep")
        assert target.exists()

    def test_skips_identical_content(self, tmp_path: Path) -> None:
        target = tmp_path / "test.txt"
        target.write_text("same content")
        result = safe_write(target, "same content")
        assert result is False

    def test_overwrites_different_content(self, tmp_path: Path) -> None:
        target = tmp_path / "test.txt"
        target.write_text("old content")
        result = safe_write(target, "new content")
        assert result is True
        assert target.read_text() == "new content"

    def test_dry_run_no_file_created(self, tmp_path: Path) -> None:
        target = tmp_path / "test.txt"
        result = safe_write(target, "hello", dry_run=True)
        assert result is True
        assert not target.exists()

    def test_dry_run_existing_identical(self, tmp_path: Path) -> None:
        target = tmp_path / "test.txt"
        target.write_text("hello")
        result = safe_write(target, "hello", dry_run=True)
        assert result is False


class TestComputeDiff:
    def test_new_file(self, tmp_path: Path) -> None:
        target = tmp_path / "new.txt"
        diff = compute_diff(target, "new content\n")
        assert diff is not None
        assert "+new content" in diff

    def test_identical_file(self, tmp_path: Path) -> None:
        target = tmp_path / "same.txt"
        target.write_text("same\n")
        diff = compute_diff(target, "same\n")
        assert diff is None

    def test_changed_file(self, tmp_path: Path) -> None:
        target = tmp_path / "changed.txt"
        target.write_text("old line\n")
        diff = compute_diff(target, "new line\n")
        assert diff is not None
        assert "-old line" in diff
        assert "+new line" in diff


class TestEnsureDir:
    def test_creates_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c"
        result = ensure_dir(target)
        assert result.is_dir()
        assert result == target

    def test_existing_dir(self, tmp_path: Path) -> None:
        result = ensure_dir(tmp_path)
        assert result == tmp_path
