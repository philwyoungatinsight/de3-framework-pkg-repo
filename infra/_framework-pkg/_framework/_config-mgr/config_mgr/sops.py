"""SOPS subprocess helpers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


def decrypt_to_dict(sops_path: Path) -> dict:
    """Decrypt a SOPS file and return its contents as a dict.

    Raises subprocess.CalledProcessError on failure.
    """
    result = subprocess.run(
        ["sops", "--decrypt", str(sops_path)],
        capture_output=True,
    )
    if result.returncode != 0:
        msg = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(
            f"sops decrypt failed for {sops_path}:\n{msg}"
        )
    return yaml.safe_load(result.stdout.decode()) or {}


def set_key(sops_path: Path, key_path: str, value: str) -> None:
    """Set a key in a SOPS-encrypted file using sops --set.

    key_path is a jq-style path string, e.g.
    '["pkg_secrets"]["config_params"]["unit/path"]["key"]'
    """
    set_expr = f'{key_path} {_quote_value(value)}'
    result = subprocess.run(
        ["sops", "--set", set_expr, str(sops_path)],
        capture_output=True,
    )
    if result.returncode != 0:
        msg = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(
            f"sops --set failed for {sops_path}:\n{msg}"
        )


def _quote_value(value: str) -> str:
    """Wrap value in double quotes for sops --set expression."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
