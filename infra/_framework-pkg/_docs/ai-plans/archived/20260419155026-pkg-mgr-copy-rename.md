# Plan: pkg-mgr copy/rename Commands

## Objective

Add `rename <src-pkg> <dst-pkg>` and `copy <src-pkg> <dst-pkg>` commands to
`framework/pkg-mgr/run`. These move or duplicate an entire package directory,
keeping the config YAML, SOPS secrets, GCS state, and internal Terragrunt
dependency references in sync — the same guarantees that unit-mgr provides for
individual units, but applied at the package level.

## Context

### Why not call unit-mgr?

unit-mgr is designed for unit subtrees **within** a package (paths like
`my-pkg/_stack/gcp/us-central1/bucket`). When a whole package is the src/dst,
unit-mgr triggers its cross-package logic and writes migrated config_params into
a **new** `infra/<dst>/_config/<dst>.yaml` file while leaving the original
`infra/<dst>/_config/<src>.yaml` mostly intact — producing two split config
files instead of one renamed one. The package-level config file rename (e.g.
`old-pkg.yaml → new-pkg.yaml`) and top-level YAML key rename (`old-pkg:` →
`new-pkg:`) are also outside unit-mgr's scope.

pkg-mgr therefore implements all phases directly in-script (same approach as
every other pkg-mgr command: pure bash + inline Python heredocs, no module
dependencies).

### Package types

Two types exist; they need different handling:

| Type | `infra/<pkg>` is | Source of truth |
|------|-----------------|-----------------|
| **Local** | Real directory | This repo |
| **Imported** | Symlink → `_ext_packages/<repo>/…` | External repo |

For **imported** packages, `rename` just renames the symlink and updates
`framework_packages.yaml`. No config/GCS work is needed — the external code is
not touched. `copy` creates a second symlink alias.

For **local** packages, both commands must handle:
1. Filesystem rename/copy
2. Config file rename (`<src>.yaml` → `<dst>.yaml`) + top-level key rename
3. SOPS secrets file rename + top-level key rename (decrypt → rename → re-encrypt)
4. `config_params` key migration inside both YAML files (`<src>/…` → `<dst>/…`)
5. Internal dep patch — string substitution in all `.hcl` files under the new dir
6. External dep scan — report `.hcl` files outside the package that reference old paths
7. GCS state migration (one gsutil cp+rm per state file)
8. `framework_packages.yaml` entry update

### GCS bucket source

Read from `config/framework.yaml` at `framework.backend.config.bucket`, same
path unit-mgr uses. If the backend is not `gcs` or bucket is absent, skip state
migration silently (same graceful-skip behaviour as unit-mgr).

### SOPS rule

NEVER use shell redirect (`>`) or Write/Edit tools on `.sops.yaml` files.
For key-rename: decrypt to a temp file → edit in Python → `git mv` old path →
`sops --encrypt --output <new-path> <temp-file>` → `rm <temp-file>`.

## Open Questions

None — all answered:

1. **Imported package `copy`**: Create a second symlink alias (OK).
2. **GCS state for `copy`**: `--skip-state` / `--with-state` are both required;
   omitting either is an error. No default — the caller must always be explicit.
3. **GUI integration**: Add Rename and Copy buttons to the GUI packages panel.

## Files to Create / Modify

### `framework/pkg-mgr/run` — modify

Add the following in order inside the file.

#### New helpers (add after the existing `_yaml_write_key` helper, before the Commands section)

```bash
# Read GCS bucket from config/framework.yaml (returns empty string if not gcs backend)
_gcs_bucket() {
  python3 -c "
import yaml, pathlib
cfg_path = pathlib.Path('$GIT_ROOT/config/framework.yaml')
if not cfg_path.exists():
    print(''); exit(0)
cfg = yaml.safe_load(cfg_path.read_text()) or {}
backend = cfg.get('framework', {}).get('backend', {})
if backend.get('type') != 'gcs':
    print(''); exit(0)
print(backend.get('config', {}).get('bucket', ''))
" 2>/dev/null || true
}

# Fail if any GCS locks exist under infra/<pkg>/
_check_gcs_locks_for_pkg() {
  local pkg="$1"
  local bucket; bucket=$(_gcs_bucket)
  [[ -z "$bucket" ]] && return 0
  local locked
  locked=$(gsutil ls -r "gs://$bucket/$pkg/" 2>/dev/null | grep '\.tflock$' | head -5 || true)
  if [[ -n "$locked" ]]; then
    echo "ERROR: GCS locks found under $pkg/ — resolve them before rename:" >&2
    echo "$locked" >&2; exit 1
  fi
}

# Migrate all GCS state files from src/ prefix to dst/ prefix
# dry_run=true prints actions without executing
_migrate_pkg_gcs_state() {
  local src="$1" dst="$2" dry_run="${3:-false}"
  local bucket; bucket=$(_gcs_bucket)
  if [[ -z "$bucket" ]]; then
    echo "  GCS state: no gcs backend configured — skipping"; return 0
  fi
  local state_files
  state_files=$(gsutil ls -r "gs://$bucket/$src/" 2>/dev/null \
    | grep -E '\.(tfstate|tflock)$' || true)
  if [[ -z "$state_files" ]]; then
    echo "  GCS state: nothing to migrate (no state under $src/)"; return 0
  fi
  local count=0
  while IFS= read -r src_path; do
    local rel="${src_path#gs://$bucket/$src/}"
    local dst_path="gs://$bucket/$dst/$rel"
    if [[ "$dry_run" == true ]]; then
      echo "  [dry-run] gsutil cp $src_path $dst_path && gsutil rm $src_path"
    else
      gsutil -q cp "$src_path" "$dst_path"
      gsutil -q rm "$src_path"
      (( count++ )) || true
    fi
  done <<< "$state_files"
  [[ "$dry_run" == false ]] && echo "  GCS state: migrated $count file(s)"
}

# Rename top-level YAML key and config_params sub-keys in a plain YAML file.
# Uses ruamel.yaml if available (preserves comments), falls back to pyyaml.
_rename_pkg_yaml_keys() {
  local yaml_file="$1" src_name="$2" dst_name="$3"
  [[ -f "$yaml_file" ]] || return 0
  python3 - "$yaml_file" "$src_name" "$dst_name" <<'PYEOF'
import sys, pathlib, os
cfg_path = pathlib.Path(sys.argv[1])
src_name, dst_name = sys.argv[2], sys.argv[3]
try:
    from ruamel.yaml import YAML as _YAML
    import io as _io
    _y = _YAML(); _y.preserve_quotes = True
    def _load(p): return _y.load(p.read_text())
    def _dump(d, p):
        buf = _io.StringIO(); _y.dump(d, buf)
        tmp = p.with_suffix('.tmp'); tmp.write_text(buf.getvalue()); os.replace(tmp, p)
except ImportError:
    import yaml as _yaml
    def _load(p): return _yaml.safe_load(p.read_text()) or {}
    def _dump(d, p):
        tmp = p.with_suffix('.tmp')
        tmp.write_text(_yaml.dump(d, allow_unicode=True, default_flow_style=False))
        os.replace(tmp, p)

data = _load(cfg_path)
if src_name not in data:
    sys.exit(0)
pkg_data = data.pop(src_name)
data[dst_name] = pkg_data

cp = pkg_data.get('config_params') or {}
prefix = src_name + '/'
new_cp = {}
for k, v in list(cp.items()):
    new_cp[(dst_name + '/' + k[len(prefix):]) if k.startswith(prefix) else k] = v
if new_cp:
    pkg_data['config_params'] = new_cp

_dump(data, cfg_path)
PYEOF
}
```

#### New command: `_cmd_rename`

```bash
_cmd_rename() {
  local src="${1:-}" dst="${2:-}"
  shift 2 || true
  local dry_run=false skip_state=false
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run)    dry_run=true ;;
      --skip-state) skip_state=true ;;
      *) echo "ERROR: unknown option: $1" >&2; exit 1 ;;
    esac; shift
  done
  if [[ -z "$src" || -z "$dst" ]]; then
    echo "Usage: pkg-mgr rename <src-pkg> <dst-pkg> [--dry-run] [--skip-state]" >&2; exit 1
  fi

  local src_dir="$INFRA_DIR/$src" dst_dir="$INFRA_DIR/$dst"

  # ---- Imported package (symlink) ----
  if [[ -L "$src_dir" ]]; then
    [[ -e "$dst_dir" ]] && { echo "ERROR: infra/$dst already exists" >&2; exit 1; }
    local target; target=$(readlink "$src_dir")
    if [[ "$dry_run" == true ]]; then
      echo "[dry-run] rename symlink: infra/$src → infra/$dst (→ $target)"
      return 0
    fi
    rm "$src_dir"; ln -s "$target" "$dst_dir"
    echo "  symlink: infra/$src → infra/$dst"
    python3 - "$FRAMEWORK_PKGS_CFG" "$src" "$dst" <<'PYEOF'
import yaml, sys, pathlib, os
cfg = pathlib.Path(sys.argv[1]); src_n, dst_n = sys.argv[2], sys.argv[3]
d = yaml.safe_load(cfg.read_text()) or {}
pkgs = d.get("framework_packages", [])
for p in pkgs:
    if p.get("name") == src_n: p["name"] = dst_n; break
d["framework_packages"] = pkgs
tmp = cfg.with_suffix(".tmp")
tmp.write_text(yaml.dump(d, allow_unicode=True, default_flow_style=False))
os.replace(tmp, cfg)
print(f"  framework_packages.yaml: '{src_n}' → '{dst_n}'")
PYEOF
    echo "==> rename complete (imported): $src → $dst"
    return 0
  fi

  # ---- Local package (real directory) ----
  [[ ! -d "$src_dir" ]] && { echo "ERROR: infra/$src does not exist" >&2; exit 1; }
  [[ -e "$dst_dir" ]] && { echo "ERROR: infra/$dst already exists" >&2; exit 1; }
  [[ "$skip_state" == false ]] && _check_gcs_locks_for_pkg "$src"

  echo "==> pkg-mgr rename $src → $dst"

  # Phase 1: Filesystem
  if [[ "$dry_run" == true ]]; then
    echo "  [dry-run] git mv infra/$src infra/$dst"
  else
    git -C "$GIT_ROOT" mv "infra/$src" "infra/$dst"
    echo "  filesystem: infra/$src → infra/$dst"
  fi

  # Phase 2: Config file rename
  local old_cfg="$dst_dir/_config/${src}.yaml"
  local new_cfg="$dst_dir/_config/${dst}.yaml"
  if [[ "$dry_run" == true ]]; then
    [[ -f "$old_cfg" ]] && echo "  [dry-run] git mv _config/${src}.yaml _config/${dst}.yaml + rename key"
  elif [[ -f "$old_cfg" ]]; then
    git -C "$GIT_ROOT" mv "infra/$dst/_config/${src}.yaml" "infra/$dst/_config/${dst}.yaml"
    _rename_pkg_yaml_keys "$new_cfg" "$src" "$dst"
    echo "  config YAML: ${src}.yaml → ${dst}.yaml (key renamed)"
  fi

  # Phase 3: SOPS secrets file rename + key update
  local old_sops="$dst_dir/_config/${src}_secrets.sops.yaml"
  local new_sops="$dst_dir/_config/${dst}_secrets.sops.yaml"
  if [[ "$dry_run" == true ]]; then
    [[ -f "$old_sops" ]] && echo "  [dry-run] rename ${src}_secrets.sops.yaml → ${dst}_secrets.sops.yaml + re-key"
  elif [[ -f "$old_sops" ]]; then
    local tmp_sops; tmp_sops=$(mktemp /tmp/pkg-mgr-sops-XXXXXX.yaml)
    sops --decrypt "$old_sops" > "$tmp_sops"
    # Rename top-level key: <src>_secrets → <dst>_secrets (and config_params sub-keys)
    python3 - "$tmp_sops" "${src}_secrets" "${dst}_secrets" "$src" "$dst" <<'PYEOF'
import sys, yaml, pathlib, os
p = pathlib.Path(sys.argv[1]); old_key, new_key = sys.argv[2], sys.argv[3]
src_n, dst_n = sys.argv[4], sys.argv[5]
d = yaml.safe_load(p.read_text()) or {}
if old_key in d:
    pkg_data = d.pop(old_key); d[new_key] = pkg_data
    cp = pkg_data.get('config_params') or {}
    prefix = src_n + '/'
    new_cp = {}
    for k, v in cp.items():
        new_cp[(dst_n + '/' + k[len(prefix):]) if k.startswith(prefix) else k] = v
    if new_cp: pkg_data['config_params'] = new_cp
tmp = p.with_suffix('.tmp')
tmp.write_text(yaml.dump(d, allow_unicode=True, default_flow_style=False))
os.replace(tmp, p)
PYEOF
    git -C "$GIT_ROOT" mv "infra/$dst/_config/${src}_secrets.sops.yaml" \
                          "infra/$dst/_config/${dst}_secrets.sops.yaml"
    sops --encrypt --output "$new_sops" "$tmp_sops"
    rm "$tmp_sops"
    echo "  secrets: ${src}_secrets.sops.yaml → ${dst}_secrets.sops.yaml (key re-encrypted)"
  fi

  # Phase 4: Patch internal .hcl deps
  if [[ "$dry_run" == false ]]; then
    python3 - "$dst_dir" "$src" "$dst" <<'PYEOF'
import sys, pathlib
dst_dir = pathlib.Path(sys.argv[1]); src_n, dst_n = sys.argv[2], sys.argv[3]
old_s, new_s = f"infra/{src_n}/", f"infra/{dst_n}/"
count = 0
for hcl in dst_dir.rglob("*.hcl"):
    if ".terragrunt-cache" in str(hcl): continue
    txt = hcl.read_text()
    if old_s in txt:
        hcl.write_text(txt.replace(old_s, new_s)); count += 1
print(f"  internal deps: patched {count} .hcl file(s)")
PYEOF
  fi

  # Phase 5: Scan for external dep warnings
  python3 - "$INFRA_DIR" "$src" "$dst" "$dry_run" <<'PYEOF'
import sys, pathlib
infra_dir = pathlib.Path(sys.argv[1]); src_n, dst_n = sys.argv[2], sys.argv[3]
old_prefix = f"infra/{src_n}/"
warnings = []
for hcl in infra_dir.rglob("*.hcl"):
    rel = str(hcl.relative_to(infra_dir))
    if ".terragrunt-cache" in rel or rel.startswith(f"{dst_n}/"): continue
    for i, ln in enumerate(hcl.read_text().splitlines(), 1):
        if old_prefix in ln:
            warnings.append(f"  {rel}:{i}: {ln.strip()}")
if warnings:
    print(f"\nWARNING: {len(warnings)} external reference(s) to infra/{src_n}/ need manual update:")
    for w in warnings: print(w)
PYEOF

  # Phase 6: GCS state
  if [[ "$skip_state" == false ]]; then
    _migrate_pkg_gcs_state "$src" "$dst" "$dry_run"
  else
    echo "  GCS state: skipped (--skip-state)"
  fi

  # Phase 7: framework_packages.yaml
  if [[ "$dry_run" == false ]]; then
    python3 - "$FRAMEWORK_PKGS_CFG" "$src" "$dst" <<'PYEOF'
import yaml, sys, pathlib, os
cfg = pathlib.Path(sys.argv[1]); src_n, dst_n = sys.argv[2], sys.argv[3]
d = yaml.safe_load(cfg.read_text()) or {}
pkgs = d.get("framework_packages", [])
for p in pkgs:
    if p.get("name") == src_n: p["name"] = dst_n; break
d["framework_packages"] = pkgs
tmp = cfg.with_suffix(".tmp")
tmp.write_text(yaml.dump(d, allow_unicode=True, default_flow_style=False))
os.replace(tmp, cfg)
print(f"  framework_packages.yaml: '{src_n}' → '{dst_n}'")
PYEOF
  fi

  echo "==> rename complete: $src → $dst"
}
```

#### New command: `_cmd_copy`

```bash
_cmd_copy() {
  local src="${1:-}" dst="${2:-}"
  shift 2 || true
  local dry_run=false state_flag=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run)    dry_run=true ;;
      --skip-state) state_flag="skip" ;;
      --with-state) state_flag="with" ;;
      *) echo "ERROR: unknown option: $1" >&2; exit 1 ;;
    esac; shift
  done
  if [[ -z "$src" || -z "$dst" ]]; then
    echo "Usage: pkg-mgr copy <src-pkg> <dst-pkg> [--dry-run] --skip-state|--with-state" >&2; exit 1
  fi
  if [[ "$dry_run" == false && -z "$state_flag" ]]; then
    echo "ERROR: copy requires --skip-state or --with-state" >&2
    echo "  --skip-state : copy filesystem only; new package starts with no deployed state" >&2
    echo "  --with-state : also copy GCS Terraform state blobs (two packages share state)" >&2
    exit 1
  fi

  local src_dir="$INFRA_DIR/$src" dst_dir="$INFRA_DIR/$dst"

  # ---- Imported package (symlink) ----
  if [[ -L "$src_dir" ]]; then
    [[ -e "$dst_dir" ]] && { echo "ERROR: infra/$dst already exists" >&2; exit 1; }
    local target; target=$(readlink "$src_dir")
    if [[ "$dry_run" == true ]]; then
      echo "  [dry-run] create symlink: infra/$dst → $target"
      return 0
    fi
    ln -s "$target" "$dst_dir"; echo "  symlink: infra/$dst → $target"
    python3 - "$FRAMEWORK_PKGS_CFG" "$src" "$dst" <<'PYEOF'
import yaml, sys, pathlib, os, copy
cfg = pathlib.Path(sys.argv[1]); src_n, dst_n = sys.argv[2], sys.argv[3]
d = yaml.safe_load(cfg.read_text()) or {}
pkgs = d.get("framework_packages", [])
src_entry = next((copy.deepcopy(p) for p in pkgs if p.get("name") == src_n), None)
if src_entry:
    src_entry["name"] = dst_n; pkgs.append(src_entry)
d["framework_packages"] = pkgs
tmp = cfg.with_suffix(".tmp")
tmp.write_text(yaml.dump(d, allow_unicode=True, default_flow_style=False))
os.replace(tmp, cfg)
print(f"  framework_packages.yaml: added '{dst_n}'")
PYEOF
    echo "==> copy complete (imported): $src → $dst"
    return 0
  fi

  # ---- Local package ----
  [[ ! -d "$src_dir" ]] && { echo "ERROR: infra/$src does not exist" >&2; exit 1; }
  [[ -e "$dst_dir" ]] && { echo "ERROR: infra/$dst already exists" >&2; exit 1; }

  echo "==> pkg-mgr copy $src → $dst"

  # Phase 1: Filesystem copy
  if [[ "$dry_run" == true ]]; then
    echo "  [dry-run] cp -r infra/$src infra/$dst (then delete .terragrunt-cache/)"
  else
    cp -r "$src_dir" "$dst_dir"
    find "$dst_dir" -type d -name ".terragrunt-cache" -exec rm -rf {} + 2>/dev/null || true
    git -C "$GIT_ROOT" add "infra/$dst"
    echo "  filesystem: copied infra/$src → infra/$dst"
  fi

  # Phase 2: Config file rename in dst
  local old_cfg="$dst_dir/_config/${src}.yaml"
  local new_cfg="$dst_dir/_config/${dst}.yaml"
  if [[ "$dry_run" == true ]]; then
    [[ -f "$old_cfg" ]] && echo "  [dry-run] rename _config/${src}.yaml → _config/${dst}.yaml + rename key"
  elif [[ -f "$old_cfg" ]]; then
    mv "$old_cfg" "$new_cfg"
    git -C "$GIT_ROOT" add "infra/$dst/_config/${dst}.yaml"
    _rename_pkg_yaml_keys "$new_cfg" "$src" "$dst"
    echo "  config YAML: ${src}.yaml → ${dst}.yaml (key renamed)"
  fi

  # Phase 3: SOPS secrets copy + rename
  local old_sops="$dst_dir/_config/${src}_secrets.sops.yaml"
  local new_sops="$dst_dir/_config/${dst}_secrets.sops.yaml"
  if [[ "$dry_run" == true ]]; then
    [[ -f "$old_sops" ]] && echo "  [dry-run] copy + re-key ${src}_secrets.sops.yaml → ${dst}_secrets.sops.yaml"
  elif [[ -f "$old_sops" ]]; then
    local tmp_sops; tmp_sops=$(mktemp /tmp/pkg-mgr-sops-XXXXXX.yaml)
    sops --decrypt "$old_sops" > "$tmp_sops"
    python3 - "$tmp_sops" "${src}_secrets" "${dst}_secrets" "$src" "$dst" <<'PYEOF'
import sys, yaml, pathlib, os
p = pathlib.Path(sys.argv[1]); old_key, new_key = sys.argv[2], sys.argv[3]
src_n, dst_n = sys.argv[4], sys.argv[5]
d = yaml.safe_load(p.read_text()) or {}
if old_key in d:
    pkg_data = d.pop(old_key); d[new_key] = pkg_data
    cp = pkg_data.get('config_params') or {}
    prefix = src_n + '/'
    new_cp = {}
    for k, v in cp.items():
        new_cp[(dst_n + '/' + k[len(prefix):]) if k.startswith(prefix) else k] = v
    if new_cp: pkg_data['config_params'] = new_cp
tmp = p.with_suffix('.tmp')
tmp.write_text(yaml.dump(d, allow_unicode=True, default_flow_style=False))
os.replace(tmp, p)
PYEOF
    rm "$old_sops"
    sops --encrypt --output "$new_sops" "$tmp_sops"
    rm "$tmp_sops"
    git -C "$GIT_ROOT" add "infra/$dst/_config/${dst}_secrets.sops.yaml"
    echo "  secrets: ${dst}_secrets.sops.yaml (re-keyed copy)"
  fi

  # Phase 4: Patch internal .hcl deps in dst tree
  if [[ "$dry_run" == false ]]; then
    python3 - "$dst_dir" "$src" "$dst" <<'PYEOF'
import sys, pathlib
dst_dir = pathlib.Path(sys.argv[1]); src_n, dst_n = sys.argv[2], sys.argv[3]
old_s, new_s = f"infra/{src_n}/", f"infra/{dst_n}/"
count = 0
for hcl in dst_dir.rglob("*.hcl"):
    if ".terragrunt-cache" in str(hcl): continue
    txt = hcl.read_text()
    if old_s in txt:
        hcl.write_text(txt.replace(old_s, new_s)); count += 1
print(f"  internal deps: patched {count} .hcl file(s)")
PYEOF
  fi

  # Phase 5: GCS state (caller must have specified --skip-state or --with-state)
  if [[ "$state_flag" == "with" ]]; then
    _migrate_pkg_gcs_state "$src" "$dst" "$dry_run"
  else
    echo "  GCS state: skipped (--skip-state)"
  fi

  # Phase 6: framework_packages.yaml
  if [[ "$dry_run" == false ]]; then
    python3 - "$FRAMEWORK_PKGS_CFG" "$src" "$dst" <<'PYEOF'
import yaml, sys, pathlib, os, copy as _copy
cfg = pathlib.Path(sys.argv[1]); src_n, dst_n = sys.argv[2], sys.argv[3]
d = yaml.safe_load(cfg.read_text()) or {}
pkgs = d.get("framework_packages", [])
src_entry = next((_copy.deepcopy(p) for p in pkgs if p.get("name") == src_n), {"name": src_n, "public": False})
src_entry["name"] = dst_n
pkgs.append(src_entry)
d["framework_packages"] = pkgs
tmp = cfg.with_suffix(".tmp")
tmp.write_text(yaml.dump(d, allow_unicode=True, default_flow_style=False))
os.replace(tmp, cfg)
print(f"  framework_packages.yaml: added '{dst_n}'")
PYEOF
  fi

  echo "==> copy complete: $src → $dst"
  echo "    NOTE: config_params values were copied verbatim — update IPs, names, etc. before deploying"
}
```

#### Dispatch block update

In the `case "$CMD" in` block, add:
```bash
  rename)      _cmd_rename "$@" ;;
  copy)        _cmd_copy "$@" ;;
```

In the usage block, add:
```
  rename <src> <dst>      Rename a package: filesystem + config + SOPS + state
                          Options: --dry-run, --skip-state
  copy <src> <dst>        Copy a package (--skip-state or --with-state required)
                          Options: --dry-run, --skip-state, --with-state
```

### `framework/pkg-mgr/README.md` — modify

Add a new **Commands** section entry for `rename` and `copy` covering:
- Syntax and options
- What each phase does
- Warning about config_params values after `copy` (they are copied verbatim and must be updated)
- Note that `copy` requires explicit `--skip-state` or `--with-state`; `rename` migrates state by default

### `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — modify

#### New AppState fields

Add to the `AppState` class alongside other `float_*` / `refactor_*` state vars:

```python
# pkg-mgr rename/copy dialog
pkg_op_open: bool = False
pkg_op_mode: str = ""           # "rename" or "copy"
pkg_op_src: str = ""
pkg_op_dst: str = ""
pkg_op_state_flag: str = ""     # "skip" or "with" (copy only)
pkg_op_running: bool = False
pkg_op_output: str = ""
pkg_op_error: str = ""
```

#### New AppState event handlers

```python
def begin_pkg_rename(self, name: str):
    self.pkg_op_mode = "rename"
    self.pkg_op_src = name
    self.pkg_op_dst = ""
    self.pkg_op_state_flag = ""
    self.pkg_op_output = ""
    self.pkg_op_error = ""
    self.pkg_op_open = True

def begin_pkg_copy(self, name: str):
    self.pkg_op_mode = "copy"
    self.pkg_op_src = name
    self.pkg_op_dst = ""
    self.pkg_op_state_flag = ""   # user must choose skip/with
    self.pkg_op_output = ""
    self.pkg_op_error = ""
    self.pkg_op_open = True

def close_pkg_op(self):
    self.pkg_op_open = False

def set_pkg_op_dst(self, v: str):
    self.pkg_op_dst = v

def set_pkg_op_state_flag(self, v: str):
    self.pkg_op_state_flag = v     # "skip" or "with"

@rx.event(background=True)
async def run_pkg_op(self):
    async with self:
        self.pkg_op_running = True
        self.pkg_op_output = ""
        self.pkg_op_error = ""

    args = [self.pkg_op_mode, self.pkg_op_src, self.pkg_op_dst]
    if self.pkg_op_mode == "copy":
        if self.pkg_op_state_flag == "skip":
            args.append("--skip-state")
        elif self.pkg_op_state_flag == "with":
            args.append("--with-state")
        else:
            async with self:
                self.pkg_op_error = "Select --skip-state or --with-state before copying."
                self.pkg_op_running = False
            return

    ok, out = _run_pkg_mgr(*args)   # blocking; fine in background task

    async with self:
        self.pkg_op_output = out
        self.pkg_op_error = "" if ok else out
        self.pkg_op_running = False
        if ok:
            global _PACKAGES_CACHE
            _PACKAGES_CACHE = _scan_packages()
            self.packages_data = _PACKAGES_CACHE
```

#### New component: `_float_pkg_op_dialog()`

Add a new top-level component function near the other float-* component functions:

```python
def _float_pkg_op_dialog() -> rx.Component:
    """Floating dialog for pkg-mgr rename / copy."""
    title = rx.cond(AppState.pkg_op_mode == "rename", "Rename Package", "Copy Package")
    return rx.cond(
        AppState.pkg_op_open,
        rx.box(
            rx.vstack(
                # Header
                rx.hstack(
                    rx.text(title, font_size="14px", font_weight="700",
                            color="var(--gui-text)"),
                    rx.spacer(),
                    rx.button("✕", size="1", variant="ghost", cursor="pointer",
                              on_click=AppState.close_pkg_op),
                    align="center", width="100%",
                ),
                # Source (read-only)
                rx.hstack(
                    rx.text("Source:", font_size="12px", color="var(--gui-text-dim)",
                            width="80px", flex_shrink="0"),
                    rx.text(AppState.pkg_op_src, font_size="12px",
                            color="var(--gui-text)", font_family="monospace"),
                    align="center", width="100%",
                ),
                # Destination input
                rx.hstack(
                    rx.text("New name:", font_size="12px", color="var(--gui-text-dim)",
                            width="80px", flex_shrink="0"),
                    rx.input(
                        placeholder="new-pkg-name",
                        value=AppState.pkg_op_dst,
                        on_change=AppState.set_pkg_op_dst,
                        size="1", font_size="12px", width="100%",
                        font_family="monospace",
                    ),
                    align="center", width="100%",
                ),
                # State flag selector (copy only)
                rx.cond(
                    AppState.pkg_op_mode == "copy",
                    rx.hstack(
                        rx.text("State:", font_size="12px", color="var(--gui-text-dim)",
                                width="80px", flex_shrink="0"),
                        rx.radio_group(
                            rx.hstack(
                                rx.radio("skip", value="skip"),
                                rx.text("--skip-state", font_size="11px"),
                                spacing="1", align="center",
                            ),
                            rx.hstack(
                                rx.radio("with", value="with"),
                                rx.text("--with-state", font_size="11px"),
                                spacing="1", align="center",
                            ),
                            value=AppState.pkg_op_state_flag,
                            on_change=AppState.set_pkg_op_state_flag,
                            direction="row",
                            spacing="4",
                        ),
                        align="center", width="100%",
                    ),
                    rx.box(),
                ),
                # Error / output strip
                rx.cond(
                    AppState.pkg_op_error,
                    rx.text(AppState.pkg_op_error, font_size="11px",
                            color="var(--red-9)", white_space="pre-wrap"),
                    rx.box(),
                ),
                rx.cond(
                    AppState.pkg_op_output & ~AppState.pkg_op_error,
                    rx.text(AppState.pkg_op_output, font_size="11px",
                            color="var(--green-9)", white_space="pre-wrap"),
                    rx.box(),
                ),
                # Action buttons
                rx.hstack(
                    rx.button(
                        rx.cond(
                            AppState.pkg_op_running,
                            rx.hstack(rx.spinner(size="1"), rx.text("Running…"), spacing="1"),
                            rx.cond(AppState.pkg_op_mode == "rename", "Rename", "Copy"),
                        ),
                        size="1", variant="solid", color_scheme="blue",
                        disabled=AppState.pkg_op_running | (AppState.pkg_op_dst == ""),
                        on_click=AppState.run_pkg_op,
                        cursor="pointer",
                    ),
                    rx.button(
                        "Cancel", size="1", variant="ghost", cursor="pointer",
                        on_click=AppState.close_pkg_op,
                        disabled=AppState.pkg_op_running,
                    ),
                    spacing="2", align="center",
                ),
                spacing="3", align="start", width="100%", padding="16px",
            ),
            position="fixed",
            top="50%",
            left="50%",
            transform="translate(-50%, -50%)",
            width="420px",
            background="var(--gray-1)",
            border="1px solid var(--gray-6)",
            border_radius="8px",
            box_shadow="0 4px 24px rgba(0,0,0,0.35)",
            z_index="200",
        ),
        rx.box(),
    )
```

#### Buttons in `_pkg_card()` expanded card header

In the expanded card header `rx.hstack`, after the existing "secrets" button and before `align="center"`, add:

```python
rx.button(
    "✎ Rename", variant="ghost", size="1", font_size="11px",
    cursor="pointer", color="var(--blue-9)",
    on_click=AppState.begin_pkg_rename(pkg.name),
    title="Rename this package",
),
rx.button(
    "⧉ Copy", variant="ghost", size="1", font_size="11px",
    cursor="pointer", color="var(--blue-9)",
    on_click=AppState.begin_pkg_copy(pkg.name),
    title="Copy this package to a new name",
),
```

#### Wire dialog into the main layout

Find where other `float_*` dialogs are included in the main layout (near `float-refactor-window` references) and add `_float_pkg_op_dialog()` alongside them. The float container `rx.box` with `id="float-pkg-op-dialog"` should be included in the JS snippet that closes all floats on outside-click.

## Execution Order

1. Edit `framework/pkg-mgr/run` — add helpers and two new commands in order
2. Edit `framework/pkg-mgr/README.md` — add documentation for both commands
3. Edit `homelab_gui.py` — add AppState fields, event handlers, dialog component, buttons, layout wiring
4. Verify (see below)

## Verification

```bash
# 1. Syntax check
bash -n framework/pkg-mgr/run && echo "syntax OK"

# 2. Dry-run rename of a local package (observe output, nothing changes)
framework/pkg-mgr/run rename pwy-home-lab-pkg pwy-home-lab-pkg-renamed --dry-run

# 3. copy without state flag should error
framework/pkg-mgr/run copy pwy-home-lab-pkg pwy-home-lab-pkg-copy 2>&1 | grep "requires"

# 4. Help text shows new commands
framework/pkg-mgr/run 2>&1 | grep -E "rename|copy"

# 5. GUI syntax check
python3 -m py_compile \
  infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py && echo "OK"

# 6. No hardcoded pkg names in pkg-mgr/run
grep -n "pwy-home-lab-pkg" framework/pkg-mgr/run | grep -v "^.*#"
```
