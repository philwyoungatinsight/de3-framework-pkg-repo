# Plan: Rename `_fw-repos-visualizer` to `_fw_repos_diagram_exporter`

## Objective

Rename the framework tool `_fw-repos-visualizer` to `_fw_repos_diagram_exporter` everywhere
it is referenced in live code and config. Historical records (ai-log files, archived ai-plans,
ai-log-summary entries, version_history.md changelog entries) are left unchanged — they describe
what happened at a point in time and should retain the original name.

## Context

The tool lives at `infra/_framework-pkg/_framework/_fw-repos-visualizer/`. Its internal structure:

- Bash entry-point: `fw-repos-visualizer` (added to `$PATH` by `set_env.sh`)
- Python package: `fw_repos_visualizer/` (modules: `__init__.py`, `config.py`, `main.py`, `renderer.py`, `scanner.py`)
- Config YAML: `infra/_framework-pkg/_config/_framework_settings/framework_repos_visualizer.yaml` (top-level key `framework_repos_visualizer:`)
- State output dir: `config/tmp/fw-repos-visualizer/`
- Repos cache dir: `~/git/fw-repos-visualizer-cache/` (default in config + Python fallback)
- Env var exported by `set_env.sh`: `_FW_REPOS_VISUALIZER`
- PATH entry in `set_env.sh`: `$_FRAMEWORK_DIR/_fw-repos-visualizer`

Live files referencing the old name outside the tool directory itself:
- `infra/_framework-pkg/_framework/_git_root/set_env.sh` (env var + PATH loop)
- `infra/_framework-pkg/_framework/README.md` (tool table)
- `infra/_framework-pkg/_config/_framework_settings/framework_repos_visualizer.yaml` (config file)
- `CLAUDE.md` (repo root, line 131 — "The fw-repos visualizer reads...")
- `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_repo_manager.yaml` (comment at line 169)

The env var `_FW_REPOS_VISUALIZER` is defined only in `set_env.sh` and is not referenced in
any other live code file in this repo.

Existing cached state at `config/tmp/fw-repos-visualizer/` will not be migrated — a
`fw_repos_diagram_exporter --refresh` is needed after the rename to regenerate it.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `infra/_framework-pkg/_framework/_fw-repos-visualizer/` → `_fw_repos_diagram_exporter/` — rename (git mv)

```bash
git mv infra/_framework-pkg/_framework/_fw-repos-visualizer \
       infra/_framework-pkg/_framework/_fw_repos_diagram_exporter
```

### `_fw_repos_diagram_exporter/fw_repos_visualizer/` → `fw_repos_diagram_exporter/` — rename (git mv)

```bash
git mv infra/_framework-pkg/_framework/_fw_repos_diagram_exporter/fw_repos_visualizer \
       infra/_framework-pkg/_framework/_fw_repos_diagram_exporter/fw_repos_diagram_exporter
```

### `_fw_repos_diagram_exporter/fw-repos-visualizer` → `fw_repos_diagram_exporter` — rename (git mv)

```bash
git mv infra/_framework-pkg/_framework/_fw_repos_diagram_exporter/fw-repos-visualizer \
       infra/_framework-pkg/_framework/_fw_repos_diagram_exporter/fw_repos_diagram_exporter
```

### `_fw_repos_diagram_exporter/fw_repos_diagram_exporter` (bash wrapper) — modify

Line 12: update the Python module reference.

```bash
# Before:
cd "${SCRIPT_DIR}" && exec python3 -m fw_repos_visualizer.main "$@"
# After:
cd "${SCRIPT_DIR}" && exec python3 -m fw_repos_diagram_exporter.main "$@"
```

### `_fw_repos_diagram_exporter/fw_repos_diagram_exporter/main.py` — modify

- Line 1: `"""fw-repos-visualizer CLI."""` → `"""fw_repos_diagram_exporter CLI."""`
- Line 16: `prog="fw-repos-visualizer"` → `prog="fw_repos_diagram_exporter"`
- Lines 21–25: all five examples in the epilog:
  ```
  "  fw_repos_diagram_exporter --refresh\n"
  "  fw_repos_diagram_exporter --list\n"
  "  fw_repos_diagram_exporter --list --format text,dot\n"
  "  fw_repos_diagram_exporter --refresh --list\n"
  "  fw_repos_diagram_exporter --list --no-auto-refresh\n"
  ```

### `_fw_repos_diagram_exporter/fw_repos_diagram_exporter/config.py` — modify

- Line 1: `"""Config loading for fw-repos-visualizer."""` → `"""Config loading for fw_repos_diagram_exporter."""`
- Line 41: `"framework_repos_visualizer.yaml"` → `"framework_repos_diagram_exporter.yaml"`
- Line 44: `raw.get("framework_repos_visualizer", {})` → `raw.get("framework_repos_diagram_exporter", {})`
- Line 48: `"fw-repos-visualizer"` → `"fw_repos_diagram_exporter"` (the `config/tmp/` subdir name)

### `_fw_repos_diagram_exporter/fw_repos_diagram_exporter/scanner.py` — modify

- Line 1: `"""Repo discovery and scanning for fw-repos-visualizer."""` → `"""Repo discovery and scanning for fw_repos_diagram_exporter."""`
- Line 29: `"git/fw-repos-visualizer-cache"` → `"git/fw_repos_diagram_exporter_cache"`
- Line 71: same default (identical change)

### `_fw_repos_diagram_exporter/fw_repos_diagram_exporter/renderer.py` — modify

- Line 15: `"fw-repos-visualizer: no state found — run --refresh first"` → `"fw_repos_diagram_exporter: no state found — run --refresh first"`
- Line 28: `f"fw-repos-visualizer: unknown format '{fmt}', skipping"` → `f"fw_repos_diagram_exporter: unknown format '{fmt}', skipping"`

### `infra/_framework-pkg/_config/_framework_settings/framework_repos_visualizer.yaml` → `framework_repos_diagram_exporter.yaml` — rename + modify

```bash
git mv infra/_framework-pkg/_config/_framework_settings/framework_repos_visualizer.yaml \
       infra/_framework-pkg/_config/_framework_settings/framework_repos_diagram_exporter.yaml
```

Then update content:
- Line 1: `framework_repos_visualizer:` → `framework_repos_diagram_exporter:`
- Line 4: `repos_cache_dir: 'git/fw-repos-visualizer-cache'` → `repos_cache_dir: 'git/fw_repos_diagram_exporter_cache'`
- Line 6: `# Formats to render on --list. All rendered simultaneously to config/tmp/fw-repos-visualizer/.`
         → `# Formats to render on --list. All rendered simultaneously to config/tmp/fw_repos_diagram_exporter/.`

### `infra/_framework-pkg/_framework/_git_root/set_env.sh` — modify

Line 42 — rename env var and update both path components:
```bash
# Before:
export _FW_REPOS_VISUALIZER="$_FRAMEWORK_DIR/_fw-repos-visualizer/fw-repos-visualizer"  # repo/package discovery and visualization
# After:
export _FW_REPOS_DIAGRAM_EXPORTER="$_FRAMEWORK_DIR/_fw_repos_diagram_exporter/fw_repos_diagram_exporter"  # repo/package discovery and diagram export
```

Line 107 — update directory in PATH loop:
```bash
# Before:
        "$_FRAMEWORK_DIR/_fw-repos-visualizer"; do
# After:
        "$_FRAMEWORK_DIR/_fw_repos_diagram_exporter"; do
```

### `infra/_framework-pkg/_framework/README.md` — modify

Line 18 — update the table entry:
```markdown
| `_fw_repos_diagram_exporter/` | Framework repo discovery and diagram export tool. BFS-discovers all reachable framework repos by cloning them into a dedicated cache (`~/git/fw_repos_diagram_exporter_cache/`) and scanning each for `_framework_settings` directories. Records results in `config/tmp/fw_repos_diagram_exporter/known-fw-repos.yaml`. Renders as yaml, json, text tree, and/or DOT graph simultaneously. Leverages `framework_repo_manager.yaml` to record which repos were generated by which source repos (`created_by` lineage). Configurable auto-refresh with modes `never`, `fixed_time`, `file_age` (default). Config: `_framework_settings/framework_repos_diagram_exporter.yaml`. |
```

### `CLAUDE.md` (repo root) — modify

Line 131:
```markdown
# Before:
# The fw-repos visualizer reads ALL uncommented `framework_repos` entries and treats them as real repos (attempts to clone, draws nodes in the diagram). An uncommented example like `my-example-repo` will appear in the diagram as a phantom repo.
# After:
# The fw_repos_diagram_exporter reads ALL uncommented `framework_repos` entries and treats them as real repos (attempts to clone, draws nodes in the diagram). An uncommented example like `my-example-repo` will appear in the diagram as a phantom repo.
```

### `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_repo_manager.yaml` — modify

Line 169 comment:
```yaml
# Before:
  # The fw-repos visualizer treats all uncommented entries as existing repos:
# After:
  # The fw_repos_diagram_exporter treats all uncommented entries as existing repos:
```

### `infra/_framework-pkg/_config/version_history.md` — modify

Prepend a new entry at the top (after the heading):
```markdown
## 1.16.0  (2026-04-26, git: <sha-after-commit>)
- Rename framework tool `_fw-repos-visualizer` → `_fw_repos_diagram_exporter`: directory, Python package, bash entry-point, config YAML, state dir, cache dir, env var
```

### `infra/_framework-pkg/_config/_framework-pkg.yaml` — modify

Bump `_provides_capability` version:
```yaml
# Before:
  - _framework-pkg: 1.15.0
# After:
  - _framework-pkg: 1.16.0
```

## Execution Order

1. `git mv` the tool directory (`_fw-repos-visualizer` → `_fw_repos_diagram_exporter`)
2. `git mv` the Python package dir inside it (`fw_repos_visualizer` → `fw_repos_diagram_exporter`)
3. `git mv` the bash wrapper inside it (`fw-repos-visualizer` → `fw_repos_diagram_exporter`)
4. Update bash wrapper content (line 12: module path)
5. Update `main.py`, `config.py`, `scanner.py`, `renderer.py` (internal strings/docstrings)
6. `git mv` the config YAML (`framework_repos_visualizer.yaml` → `framework_repos_diagram_exporter.yaml`)
7. Update config YAML content (top-level key, `repos_cache_dir`, comment)
8. Update `set_env.sh` (env var name, both path references)
9. Update `README.md` in `_framework/`
10. Update `CLAUDE.md` at repo root
11. Update `framework_repo_manager.yaml` comment
12. Update `version_history.md` (new entry) and `_framework-pkg.yaml` (version bump)
13. Write ai-log entry, then commit

## Verification

After executing:

```bash
# 1. Source set_env.sh to pick up new env var and PATH entry
source set_env.sh

# 2. Confirm new env var is exported and old one is gone
echo "$_FW_REPOS_DIAGRAM_EXPORTER"   # should print the full path
echo "${_FW_REPOS_VISUALIZER:-GONE}" # should print GONE

# 3. Confirm the tool runs
fw_repos_diagram_exporter --help

# 4. Confirm state dir is created under the new name
fw_repos_diagram_exporter --refresh
ls config/tmp/fw_repos_diagram_exporter/

# 5. Confirm old tool name is gone from live code (excluding historical docs)
grep -r "fw-repos-visualizer\|fw_repos_visualizer" infra/_framework-pkg/_framework/ infra/_framework-pkg/_config/_framework_settings/ infra/pwy-home-lab-pkg/_config/ CLAUDE.md \
  | grep -v "__pycache__\|\.venv\|version_history"
# Expected: no output
```
