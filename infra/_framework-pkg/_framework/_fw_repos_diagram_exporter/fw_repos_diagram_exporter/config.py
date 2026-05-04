"""Config loading for fw-repos-diagram-exporter."""
from __future__ import annotations
import os
import subprocess
from pathlib import Path

import yaml


def _fw_cfg_path(repo_root: Path, filename: str) -> Path:
    """Inline 3-tier lookup (mirrors packages.py — no cross-tool import)."""
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


def repo_root() -> Path:
    fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
    if fw_pkg:
        return Path(fw_pkg).parent.parent
    r = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return Path(r.stdout.strip())


def load_config() -> dict:
    root = repo_root()
    path = _fw_cfg_path(root, "framework_repos_diagram_exporter.yaml")
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text()) or {}
    return raw.get("framework_repos_diagram_exporter", {})


def state_dir() -> Path:
    return repo_root() / "config" / "tmp" / "fw_repos_diagram_exporter"
