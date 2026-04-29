#!/usr/bin/env python3
"""Minimal YAML reader for set_env.sh — extracts two bootstrap values.

Usage:
  python3 read-set-env.py config-pkg <git_root>
      Reads config/_framework.yaml and prints _framework.main_package (or "").

  python3 read-set-env.py gcs-bucket <backend_yaml_path>
      Reads the given backend YAML and prints framework_backend.config.bucket.
"""
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("", flush=True)
    sys.exit(0)


def cmd_config_pkg(git_root: str) -> None:
    p = Path(git_root) / "config" / "_framework.yaml"
    try:
        d = yaml.safe_load(p.read_text()) if p.exists() else {}
        print((d or {}).get("_framework", {}).get("main_package", ""))
    except Exception:
        print("")


def cmd_gcs_bucket(backend_yaml: str) -> None:
    try:
        d = yaml.safe_load(Path(backend_yaml).read_text())
        print(d["framework_backend"]["config"]["bucket"])
    except Exception as e:
        print(f"ERROR: could not read GCS bucket from {backend_yaml}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} config-pkg <git_root>", file=sys.stderr)
        print(f"       {sys.argv[0]} gcs-bucket <backend_yaml>", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    arg = sys.argv[2]
    if cmd == "config-pkg":
        cmd_config_pkg(arg)
    elif cmd == "gcs-bucket":
        cmd_gcs_bucket(arg)
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)
