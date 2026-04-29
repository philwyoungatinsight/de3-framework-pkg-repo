"""Read and write config_params keys in package YAML files using ruamel.yaml."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    from ruamel.yaml import YAML as _RuamelYAML
    _HAS_RUAMEL = True
except ImportError:
    _HAS_RUAMEL = False
    import yaml as _pyyaml


def _load_yaml(path: Path) -> tuple[Any, Any]:
    """Load YAML from path. Returns (data, yaml_instance).

    yaml_instance is either a ruamel.yaml.YAML instance (for round-trip) or None
    (for pyyaml). Caller must pass it back to _save_yaml.
    """
    if _HAS_RUAMEL:
        yml = _RuamelYAML()
        yml.preserve_quotes = True
        # Prevent anchor/alias generation — stops ruamel adding &id001/*id001 for identical dicts
        yml.representer.ignore_aliases = lambda *_: True
        # Prevent line-wrapping reformatting of long strings (match original style)
        yml.width = 4096
        with open(path, encoding="utf-8") as f:
            data = yml.load(f)
        return data, yml
    else:
        with open(path, encoding="utf-8") as f:
            data = _pyyaml.safe_load(f)
        return data, None


def _save_yaml(path: Path, data: Any, yml: Any) -> None:
    """Save data back to path atomically (tmp + os.replace)."""
    import io, os
    tmp = path.with_suffix(".tmp")
    if _HAS_RUAMEL and yml is not None:
        buf = io.StringIO()
        yml.dump(data, buf)
        tmp.write_text(buf.getvalue(), encoding="utf-8")
    else:
        tmp.write_text(
            _pyyaml.dump(data, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
    os.replace(tmp, path)


def migrate_config_params(
    src_yaml_path: Path,
    dst_yaml_path: Path,
    src_pkg: str,
    dst_pkg: str,
    src_rel: str,
    dst_rel: str,
    operation: str,  # "copy" or "move"
) -> int:
    """Migrate config_params keys from src_rel to dst_rel.

    For same-package operations: renames keys in-place in src_yaml_path.
    For cross-package operations: removes from src, inserts into dst.

    Returns the number of keys migrated.
    """
    is_cross_package = src_pkg != dst_pkg

    # Load source YAML
    src_data, src_yml = _load_yaml(src_yaml_path)
    if src_data is None:
        src_data = {}

    src_top = src_data.get(src_pkg, {})
    if src_top is None:
        src_top = {}
    src_config_params = src_top.get("config_params", {})
    if src_config_params is None:
        src_config_params = {}

    # Find matching keys
    keys_to_migrate = {
        k: v for k, v in src_config_params.items()
        if k == src_rel or k.startswith(src_rel + "/")
    }
    if not keys_to_migrate:
        return 0

    # Build renamed mapping
    renamed = {
        dst_rel + k[len(src_rel):]: v
        for k, v in keys_to_migrate.items()
    }

    if not is_cross_package:
        # Same package — rename keys in place
        cfg = src_top.get("config_params", {})
        if cfg is None:
            cfg = {}
        if operation == "move":
            old_to_new = {k: dst_rel + k[len(src_rel):] for k in keys_to_migrate}
            new_cfg = _rename_keys_inplace(cfg, old_to_new)
            src_top["config_params"] = new_cfg
            src_data[src_pkg] = src_top
            _save_yaml(src_yaml_path, src_data, src_yml)
        else:
            # copy: add new keys but keep old ones too
            for old_k in keys_to_migrate:
                new_k = dst_rel + old_k[len(src_rel):]
                cfg[new_k] = cfg[old_k]
            src_top["config_params"] = cfg
            src_data[src_pkg] = src_top
            _save_yaml(src_yaml_path, src_data, src_yml)
    else:
        # Cross-package — remove from src, add to dst
        if operation == "move":
            cfg = src_top.get("config_params", {}) or {}
            for k in keys_to_migrate:
                if k in cfg:
                    del cfg[k]
            src_top["config_params"] = cfg
            src_data[src_pkg] = src_top
            _save_yaml(src_yaml_path, src_data, src_yml)

        # Load and update destination YAML
        if dst_yaml_path.exists():
            dst_data, dst_yml = _load_yaml(dst_yaml_path)
            if dst_data is None:
                dst_data = {}
        else:
            dst_data = {dst_pkg: {"config_params": {}}}
            dst_yml = None

        dst_top = dst_data.get(dst_pkg, {})
        if dst_top is None:
            dst_top = {}
        dst_cfg = dst_top.get("config_params", {})
        if dst_cfg is None:
            dst_cfg = {}
        dst_cfg.update(renamed)
        dst_top["config_params"] = dst_cfg
        dst_data[dst_pkg] = dst_top
        _save_yaml(dst_yaml_path, dst_data, dst_yml)

    return len(keys_to_migrate)


def _rename_keys_inplace(cfg: Any, old_to_new: dict) -> Any:
    """Return a new ordered mapping with keys in old_to_new renamed.

    Keys not in old_to_new are passed through unchanged. Preserves insertion order.
    """
    if _HAS_RUAMEL:
        from ruamel.yaml.comments import CommentedMap
        result = CommentedMap()
        for k, v in cfg.items():
            result[old_to_new.get(k, k)] = v
        return result
    else:
        return {old_to_new.get(k, k): v for k, v in cfg.items()}
