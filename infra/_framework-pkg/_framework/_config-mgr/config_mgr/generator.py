"""Generate pre-merged config and encrypted SOPS copies into $_CONFIG_DIR."""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from .merger import merge_config_params
from .packages import (
    load_framework_config_mgr,
    load_framework_packages,
    pkg_sops_path,
    pkg_yaml_path,
    resolve_config_source,
)

try:
    from ruamel.yaml import YAML as _RuamelYAML
    _HAS_RUAMEL = True
except ImportError:
    _HAS_RUAMEL = False


_MANIFEST_FILE = ".manifest"


def _load_manifest(config_dir: Path) -> dict:
    manifest_path = config_dir / _MANIFEST_FILE
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text()) or {}
    except Exception:
        return {}


def _save_manifest(config_dir: Path, manifest: dict) -> None:
    tmp = config_dir / (_MANIFEST_FILE + ".tmp")
    tmp.write_text(json.dumps(manifest, indent=2))
    os.replace(tmp, config_dir / _MANIFEST_FILE)


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except FileNotFoundError:
        return -1.0


def _is_stale(pkg_name: str, source_files: list[Path], manifest: dict) -> bool:
    """Return True if any source file has changed since last generation."""
    entry = manifest.get(pkg_name, {})
    for f in source_files:
        key = str(f)
        recorded = entry.get(key, -2.0)
        if _mtime(f) != recorded:
            return True
    return False


def _manifest_entry(source_files: list[Path]) -> dict:
    return {str(f): _mtime(f) for f in source_files}


def _load_yaml_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        raise RuntimeError(f"YAML parse error in {path}: {e}") from e


def _copy_file(src: Path, dst: Path) -> None:
    """Atomically copy src to dst."""
    tmp = dst.with_suffix(".tmp")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


def _dump_yaml(data: Any, path: Path) -> None:
    """Write data to path atomically, using ruamel.yaml if available."""
    tmp = path.with_suffix(".tmp")
    if _HAS_RUAMEL:
        yml = _RuamelYAML()
        yml.preserve_quotes = True
        yml.representer.ignore_aliases = lambda *_: True
        yml.width = 4096
        buf = io.StringIO()
        yml.dump(data, buf)
        tmp.write_text(buf.getvalue(), encoding="utf-8")
    else:
        tmp.write_text(
            yaml.dump(data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
    os.replace(tmp, path)


def _get_config_params(top_level_data: dict, pkg_name: str) -> dict:
    """Extract config_params from a package YAML's top-level key."""
    pkg_section = top_level_data.get(pkg_name, {}) or {}
    return pkg_section.get("config_params", {}) or {}


def _filter_config_params_for_pkg(config_params: dict, pkg_name: str) -> dict:
    """Return only config_params entries that belong to pkg_name.

    Keeps keys equal to pkg_name (top-level ancestor) or starting with pkg_name/.
    This prevents cross-package key pollution in output files.
    """
    prefix = pkg_name + "/"
    return {
        k: v for k, v in config_params.items()
        if k == pkg_name or k.startswith(prefix)
    }


def _build_output_yaml(
    pkg_name: str,
    own_data: dict,
    merged_config_params: dict,
) -> dict:
    """Build the output YAML preserving all top-level keys except config_params."""
    pkg_section = dict(own_data.get(pkg_name, {}) or {})
    pkg_section["config_params"] = merged_config_params
    return {pkg_name: pkg_section}


def generate(repo_root: Path, config_dir: Path, output_mode: str | None = None) -> None:
    """Generate pre-merged config into config_dir.

    output_mode overrides the setting from framework_config_mgr.yaml when provided.
    Exits non-zero on any error (SOPS failure, missing package, etc.).
    """
    packages = load_framework_packages(repo_root)
    cfg_mgr = load_framework_config_mgr(repo_root)

    merge_method = cfg_mgr.get("merge_method", "interleave")
    effective_mode = output_mode or cfg_mgr.get("output_mode", "normal")

    config_dir.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(config_dir)

    # Remove legacy plaintext secrets files (replaced by .secrets.sops.yaml copies)
    for legacy in config_dir.glob("*.secrets.yaml"):
        legacy.unlink()
        if effective_mode in ("normal", "verbose"):
            print(f"config-mgr: removed legacy plaintext secrets file {legacy.name}", flush=True)

    pkg_map = {p["name"]: p for p in packages}
    errors: list[str] = []

    for pkg_entry in packages:
        pkg_name = pkg_entry["name"]

        # Determine config_source terminal (follows chains)
        try:
            config_source_name = resolve_config_source(pkg_name, packages)
        except ValueError as e:
            errors.append(str(e))
            continue

        has_config_source = config_source_name != pkg_name

        # Collect source files to watch for staleness
        own_yaml = pkg_yaml_path(repo_root, pkg_name)
        own_sops = pkg_sops_path(repo_root, pkg_name)
        source_files = [f for f in [own_yaml, own_sops] if True]  # always track

        if has_config_source:
            cs_yaml = pkg_yaml_path(repo_root, config_source_name)
            cs_sops = pkg_sops_path(repo_root, config_source_name)
            source_files += [cs_yaml, cs_sops]

        # Only track files that exist for staleness (non-existent → -1.0, always stale if appears)
        stale = _is_stale(pkg_name, source_files, manifest)
        # Also stale if the output file is missing (e.g. _CONFIG_DIR was wiped after last run)
        if not stale and not (config_dir / f"{pkg_name}.yaml").exists():
            stale = True
        # Also stale if expected SOPS copy is missing
        _expected_sops_dest = config_dir / f"{pkg_name}.secrets.sops.yaml"
        _has_sops_src = own_sops.exists() or (
            has_config_source and pkg_sops_path(repo_root, config_source_name).exists()
        )
        if not stale and _has_sops_src and not _expected_sops_dest.exists():
            stale = True
        if not stale:
            if effective_mode == "verbose":
                print(f"config-mgr: {pkg_name} up to date", flush=True)
            continue

        # Load own public config
        if not own_yaml.exists():
            if effective_mode == "verbose":
                print(f"config-mgr: {pkg_name} — no config file, skipping", flush=True)
            manifest[pkg_name] = _manifest_entry(source_files)
            continue

        try:
            own_data = _load_yaml_file(own_yaml)
        except RuntimeError as e:
            errors.append(str(e))
            continue

        # Filter own config_params to only keys belonging to this package
        own_config_params = _filter_config_params_for_pkg(
            _get_config_params(own_data, pkg_name), pkg_name
        )

        # Load config_source public config
        cs_config_params: dict = {}
        cs_data: dict = {}
        if has_config_source:
            cs_path = pkg_yaml_path(repo_root, config_source_name)
            if cs_path.exists():
                try:
                    cs_data = _load_yaml_file(cs_path)
                except RuntimeError as e:
                    errors.append(str(e))
                    continue
                # Filter cs config_params to only keys belonging to this package
                cs_config_params = _filter_config_params_for_pkg(
                    _get_config_params(cs_data, config_source_name), pkg_name
                )

        # Merge config_params (per merge_method)
        # Per-package override of merge_method via config_merge_method in framework_packages.yaml
        pkg_merge_method = pkg_entry.get("config_merge_method", merge_method)
        merged_params = merge_config_params(
            own_config_params, cs_config_params, pkg_merge_method
        )

        # Write public output YAML
        output_data = _build_output_yaml(pkg_name, own_data, merged_params)
        out_yaml = config_dir / f"{pkg_name}.yaml"
        try:
            _dump_yaml(output_data, out_yaml)
        except Exception as e:
            errors.append(f"Failed to write {out_yaml}: {e}")
            continue

        # Secrets: copy encrypted SOPS file — never decrypt to disk.
        # own_sops takes precedence; fall back to config_source's SOPS if own is absent.
        sops_dest = config_dir / f"{pkg_name}.secrets.sops.yaml"
        _sops_src: Path | None = None
        if own_sops.exists():
            _sops_src = own_sops
        elif has_config_source and cs_sops.exists():
            _sops_src = cs_sops
        if _sops_src is not None:
            try:
                _copy_file(_sops_src, sops_dest)
            except Exception as e:
                errors.append(f"Failed to copy SOPS file to {sops_dest}: {e}")
                continue
        elif sops_dest.exists():
            sops_dest.unlink()

        manifest[pkg_name] = _manifest_entry(source_files)
        if effective_mode in ("normal", "verbose"):
            print(f"config-mgr: regenerated {pkg_name}", flush=True)

    if errors:
        for e in errors:
            print(f"config-mgr ERROR: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

    _save_manifest(config_dir, manifest)
