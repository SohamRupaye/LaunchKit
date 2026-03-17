# Demo Recording

The fastest high-signal demo for LaunchKit is a terminal recording that shows:

1. `launchkit init` detecting a mixed stack
2. `launchkit generate` producing deployable files

## Prerequisites

```bash
source .venv/bin/activate
python -m pip install asciinema
```

## Record The Demo

```bash
bash scripts/record_mixed_stack_demo.sh
```

The script:

1. creates a temporary monorepo with Python, Node, and Go services
2. runs `launchkit init --path <tempdir>`
3. runs `launchkit generate --config <tempdir>/launchkit.yaml`
4. writes the cast to `demo/launchkit-mixed-stack.cast`

## Suggested Social Workflow

1. Record the cast.
2. Convert it to a GIF or MP4 with your preferred tool.
3. Post the short clip instead of a README excerpt when sharing LaunchKit publicly.