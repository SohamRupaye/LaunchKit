"""Template loader — loads and renders Jinja2 templates for generators."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# Templates directory lives alongside the source code
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _get_env() -> Environment:
    """Create a Jinja2 environment configured for LaunchKit templates."""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
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
