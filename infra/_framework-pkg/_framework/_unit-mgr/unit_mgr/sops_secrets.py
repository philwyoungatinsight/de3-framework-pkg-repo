"""Read and write config_params keys in SOPS-encrypted secrets files."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import yaml


def _sops_decrypt(path: Path) -> dict:
    """Decrypt a SOPS file and return parsed YAML dict."""
    result = subprocess.run(
        ["sops", "--decrypt", str(path)],
        capture_output=True, text=True, check=True,
    )
    return yaml.safe_load(result.stdout) or {}


def _sops_encrypt_from_dict(path: Path, data: dict) -> None:
    """Write data to a SOPS file atomically.

    NEVER uses shell redirect (>) — uses sops --encrypt --output (atomic write).
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as tmp:
        yaml.dump(data, tmp, default_flow_style=False, allow_unicode=True)
        tmp_path = tmp.name

    try:
        subprocess.run(
            ["sops", "--encrypt", "--output", str(path), tmp_path],
            check=True,
        )
    finally:
        os.unlink(tmp_path)


def migrate_secrets(
    src_sops_path: Path,
    dst_sops_path: Path,
    src_pkg: str,
    dst_pkg: str,
    src_rel: str,
    dst_rel: str,
    operation: str,  # "copy" or "move"
) -> int:
    """Migrate config_params keys from src SOPS file to dst SOPS file.

    Returns the number of keys migrated.
    """
    if not src_sops_path.exists():
        return 0

    src_data = _sops_decrypt(src_sops_path)

    src_top = src_data.get(f"{src_pkg}_secrets", {}) or {}
    config_params = src_top.get("config_params", {}) or {}

    keys_to_move = {
        k: v for k, v in config_params.items()
        if k == src_rel or k.startswith(src_rel + "/")
    }
    if not keys_to_move:
        return 0

    # Rename keys
    moved = {dst_rel + k[len(src_rel):]: v for k, v in keys_to_move.items()}

    # Remove from source (in-memory)
    for k in keys_to_move:
        del config_params[k]
    src_top["config_params"] = config_params
    src_data[f"{src_pkg}_secrets"] = src_top

    # Re-encrypt source for cross-package move (remove old keys from src file).
    # Same-package move is handled below in a single write to avoid a vulnerability
    # window where old keys are deleted but renamed keys not yet written.
    if operation == "move" and src_pkg != dst_pkg:
        _sops_encrypt_from_dict(src_sops_path, src_data)

    # Merge into destination
    if src_pkg == dst_pkg:
        if operation == "copy":
            # Source unchanged; re-read and add renamed keys alongside originals.
            dst_data = _sops_decrypt(src_sops_path)
            dst_top = dst_data.get(f"{dst_pkg}_secrets", {}) or {}
            dst_cfg = dst_top.get("config_params", {}) or {}
            dst_cfg.update(moved)
            dst_top["config_params"] = dst_cfg
            dst_data[f"{dst_pkg}_secrets"] = dst_top
            _sops_encrypt_from_dict(src_sops_path, dst_data)
        else:
            # Same-package move: old keys already removed from src_data in-memory above.
            # Add renamed keys and write once (single SOPS operation — no vulnerability window).
            config_params.update(moved)
            src_top["config_params"] = config_params
            src_data[f"{src_pkg}_secrets"] = src_top
            _sops_encrypt_from_dict(src_sops_path, src_data)
    else:
        # Cross-package: src already written above; write dst now.
        if dst_sops_path.exists():
            dst_data = _sops_decrypt(dst_sops_path)
        else:
            dst_data = {f"{dst_pkg}_secrets": {"config_params": {}}}

        dst_top = dst_data.get(f"{dst_pkg}_secrets", {}) or {}
        dst_cfg = dst_top.get("config_params", {}) or {}
        dst_cfg.update(moved)
        dst_top["config_params"] = dst_cfg
        dst_data[f"{dst_pkg}_secrets"] = dst_top
        _sops_encrypt_from_dict(dst_sops_path, dst_data)

    return len(keys_to_move)
