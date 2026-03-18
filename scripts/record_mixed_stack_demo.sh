#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEMO_DIR="$ROOT_DIR/demo"
CAST_PATH="$DEMO_DIR/launchkit-mixed-stack.cast"
WORK_DIR="$(mktemp -d)"
TARGET_DIR="$WORK_DIR/mixed-stack-demo"

cleanup() {
  rm -rf "$WORK_DIR"
}

trap cleanup EXIT

mkdir -p "$DEMO_DIR"
mkdir -p "$TARGET_DIR/services/api" "$TARGET_DIR/services/frontend" "$TARGET_DIR/services/processor"

cp "$ROOT_DIR/examples/mixed-stack/services/api/requirements.txt" "$TARGET_DIR/services/api/requirements.txt"
cp "$ROOT_DIR/examples/mixed-stack/services/frontend/package.json" "$TARGET_DIR/services/frontend/package.json"
cp "$ROOT_DIR/examples/mixed-stack/services/processor/go.mod" "$TARGET_DIR/services/processor/go.mod"

cat > "$TARGET_DIR/services/api/main.py" <<'EOF'
from fastapi import FastAPI

app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
EOF

cat > "$TARGET_DIR/services/processor/main.go" <<'EOF'
package main

func main() {}
EOF

if ! command -v asciinema >/dev/null 2>&1; then
  echo "asciinema is required. Install it in the project venv first." >&2
  exit 1
fi

if [[ -f "$ROOT_DIR/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
fi

asciinema rec --overwrite --quiet --command "cd '$ROOT_DIR' && clear && printf 'Temporary demo repo: %s\n\n' '$TARGET_DIR' && launchkit init --path '$TARGET_DIR' && printf '\n' && launchkit generate --config '$TARGET_DIR/launchkit.yaml' && printf '\nGenerated files:\n' && find '$TARGET_DIR' -maxdepth 4 -type f | sed 's#'$TARGET_DIR'/##' | sort" "$CAST_PATH"

printf 'Wrote %s\n' "$CAST_PATH"