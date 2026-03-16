# Contributing to LaunchKit

Thanks for contributing. LaunchKit is intentionally simple — keep it that way.

## Setup

```bash
git clone https://github.com/SohamRupaye/launchkit
cd launchkit
pip install -e ".[dev]"
```

For release work:

```bash
pip install -e ".[dev,release]"
```

## Adding a Language

1. Create `src/launchkit/detectors/yourlang.py` implementing `BaseDetector`
2. Create `src/launchkit/generators/docker/yourlang.py` with a Dockerfile template
3. Register the detector in `src/launchkit/detectors/base.py`
4. Add the lang to `Lang` enum in `src/launchkit/core/config.py`
5. Add tests in `tests/unit/`
6. Add an example in `examples/`

See [docs/adding-a-language.md](docs/adding-a-language.md) for a full walkthrough.

## Adding a CI Provider

1. Create `src/launchkit/generators/ci/yourprovider.py`
2. Add the provider to `CIProvider` enum in config
3. Wire it in `GenerateEngine._generate_ci()`

## Running Tests

```bash
pytest
```

## Release Checklist

1. Confirm the suite passes locally from the project virtualenv.
2. Build distributions with `python -m build`.
3. Check artifacts with `python -m twine check dist/*`.
4. Tag a release as `vX.Y.Z` to trigger the publish workflow in `.github/workflows/publish.yml`.

## Demo Recording

Generate the mixed-stack demo cast with:

```bash
bash scripts/record_mixed_stack_demo.sh
```

The script is designed for asciinema and records `launchkit init` followed by `launchkit generate` against a temporary mixed-stack repo.

## Real-World Validation

Use [docs/real-world-validation.md](docs/real-world-validation.md) before opening issues about detection misses or incorrect output. It standardizes what information maintainers need to reproduce a problem quickly.

## Principles

- **Output is plain files.** No runtime dependency on LaunchKit after generation.
- **No vendor lock-in** in generated output. Generated K8s manifests must work on any conformant cluster.
- **Detectors should be conservative.** A false negative (not detecting) is better than a false positive (wrong detection).
- **Keep the config schema minimal.** If a user has to read docs to fill in a field, reconsider whether the field should exist.
