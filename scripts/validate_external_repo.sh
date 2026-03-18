#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 /absolute/path/to/repo" >&2
  exit 1
fi

SOURCE_REPO="$1"
if [[ ! -d "$SOURCE_REPO" ]]; then
  echo "repo not found: $SOURCE_REPO" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="$(mktemp -d)"
TARGET_DIR="$WORK_DIR/validation-target"

cleanup() {
  rm -rf "$WORK_DIR"
}

trap cleanup EXIT

cp -R "$SOURCE_REPO" "$TARGET_DIR"

if [[ -f "$ROOT_DIR/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.venv/bin/activate"
fi

printf 'Validation copy: %s\n\n' "$TARGET_DIR"
launchkit init --path "$TARGET_DIR"
printf '\n'
launchkit generate --config "$TARGET_DIR/launchkit.yaml"
printf '\nGenerated files:\n'
find "$TARGET_DIR" -maxdepth 4 -type f | sed "s#$TARGET_DIR/##" | sort