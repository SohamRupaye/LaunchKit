# Release Guide

LaunchKit is ready to publish from GitHub Actions, but the first release still requires PyPI configuration in the repository settings.

## Local Release Validation

```bash
source .venv/bin/activate
python -m pip install -e ".[dev,release]"
python -m pytest -q
python -m build
python -m twine check dist/*
```

## GitHub Publish Flow

The repository includes `.github/workflows/publish.yml`.

It runs when a tag matching `v*` is pushed and does two things:

1. builds both sdist and wheel artifacts
2. publishes them to PyPI using trusted publishing

## One-Time PyPI Setup

1. Create the `launchkit` project on PyPI if it does not already exist.
2. Configure PyPI trusted publishing for this repository.
3. Push a tag such as `v0.1.0`.

Until that setup is complete, `pip install launchkit` will not work for new users because there is nothing published for pip to fetch.