# Plan: Refactor set_env.sh — Extract Inline Python to Named Helper

## Objective

`set_env.sh` currently embeds two heredoc Python snippets for YAML parsing, making it
an awkward blend of bash and Python. Extract those snippets into a small, named Python
helper (`read-set-env.py`) in `_utilities/python/`. `set_env.sh` stays pure bash and
gains two clean one-liner calls. No `.env` file or full Python rewrite — blast radius
is minimal and the sourcing contract is unchanged.

## Context

### The two inline Python snippets today

**Snippet 1** (lines 29–38): reads `_FRAMEWORK_CONFIG_PKG` from `config/_framework.yaml`.
```bash
_FRAMEWORK_CONFIG_PKG="$(python3 - "$_GIT_ROOT/config/_framework.yaml" <<'EOF'
import sys, yaml, pathlib
p = pathlib.Path(sys.argv[1])
try:
    d = yaml.safe_load(p.read_text()) if p.exists() else {}
    print((d or {}).get('_framework', {}).get('config_package', ''))
except Exception:
    print('')
EOF
)"
```

**Snippet 2** (lines 54–59): reads `_GCS_BUCKET` from the resolved backend YAML path.
```bash
_GCS_BUCKET="$(python3 - "$_fw_backend" <<'EOF'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
print(d["framework_backend"]["config"]["bucket"])
EOF
)"
```

### Why not use `framework_config.py`

`framework_config.py`'s `find_framework_config_dirs()` reads `_FRAMEWORK_CONFIG_PKG_DIR`
from the environment, but that var is only set *after* snippet 1 resolves it. Using
`framework_config.py` for snippet 1 would be circular. A standalone helper avoids the
ordering dependency entirely.

### Why not a `.env` file or full Python rewrite

`set_env.sh` is a framework contract file (symlinked into every consumer repo). Changing
the sourcing convention (e.g. `eval "$(python3 gen_env.py)"` or `. .env`) would require
updating every consumer repo, CI pipeline, and developer muscle memory. A helper script
called from within the existing bash structure carries no external impact.

### Ordering constraint

By the time each snippet runs, `_FRAMEWORK_DIR` is already exported (line 14). The
helper can be invoked as `python3 "$_FRAMEWORK_DIR/_utilities/python/read-set-env.py"`.
No venv needed — only stdlib + pyyaml (already required by `set_env.sh`).

---

## Open Questions

None — ready to proceed.

---

## Files to Create / Modify

### `_utilities/python/read-set-env.py` — create

New helper script. Two subcommands, each prints one value to stdout and exits.

```python
#!/usr/bin/env python3
"""Minimal YAML reader for set_env.sh — extracts two bootstrap values.

Usage:
  python3 read-set-env.py config-pkg <git_root>
      Reads config/_framework.yaml and prints _framework.config_package (or "").

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
        print((d or {}).get("_framework", {}).get("config_package", ""))
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
```

Make executable: `chmod +x _utilities/python/read-set-env.py`

---

### `_git_root/set_env.sh` — replace two heredocs with helper calls

Replace snippet 1 (lines 28–39 in the current file):
```bash
# Before:
if [[ -z "${_FRAMEWORK_CONFIG_PKG:-}" ]]; then
    export _FRAMEWORK_CONFIG_PKG
    _FRAMEWORK_CONFIG_PKG="$(python3 - "$_GIT_ROOT/config/_framework.yaml" <<'EOF'
import sys, yaml, pathlib
p = pathlib.Path(sys.argv[1])
try:
    d = yaml.safe_load(p.read_text()) if p.exists() else {}
    print((d or {}).get('_framework', {}).get('config_package', ''))
except Exception:
    print('')
EOF
)"
fi

# After:
if [[ -z "${_FRAMEWORK_CONFIG_PKG:-}" ]]; then
    export _FRAMEWORK_CONFIG_PKG
    _FRAMEWORK_CONFIG_PKG="$(python3 "$_FRAMEWORK_DIR/_utilities/python/read-set-env.py" config-pkg "$_GIT_ROOT")"
fi
```

Replace snippet 2 (lines 53–59 in the current file):
```bash
# Before:
export _GCS_BUCKET
_GCS_BUCKET="$(python3 - "$_fw_backend" <<'EOF'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
print(d["framework_backend"]["config"]["bucket"])
EOF
)"

# After:
export _GCS_BUCKET
_GCS_BUCKET="$(python3 "$_FRAMEWORK_DIR/_utilities/python/read-set-env.py" gcs-bucket "$_fw_backend")"
```

---

## Execution Order

Both files are in de3-runner (`_ext_packages/de3-runner/main`):

1. Create `infra/_framework-pkg/_framework/_utilities/python/read-set-env.py`.
2. Update `infra/_framework-pkg/_framework/_git_root/set_env.sh` — replace both heredocs.
3. Test: `source set_env.sh && echo "_FRAMEWORK_CONFIG_PKG=$_FRAMEWORK_CONFIG_PKG" && echo "_GCS_BUCKET=$_GCS_BUCKET"`
4. Commit both files together in de3-runner.

## Verification

```bash
# Source in the consumer repo and confirm the two key vars are set
source /home/pyoung/git/pwy-home-lab-pkg/set_env.sh
echo "config_pkg:  $_FRAMEWORK_CONFIG_PKG"
echo "gcs_bucket:  $_GCS_BUCKET"

# Confirm no heredoc Python remains in set_env.sh
grep -n "<<'EOF'" infra/_framework-pkg/_framework/_git_root/set_env.sh

# Confirm helper is callable standalone
python3 infra/_framework-pkg/_framework/_utilities/python/read-set-env.py \
  config-pkg /home/pyoung/git/pwy-home-lab-pkg
python3 infra/_framework-pkg/_framework/_utilities/python/read-set-env.py \
  gcs-bucket infra/_framework-pkg/_config/_framework_settings/framework_backend.yaml
```
