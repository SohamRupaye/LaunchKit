"""Template loader — loads and renders Jinja2 templates for generators.

Users can override any template without ejecting: drop a file with the same
relative path (e.g. ``docker/python.dockerfile.j2``) into ``.launchkit/templates/``
in their project root, and it takes precedence over the packaged version. Verify
then runs against the overridden output, so a template fix stays honest.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, select_autoescape

# Templates directory lives alongside the source code
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Project-local override directory, set per-run by the engine/diff/verify.
_OVERRIDE_DIR: Path | None = None

# Conventional location for user template overrides, relative to project root.
OVERRIDE_SUBPATH = Path(".launchkit") / "templates"


def set_template_override(project_root: Path | None) -> None:
    """
    Point the loader at a project's ``.launchkit/templates/`` override directory.

    Call once at the start of a generation run. Pass None (or a root without an
    override dir) to use only the packaged templates.
    """
    global _OVERRIDE_DIR
    if project_root is None:
        _OVERRIDE_DIR = None
        return
    candidate = project_root / OVERRIDE_SUBPATH
    _OVERRIDE_DIR = candidate if candidate.is_dir() else None


def _get_env() -> Environment:
    """Create a Jinja2 environment, honoring a project override dir when present."""
    loaders = []
    if _OVERRIDE_DIR is not None:
        loaders.append(FileSystemLoader(str(_OVERRIDE_DIR)))
    loaders.append(FileSystemLoader(str(_TEMPLATES_DIR)))
    return Environment(
        loader=ChoiceLoader(loaders),
        autoescape=select_autoescape([]),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(template_name: str, **context: object) -> str:
    """
    Load and render a Jinja2 template by name.

    Args:
        template_name: Relative path within the templates/ directory,
                       e.g. "docker/python.dockerfile.j2"
        **context: Variables passed to the template.

    Returns:
        Rendered template string.
    """
    env = _get_env()
    template = env.get_template(template_name)
    return template.render(**context)
