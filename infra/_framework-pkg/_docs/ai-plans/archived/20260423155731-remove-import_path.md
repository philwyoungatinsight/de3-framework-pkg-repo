# Plan: Remove `import_path` from Package Config

## Objective

Remove the `import_path` field from all package configuration files and enforce that the
symlink path for any external package is always derived from the package `name`. The field
was always redundant (every value equalled `name`), and allowing it to be set independently
creates a risk of misconfiguration. After this change, `import_path` cannot be set by users
at all — `pkg-mgr` will error if it finds the field in any package entry.

## Context

`import_path` is defined in two YAML config files and consumed only in `pkg-mgr`:

- **Where it is defined** (redundant, always equals `name`):
  - `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_packages.yaml` — 12 external packages
  - `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_repo_manager.yaml` — `framework_package_template` + 10 external entries inside `framework_repos`
  - `infra/_framework-pkg/_config/_framework_settings/framework_packages.yaml` (de3-runner repo) — 12 external packages
  - `infra/_framework-pkg/_config/_framework_settings/framework_repo_manager.yaml` (de3-runner repo) — 1 comment-only reference + 1 active entry

- **Where it is consumed** — only `pkg-mgr` at `infra/_framework-pkg/_framework/_pkg-mgr/pkg-mgr` (de3-runner repo):
  - `_create_symlink()` (arg 3): builds `../infra/$import_path` — must use `$pkg_name` instead
  - `_check_unit_collisions()` / `_check_config_collisions()` / `_check_collisions()` (arg 2): pass-through path — must use `$pkg_name` instead
  - `_resolve_pkg_repo()`: reads `import_path` from YAML; outputs `"$repo $import_path"` as two-word line — simplify to output only `"$repo"`
  - `_cmd_sync()` Python block: extracts `import_path`, emits it in `ENTRY` line — remove it
  - `_cmd_sync()` shell loop: reads `import_path` from `ENTRY` line — remove it
  - `_cmd_import()` (lines 551, 554, 612): reads from `_resolve_pkg_repo` output, passes to helpers — simplify
  - `_cmd_check()` (lines 688–689): same pattern as `_cmd_import`
  - Python entry-write block in `_cmd_import()` (line 597): writes `import_path` to YAML — remove it

- **One docstring mention** in `de3-gui-pkg/homelab_gui/homelab_gui.py` (line 3075) — update comment only.

Both config files exist in **two** git repos:
- **pwy-home-lab-pkg** (main repo, `/home/pyoung/git/pwy-home-lab-pkg/`)
- **de3-runner** (external package repo, `/home/pyoung/git/de3-ext-packages/de3-runner/main/`)

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_packages.yaml` (pwy-home-lab-pkg repo) — modify

Remove all 12 `import_path: <name>` lines from the external package entries (lines 37, 45, 53,
61, 68, 76, 84, 92, 100, 108, 116, 124). Also update the comment example (line 22) to remove
`import_path: foo-pkg` from the example block.

```yaml
# Before (example):
  - name: aws-pkg
    package_type: external
    exportable: true
    repo: de3-runner
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: aws-pkg      # ← remove this line
    config_source: pwy-home-lab-pkg

# After:
  - name: aws-pkg
    package_type: external
    exportable: true
    repo: de3-runner
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    config_source: pwy-home-lab-pkg
```

Same removal for azure-pkg, de3-gui-pkg, _framework-pkg, demo-buckets-example-pkg, gcp-pkg,
image-maker-pkg, maas-pkg, mesh-central-pkg, mikrotik-pkg, proxmox-pkg, unifi-pkg.

---

### `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_repo_manager.yaml` (pwy-home-lab-pkg repo) — modify

Remove `import_path:` from:
- `framework_package_template` block (line 55): `import_path: _framework-pkg`
- All 9 external package entries inside `framework_repos` (lines 109, 116, 123, 146, 153, 168, 183, 190, 213)

---

### `infra/_framework-pkg/_config/_framework_settings/framework_packages.yaml` (de3-runner repo) — modify

Same as the pwy-home-lab-pkg version above: remove 12 `import_path:` lines and update the
comment example (line 22).

---

### `infra/_framework-pkg/_config/_framework_settings/framework_repo_manager.yaml` (de3-runner repo) — modify

Remove:
- Line 26: `#  import_path: _framework-pkg` (inside the commented-out `framework_package_template` example)
- Line 100: `import_path: proxmox-pkg` (inside the active `my-homelab` repo entry)

---

### `infra/_framework-pkg/_framework/_pkg-mgr/pkg-mgr` (de3-runner repo) — modify

This is the main logic change. Changes by function:

**`_create_symlink()` — remove `import_path` param, use `pkg_name` directly:**
```bash
# Before:
_create_symlink() {
  local pkg_name="$1" repo="$2" import_path="$3" git_ref="${4:-}"
  local ref_dir; ref_dir=$(_ref_to_dir "$git_ref")
  local link="$INFRA_DIR/$pkg_name"
  local target="../_ext_packages/$repo/$ref_dir/infra/$import_path"
  ...
}

# After:
_create_symlink() {
  local pkg_name="$1" repo="$2" git_ref="${3:-}"
  local ref_dir; ref_dir=$(_ref_to_dir "$git_ref")
  local link="$INFRA_DIR/$pkg_name"
  local target="../_ext_packages/$repo/$ref_dir/infra/$pkg_name"
  ...
}
```

**`_check_unit_collisions()` — rename param:**
```bash
# Before:
_check_unit_collisions() {
  local repo="$1" pkg_import_path="$2" git_ref="${3:-}"
  local ref_dir; ref_dir=$(_ref_to_dir "$git_ref")
  local candidate_dir="$EXT_PACKAGES_DIR/$repo/$ref_dir/infra/$pkg_import_path"
  ...
      candidate_rel="$pkg_import_path/$rel"
  ...
}

# After:
_check_unit_collisions() {
  local repo="$1" pkg_name="$2" git_ref="${3:-}"
  local ref_dir; ref_dir=$(_ref_to_dir "$git_ref")
  local candidate_dir="$EXT_PACKAGES_DIR/$repo/$ref_dir/infra/$pkg_name"
  ...
      candidate_rel="$pkg_name/$rel"
  ...
}
```

**`_check_config_collisions()` — rename param:**
```bash
# Before:
_check_config_collisions() {
  local repo="$1" pkg_import_path="$2" git_ref="${3:-}"
  local ref_dir; ref_dir=$(_ref_to_dir "$git_ref")
  local candidate_cfg="$EXT_PACKAGES_DIR/$repo/$ref_dir/infra/$pkg_import_path/_config/$pkg_import_path.yaml"
  ...
}

# After:
_check_config_collisions() {
  local repo="$1" pkg_name="$2" git_ref="${3:-}"
  local ref_dir; ref_dir=$(_ref_to_dir "$git_ref")
  local candidate_cfg="$EXT_PACKAGES_DIR/$repo/$ref_dir/infra/$pkg_name/_config/$pkg_name.yaml"
  ...
}
```

**`_check_collisions()` — rename param:**
```bash
# Before:
_check_collisions() {
  local repo="$1" pkg_import_path="$2" git_ref="${3:-}"
  _check_unit_collisions   "$repo" "$pkg_import_path" "$git_ref"
  _check_config_collisions "$repo" "$pkg_import_path" "$git_ref"
}

# After:
_check_collisions() {
  local repo="$1" pkg_name="$2" git_ref="${3:-}"
  _check_unit_collisions   "$repo" "$pkg_name" "$git_ref"
  _check_config_collisions "$repo" "$pkg_name" "$git_ref"
}
```

**`_resolve_pkg_repo()` — remove `import_path` variable, simplify output:**
```bash
# Before:
_resolve_pkg_repo() {
  local parent_repo="$1" pkg_name="$2"
  local parent_cfg; parent_cfg="$(_clone_dir "$parent_repo")/config/framework_packages.yaml"

  if [[ ! -f "$parent_cfg" ]]; then
    echo "$parent_repo $pkg_name"
    return 0
  fi

  local source_url import_path
  source_url=$(python3 -c "
import yaml, sys
pkgs = yaml.safe_load(open('$parent_cfg'))['framework_packages']
entry = next((p for p in pkgs if p['name'] == '$pkg_name'), {})
print(entry.get('source', ''))
" 2>/dev/null || true)
  import_path=$(python3 -c "
import yaml, sys
pkgs = yaml.safe_load(open('$parent_cfg'))['framework_packages']
entry = next((p for p in pkgs if p['name'] == '$pkg_name'), {})
print(entry.get('import_path', '$pkg_name'))
" 2>/dev/null || echo "$pkg_name")

  if [[ -n "$source_url" ]]; then
    local slug
    slug=$(_url_to_slug "$source_url")
    _ensure_cloned "$slug" "$source_url"
    echo "$slug $import_path"
  else
    echo "$parent_repo $import_path"
  fi
}

# After:
_resolve_pkg_repo() {
  local parent_repo="$1" pkg_name="$2"
  local parent_cfg; parent_cfg="$(_clone_dir "$parent_repo")/config/framework_packages.yaml"

  if [[ ! -f "$parent_cfg" ]]; then
    echo "$parent_repo"
    return 0
  fi

  local source_url
  source_url=$(python3 -c "
import yaml, sys
pkgs = yaml.safe_load(open('$parent_cfg'))['framework_packages']
entry = next((p for p in pkgs if p['name'] == '$pkg_name'), {})
print(entry.get('source', ''))
" 2>/dev/null || true)

  if [[ -n "$source_url" ]]; then
    local slug
    slug=$(_url_to_slug "$source_url")
    _ensure_cloned "$slug" "$source_url"
    echo "$slug"
  else
    echo "$parent_repo"
  fi
}
```

**`_cmd_sync()` Python block — remove `import_path`, add validation:**
```python
# Before (lines 398-406):
for p in pkgs:
    if p.get("package_type") != "external":
        continue
    repo = p.get("repo", "")
    name = p["name"]
    import_path = p.get("import_path", name)
    source = p.get("source", "")
    ref = p.get("git_ref", "")
    print(f"ENTRY {name} {repo} {import_path} {source} {ref}")

# After:
for p in pkgs:
    if "import_path" in p:
        invalid.append(f"  '{p['name']}': import_path is not supported — the symlink path always equals the package name")
for p in pkgs:
    if p.get("package_type") != "external":
        continue
    repo = p.get("repo", "")
    name = p["name"]
    source = p.get("source", "")
    ref = p.get("git_ref", "")
    print(f"ENTRY {name} {repo} {source} {ref}")
```

Note: the `invalid` list check already happens in the block at lines 382-396 that prints and exits. The new `import_path` check must be appended to that same validation block (before `sys.exit(1)`), or added as a separate check after. Either way it must use the same `invalid` list and exit.

**`_cmd_sync()` shell `while read` loop — remove `import_path` from field list:**
```bash
# Before (line 367):
python3 - "$FRAMEWORK_PKGS_CFG" "$EXT_PACKAGES_DIR" "$INFRA_DIR" <<'PYEOF' | while read -r _ pkg_name repo import_path source_url git_ref; do

# After:
python3 - "$FRAMEWORK_PKGS_CFG" "$EXT_PACKAGES_DIR" "$INFRA_DIR" <<'PYEOF' | while read -r _ pkg_name repo source_url git_ref; do
```

**`_cmd_sync()` `_create_symlink` call — remove `import_path`:**
```bash
# Before (line 420):
    _create_symlink "$pkg_name" "$repo" "$import_path" "$git_ref"

# After:
    _create_symlink "$pkg_name" "$repo" "$git_ref"
```

**`_cmd_import()` — update three sites:**
```bash
# Before (lines 551, 554, 612):
  read -r actual_repo import_path < <(_resolve_pkg_repo "$repo" "$pkg_name")
  collisions=$(_check_collisions "$actual_repo" "$import_path" "$git_ref")
  ...
  _create_symlink "$pkg_name" "$actual_repo" "$import_path" "$git_ref"

# After:
  read -r actual_repo < <(_resolve_pkg_repo "$repo" "$pkg_name")
  collisions=$(_check_collisions "$actual_repo" "$pkg_name" "$git_ref")
  ...
  _create_symlink "$pkg_name" "$actual_repo" "$git_ref"
```

**`_cmd_import()` Python entry-write block — remove `import_path` from entry dict:**
```python
# Before (lines 580-609):
import_path = sys.argv[4]
...
entry = {"name": name, "package_type": "external", "exportable": False, "repo": repo, "import_path": import_path}

# After: remove the sys.argv[4] assignment and the import_path key from entry:
# (sys.argv indices for remaining args shift: name=2, repo=3, source_url=4, git_ref=5)
entry = {"name": name, "package_type": "external", "exportable": False, "repo": repo}
```

Also update the Python invocation at line 580 to not pass `import_path` as arg 4, and fix the sys.argv indices:
```bash
# Before (line 580):
  python3 - "$FRAMEWORK_PKGS_CFG" "$pkg_name" "$actual_repo" "$import_path" "$source_url" "$git_ref" <<'PYEOF'

# After:
  python3 - "$FRAMEWORK_PKGS_CFG" "$pkg_name" "$actual_repo" "$source_url" "$git_ref" <<'PYEOF'
```
And inside the Python heredoc, change `sys.argv[5]` → `sys.argv[4]` and `sys.argv[6]` → `sys.argv[5]`.

**`_cmd_check()` — update two sites:**
```bash
# Before (lines 688-689):
  read -r actual_repo import_path < <(_resolve_pkg_repo "$repo" "$pkg_name")
  collisions=$(_check_collisions "$actual_repo" "$import_path")

# After:
  read -r actual_repo < <(_resolve_pkg_repo "$repo" "$pkg_name")
  collisions=$(_check_collisions "$actual_repo" "$pkg_name")
```

---

### `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` (de3-runner repo) — modify

Update the docstring comment at line 3075 to remove the `import_path` field from the
documented return shape:
```python
# Before:
"""Return [{name, public, repo, import_path, source, version}] from framework_packages.yaml."""

# After:
"""Return [{name, public, repo, source, version}] from framework_packages.yaml."""
```

---

## Execution Order

1. Modify `pkg-mgr` (de3-runner repo) — the script change is the core logic; do this first so it is correct before any YAML is touched.
2. Remove `import_path` from `infra/_framework-pkg/_config/_framework_settings/framework_packages.yaml` (de3-runner repo).
3. Remove `import_path` from `infra/_framework-pkg/_config/_framework_settings/framework_repo_manager.yaml` (de3-runner repo).
4. Update docstring in `homelab_gui.py` (de3-runner repo).
5. Commit the de3-runner changes as one commit.
6. Remove `import_path` from `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_packages.yaml` (pwy-home-lab-pkg repo).
7. Remove `import_path` from `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_repo_manager.yaml` (pwy-home-lab-pkg repo).
8. Bump version in `infra/_framework-pkg/_config/version_history.md` + `_framework-pkg.yaml` (de3-runner repo).
9. Commit pwy-home-lab-pkg changes.

## Verification

```bash
# 1. Confirm no import_path remains in active config or scripts
grep -r "import_path" \
  /home/pyoung/git/pwy-home-lab-pkg/infra/pwy-home-lab-pkg/_config/ \
  /home/pyoung/git/de3-ext-packages/de3-runner/main/infra/_framework-pkg/ \
  | grep -v "_docs/\|archived\|ai-log\|ai-plans"

# 2. Re-sync packages (should succeed, symlinks should still resolve)
cd /home/pyoung/git/pwy-home-lab-pkg
source set_env.sh
pkg-mgr sync

# 3. Confirm symlinks are intact
ls -la infra/aws-pkg infra/_framework-pkg infra/maas-pkg

# 4. Confirm validation fires if import_path is manually added back
# (manual test: temporarily add import_path to one entry, run pkg-mgr sync, expect ERROR)
```
