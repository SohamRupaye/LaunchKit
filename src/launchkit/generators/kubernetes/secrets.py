"""Secret management hints — generates K8s Secret templates from env_file references."""

from __future__ import annotations

from pathlib import Path

import yaml

from launchkit.core.config import LaunchKitConfig, ServiceConfig


def generate_secrets_hint(
    name: str,
    service: ServiceConfig,
    cfg: LaunchKitConfig,
    root: Path | None = None,
) -> str | None:
    """
    Generate a K8s Secret hint file for a service that references an env_file.

    Returns None if the service has no env_file.
    The generated file is a HINT — not meant to be committed with real values.
    """
    if not service.env_file:
        return None

    namespace = cfg.deploy.namespace
    env_keys = _extract_env_keys(service.env_file, root)

    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": f"{name}-secrets",
            "namespace": namespace,
            "labels": {
                "app": name,
                "managed-by": "launchkit",
            },
        },
        "type": "Opaque",
        "stringData": {k: "" for k in env_keys} if env_keys else {"EXAMPLE_KEY": ""},
    }

    header = (
        f"# LaunchKit detected env_file: {service.env_file}\n"
        f"#\n"
        f"# ⚠ This is a HINT — do NOT commit this file with real secrets!\n"
        f"#\n"
        f"# For production, use one of:\n"
        f"#   - External Secrets Operator (https://external-secrets.io)\n"
        f"#   - Sealed Secrets (https://sealed-secrets.netlify.app)\n"
        f"#   - Vault + vault-injector\n"
        f"#   - kubectl create secret generic {name}-secrets --from-env-file={service.env_file}\n"
        f"#\n"
    )

    return header + yaml.dump(secret, default_flow_style=False, sort_keys=False)


def _extract_env_keys(env_file: str, root: Path | None) -> list[str]:
    """
    Try to read the env file and extract variable names.

    Reads lines like:
        DATABASE_URL=postgres://...
        SECRET_KEY=abc123
        # comment
        EMPTY_VAR=

    Returns a list of variable names (no values).
    """
    if not root:
        return []

    env_path = root / env_file
    if not env_path.exists():
        return []

    keys: list[str] = []
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key = line.split("=", 1)[0].strip()
                if key:
                    keys.append(key)
    except (OSError, UnicodeDecodeError):
        pass

    return keys
