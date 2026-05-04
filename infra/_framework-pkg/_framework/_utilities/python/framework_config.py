"""Load split framework_*.yaml config files into a unified dict.

Usage:
    from framework_config import load_framework_config, find_framework_config_dirs

    dirs = find_framework_config_dirs(git_root)
    fw = load_framework_config(dirs)
    bucket = fw["backend"]["config"]["bucket"]
"""
from __future__ import annotations
import os
from pathlib import Path

try:
    import yaml
except ImportError:
    raise ImportError("pyyaml not found — run: pip install pyyaml")


def find_framework_config_dirs(root: Path) -> list[Path]:
    """Return ordered list of config dirs containing framework_*.yaml files.

    Search order (lowest to highest priority):
      1. infra/_framework-pkg/_config/defaults/        framework defaults
      2. infra/$_FRAMEWORK_MAIN_PACKAGE/_config/overrides/  main package overrides (via $_MAIN_PKG_DIR)
      3. config/                                        ad-hoc/dev overrides

    Files in later dirs override same-named keys from earlier dirs.
    """
    dirs: list[Path] = []

    env_dir = os.environ.get("_FRAMEWORK_PKG_DIR")
    fw_cfg = Path(env_dir) / "_config" / "_framework_settings" if env_dir else root / "infra" / "_framework-pkg" / "_config" / "_framework_settings"
    if fw_cfg.is_dir():
        dirs.append(fw_cfg)

    config_pkg_dir = os.environ.get("_MAIN_PKG_DIR")
    if config_pkg_dir:
        pkg_cfg = Path(config_pkg_dir) / "_config" / "_framework_settings"
        if pkg_cfg.is_dir() and pkg_cfg not in dirs:
            dirs.append(pkg_cfg)

    override_cfg = root / "config"
    if override_cfg.is_dir() and override_cfg not in dirs:
        dirs.append(override_cfg)

    if not dirs:
        raise FileNotFoundError(f"Framework config dir not found: expected {fw_cfg}")
    return dirs


def find_framework_config_dir(root: Path) -> Path:
    """Backward-compat: return the primary (framework) config dir."""
    return find_framework_config_dirs(root)[0]


def fw_cfg_path(root: Path, filename: str) -> Path:
    """3-tier lookup for a single framework settings file.

    Priority (highest first):
      1. <root>/config/<filename>                                     per-dev override
      2. $_MAIN_PKG_DIR/_config/_framework_settings/<filename>  main package
      3. $_FRAMEWORK_PKG_DIR/_config/_framework_settings/<filename>          framework default

    Returns the path of the highest-priority file that exists, falling back to
    the framework default path even if it does not exist (caller decides how to handle).
    """
    override = root / "config" / filename
    if override.exists():
        return override
    config_pkg_dir = os.environ.get("_MAIN_PKG_DIR")
    if config_pkg_dir:
        candidate = Path(config_pkg_dir) / "_config" / "_framework_settings" / filename
        if candidate.exists():
            return candidate
    pkg_dir = os.environ.get("_FRAMEWORK_PKG_DIR") or str(root / "infra" / "_framework-pkg")
    return Path(pkg_dir) / "_config" / "_framework_settings" / filename


def load_framework_config(config_dir_or_dirs) -> dict:
    """Read all framework_*.yaml files and assemble a flat framework dict.

    Accepts a single Path (backward-compat) or a list of Paths.
    Files in later dirs override same-named keys from earlier dirs.
    Secrets files (containing 'secrets') are excluded.

    Example: framework_backend.yaml with top-level key framework_backend
    contributes {"backend": <value>} to the result.
    """
    if isinstance(config_dir_or_dirs, Path):
        dirs = [config_dir_or_dirs]
    else:
        dirs = list(config_dir_or_dirs)

    result: dict = {}
    for config_dir in dirs:
        for f in sorted(config_dir.glob("framework_*.yaml")):
            if "secrets" in f.name:
                continue
            try:
                raw = yaml.safe_load(f.read_text())
            except yaml.YAMLError:
                continue
            if not isinstance(raw, dict):
                continue
            for k, v in raw.items():
                if k.startswith("framework_"):
                    result[k[len("framework_"):]] = v
    return result
