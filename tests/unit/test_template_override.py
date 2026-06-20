"""Tests for the user template-override escape hatch."""

from __future__ import annotations

from pathlib import Path

from launchkit.utils.templates import render_template, set_template_override


class TestTemplateOverride:
    def test_override_takes_precedence(self, tmp_path: Path) -> None:
        override = tmp_path / ".launchkit" / "templates" / "docker"
        override.mkdir(parents=True)
        (override.parent.parent / "templates" / "docker" / "python.dockerfile.j2")  # noqa: for clarity
        (override / "python.dockerfile.j2").write_text("# CUSTOM {{ port }}\n")

        set_template_override(tmp_path)
        out = render_template("docker/python.dockerfile.j2", port=8000, framework=None,
                              service_type="web", command=None, dep_manager="requirements", name="x")
        assert out.strip() == "# CUSTOM 8000"

    def test_falls_back_to_packaged(self, tmp_path: Path) -> None:
        # No override dir → packaged template is used.
        set_template_override(tmp_path)
        out = render_template("docker/python.dockerfile.j2", port=8000, framework="fastapi",
                              service_type="web", command=None, dep_manager="requirements", name="x")
        assert "python:3.12-slim" in out

    def test_none_disables_override(self, tmp_path: Path) -> None:
        override = tmp_path / ".launchkit" / "templates" / "docker"
        override.mkdir(parents=True)
        (override / "python.dockerfile.j2").write_text("# CUSTOM\n")
        set_template_override(None)
        out = render_template("docker/python.dockerfile.j2", port=8000, framework="fastapi",
                              service_type="web", command=None, dep_manager="requirements", name="x")
        assert "# CUSTOM" not in out
