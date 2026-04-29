"""Write config_params to the correct source file via config_source routing."""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

import yaml

from .packages import (
    load_framework_packages,
    pkg_sops_path,
    pkg_yaml_path,
    resolve_config_source,
)
from .sops import set_key as sops_set_key

try:
    from ruamel.yaml import YAML as _RuamelYAML
    _HAS_RUAMEL = True
except ImportError:
    _HAS_RUAMEL = False


def _load_yaml(path: Path) -> tuple[Any, Any]:
    if _HAS_RUAMEL:
        yml = _RuamelYAML()
        yml.preserve_quotes = True
        yml.representer.ignore_aliases = lambda *_: True
        yml.width = 4096
        with open(path, encoding="utf-8") as f:
            data = yml.load(f)
        return data or {}, yml
    else:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data or {}, None


def _save_yaml(path: Path, data: Any, yml: Any) -> None:
    tmp = path.with_suffix(".tmp")
    if _HAS_RUAMEL and yml is not None:
        buf = io.StringIO()
        yml.dump(data, buf)
        tmp.write_text(buf.getvalue(), encoding="utf-8")
    else:
        tmp.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
    os.replace(tmp, path)


def set_config_param(
    unit_path: str,
    key: str,
    value: Any,
    sops: bool,
    repo_root: Path,
) -> None:
    """Write a config_params key to the correct source file.

    Routing: unit_path's package → resolve config_source → write to terminal package file.
    For --sops, uses sops --set to update the encrypted file.
    """
    pkg_name = unit_path.split("/")[0]
    packages = load_framework_packages(repo_root)
    target_pkg = resolve_config_source(pkg_name, packages)

    # key may be dot-separated for nested access: "token.id" → ["token"]["id"]
    key_parts = key.split(".")

    if sops:
        target_path = pkg_sops_path(repo_root, target_pkg)
        if not target_path.exists():
            raise FileNotFoundError(
                f"Secrets file not found: {target_path}. "
                "Create it with sops before setting secrets."
            )
        secrets_key = f"{target_pkg}_secrets"
        nested = "".join(f'["{k}"]' for k in key_parts)
        jq_path = f'["{secrets_key}"]["config_params"]["{unit_path}"]{nested}'
        sops_set_key(target_path, jq_path, str(value))
    else:
        target_path = pkg_yaml_path(repo_root, target_pkg)
        if not target_path.exists():
            raise FileNotFoundError(f"Config file not found: {target_path}")
        data, yml = _load_yaml(target_path)
        pkg_section = data.get(target_pkg, {}) or {}
        config_params = pkg_section.get("config_params", {}) or {}
        unit_params = config_params.get(unit_path, {}) or {}
        # Navigate/create nested structure for dot-separated keys
        node = unit_params
        for part in key_parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[key_parts[-1]] = value
        config_params[unit_path] = unit_params
        pkg_section["config_params"] = config_params
        data[target_pkg] = pkg_section
        _save_yaml(target_path, data, yml)


def set_raw_key(
    pkg_name: str,
    yaml_key_path: str,
    value: Any,
    sops: bool,
    repo_root: Path,
) -> None:
    """Write an arbitrary key in a package's config (not scoped to config_params).

    yaml_key_path is dot-separated, e.g. '_provides_capability.0' or 'vars.my_var'.
    """
    packages = load_framework_packages(repo_root)
    target_pkg = resolve_config_source(pkg_name, packages)

    if sops:
        target_path = pkg_sops_path(repo_root, target_pkg)
        if not target_path.exists():
            raise FileNotFoundError(f"Secrets file not found: {target_path}")
        keys = yaml_key_path.split(".")
        jq_path = "".join(f'["{k}"]' for k in keys)
        sops_set_key(target_path, jq_path, str(value))
    else:
        target_path = pkg_yaml_path(repo_root, target_pkg)
        if not target_path.exists():
            raise FileNotFoundError(f"Config file not found: {target_path}")
        data, yml = _load_yaml(target_path)
        keys = yaml_key_path.split(".")
        # Navigate/create nested structure
        node = data
        for k in keys[:-1]:
            if k not in node or not isinstance(node[k], dict):
                node[k] = {}
            node = node[k]
        node[keys[-1]] = value
        _save_yaml(target_path, data, yml)
