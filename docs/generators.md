# How Generators Work

LaunchKit's generators are pure functions that take a `LaunchKitConfig` (or individual `ServiceConfig`) and return a string of file content. No side effects, no file I/O — that's handled by the engine.

## Architecture

```
LaunchKitConfig
    │
    ▼
GenerateEngine (core/engine.py)
    │
    ├── generators/docker/python.py   → Dockerfile string
    ├── generators/docker/node.py     → Dockerfile string
    ├── generators/docker/go.py       → Dockerfile string
    ├── generators/ci/github.py       → ci.yml string
    ├── generators/ci/gitlab.py       → .gitlab-ci.yml string
    ├── generators/compose.py         → docker-compose.yml string
    ├── generators/kubernetes/deployment.py → deployment.yaml string
    ├── generators/kubernetes/service.py    → service.yaml string
    ├── generators/kubernetes/hpa.py        → hpa.yaml string
    └── generators/kubernetes/ingress.py    → ingress.yaml string
    │
    ▼
utils/fs.py — safe_write() handles file I/O
```

## Generator Contract

Every generator function follows this pattern:

```python
def generate_something(name: str, service: ServiceConfig, cfg: LaunchKitConfig) -> str:
    """Return the full file content as a string."""
    ...
```

### Rules

1. **Pure functions only.** No file I/O, no `Path.write_text()`, no `print()`.
2. **Return complete file content.** Include header comments, newlines, everything.
3. **Use `yaml.dump()` for YAML output.** Don't hand-build YAML strings for structured data.
4. **Use string building for non-YAML output.** Dockerfiles and CI pipelines use `"\n".join(lines)`.
5. **Accept the full config.** Generators may need project-level info (registry, namespace) beyond just the service config.

## Adding a New Generator

1. Create a new file in the appropriate subdirectory (`docker/`, `ci/`, `kubernetes/`).
2. Implement a function matching the contract above.
3. Wire it into `GenerateEngine` in `core/engine.py`.
4. Add corresponding logic to `core/diff.py` so `launchkit diff` includes the new output.
5. Add tests in `tests/unit/`.

## How the Engine Dispatches

The `GenerateEngine.run()` method:

1. Loads and validates `launchkit.yaml` via `load_and_validate()`.
2. Determines the output root (directory containing the config file).
3. Calls each generator category (`_generate_dockerfiles`, `_generate_ci`, etc.).
4. Each category iterates over services, calls the appropriate generator, and writes via `safe_write()`.
5. Collects results and prints a summary table.

The `--only` flag filters which categories run. The `--dry-run` flag passes through to `safe_write()` which skips the actual write.

## Output Structure

For a monorepo with services `api` and `frontend`:

```
project/
├── services/
│   ├── api/
│   │   └── Dockerfile          ← generated
│   └── frontend/
│       └── Dockerfile          ← generated
├── docker-compose.yml          ← generated
├── .github/workflows/ci.yml   ← generated
├── k8s/
│   ├── api/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── hpa.yaml
│   ├── frontend/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── hpa.yaml
│   └── ingress.yaml            ← if ingress.enabled
└── launchkit.yaml
```

For a flat (single-service) project, the Dockerfile is placed at the project root instead of `services/<name>/`.
