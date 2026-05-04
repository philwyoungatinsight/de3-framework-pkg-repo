"""Load framework_packages.yaml and resolve config_source chains."""

from __future__ import annotations

import os
from pathlib import Path

import yaml


def _fw_cfg_path(repo_root: Path, filename: str) -> Path:
    """Three-path lookup for framework config files.

    Priority (highest first): config/ → _FRAMEWORK_MAIN_PACKAGE/_config/ → _framework-pkg/_config/defaults/
    """
    override = repo_root / "config" / filename
    if override.exists():
        return override
    config_pkg_dir = os.environ.get("_MAIN_PKG_DIR")
    if config_pkg_dir:
        candidate = Path(config_pkg_dir) / "_config" / "_framework_settings" / filename
        if candidate.exists():
            return candidate
    pkg_dir = os.environ.get("_FRAMEWORK_PKG_DIR") or str(repo_root / "infra" / "_framework-pkg")
    return Path(pkg_dir) / "_config" / "_framework_settings" / filename


def load_framework_packages(repo_root: Path) -> list[dict]:
    """Load the list of package entries from framework_packages.yaml."""
    path = _fw_cfg_path(repo_root, "framework_packages.yaml")
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw.get("framework_packages", [])


def load_framework_config_mgr(repo_root: Path) -> dict:
    """Load framework_config_mgr.yaml settings."""
    path = _fw_cfg_path(repo_root, "framework_config_mgr.yaml")
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw.get("framework_config_mgr", {})


def resolve_config_source(pkg_name: str, packages: list[dict]) -> str:
    """Follow config_source chain; return terminal package name.

    Raises ValueError on cycle or if a package in the chain does not exist.
    """
    pkg_map = {p["name"]: p for p in packages}
    visited: list[str] = []
    current = pkg_name
    while True:
        if current in visited:
            raise ValueError(
                f"config_source cycle: {' -> '.join(visited + [current])}"
            )
        visited.append(current)
        entry = pkg_map.get(current)
        if entry is None:
            if len(visited) > 1:
                raise ValueError(
                    f"config_source chain broken: '{visited[-2]}' points to "
                    f"'{current}' which is not in framework_packages.yaml"
                )
            # The package itself is not in the list — no config_source
            return pkg_name
        nxt = entry.get("config_source")
        if not nxt:
            return current
        current = nxt


def pkg_yaml_path(repo_root: Path, pkg: str) -> Path:
    return repo_root / "infra" / pkg / "_config" / f"{pkg}.yaml"


def pkg_sops_path(repo_root: Path, pkg: str) -> Path:
    return repo_root / "infra" / pkg / "_config" / f"{pkg}_secrets.sops.yaml"
