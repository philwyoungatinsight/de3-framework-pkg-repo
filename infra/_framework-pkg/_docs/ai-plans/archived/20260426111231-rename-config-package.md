# Plan: Rename `_framework.config_package` → `_framework.main_package`

## Objective

Rename the YAML key `config_package` (under `_framework:` in every repo's `config/_framework.yaml`)
to `main_package`. Update all code that writes or reads this key, all comments that document it,
and regenerate all derived outputs.

## Context

`config_package` lives at the YAML path `_framework > config_package` in `config/_framework.yaml`.
It is a distinct concept from:
- `is_config_package: true` on package entries in `framework_repo_manager.yaml` (boolean flag, NOT renamed)
- Legacy `config_package:` at the repo-entry level in `framework_repo_manager.yaml` (legacy key, NOT renamed)

**Files that write this key:**
- `fw-repo-mgr` → `_write_config_framework_yaml()` generates `config/_framework.yaml` for every
  managed repo via `fw-repo-mgr -b`

**Files that read this key:**
- `read-set-env.py` — called by `set_env.sh` to populate `_FRAMEWORK_CONFIG_PKG`
- `scanner.py` (fw-repos-visualizer) — reads it from each cloned repo's `config/_framework.yaml`
  AND stores it as an internal dict field in the scan result

**All code lives in `de3-runner`** at
`/home/pyoung/git/de3-ext-packages/de3-runner/main/`, because `_framework-pkg` is an external
package (symlinked). Changes must be committed to de3-runner, not to pwy-home-lab-pkg.

**Locally-present repos with `config_package:` in `config/_framework.yaml`:**
- `pwy-home-lab-pkg/config/_framework.yaml` (the live file)
- `~/git/fw-repos-visualizer-cache/pwy-home-lab-pkg/config/_framework.yaml` (stale cache — will
  auto-update when the visualizer rescans)

Generated repos (proxmox-pkg-repo, de3-gui-pkg, etc.) have their `config/_framework.yaml` written
by `fw-repo-mgr -b`, so they will be updated automatically once the tool is fixed.

**Current versions:**
- `_framework-pkg`: 1.12.0 (version_history.md in de3-runner)
- `pwy-home-lab-pkg`: 1.0.0

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `de3-runner`: `infra/_framework-pkg/_framework/_utilities/python/read-set-env.py` — modify

Two changes:

1. Docstring line 6: `_framework.config_package` → `_framework.main_package`
2. Line 25: `.get("config_package", "")` → `.get("main_package", "")`

```python
# line 6 (in docstring):
      Reads config/_framework.yaml and prints _framework.main_package (or "").

# line 25:
        print((d or {}).get("_framework", {}).get("main_package", ""))
```

### `de3-runner`: `infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr` — modify

Five changes (all in or near `_write_config_framework_yaml()`):

```bash
# Line 226 — comment block header:
# Write config/_framework.yaml to set main_package in the target repo

# Line 228 — function signature comment:
_write_config_framework_yaml() {   # _write_config_framework_yaml <repo_dir> <main_package>

# Line 233 — heredoc body:
  main_package: $config_pkg

# Line 235 — echo confirmation:
  echo "  wrote: config/_framework.yaml (main_package: $config_pkg)"

# Lines 393 comment + 418 comment: update occurrences of "config_package" in inline comments
# to "main_package" where they refer to the _framework.yaml key (not to the legacy fw-mgr key)
```

Lines 393–394 (the step comment, not the variable name):
```bash
  # Step 3: set up main_package scaffolding when main_package is specified
  local config_pkg; config_pkg=$(_config_package "$repo_name")
```

Line 418 comment:
```bash
  # When main_package is set, _framework-pkg was pruned (it's external), making
```

**Do NOT rename:** the shell function `_config_package()`, the shell variable `config_pkg`, the
local-variable names, or the usage text block starting at line 522 (`config_package support:`).
Those refer to the legacy `framework_repo_manager.yaml` repo-level key which is not being renamed.

### `de3-runner`: `infra/_framework-pkg/_framework/_fw-repos-visualizer/fw_repos_visualizer/scanner.py` — modify

Replace all occurrences of `"config_package"` as a Python dict key or YAML field name with
`"main_package"`. All 10 occurrences are in `scanner.py` — none in `renderer.py`, `main.py`,
or `config.py`.

Full sed-style substitution — replace every `"config_package"` string literal with `"main_package"`:
- Line 118: `declared_repos.get(current_name) or {}).get("config_package", "")` → `"main_package"`
- Line 119: `result[current_name].get("config_package")` → `"main_package"`
- Line 120: `result[current_name]["config_package"]` → `"main_package"`
- Line 213: `"config_package": config_pkg,` → `"main_package": config_pkg,`
- Line 297: `fw_cfg.get("config_package", "")` → `"main_package"`
- Line 299: `entry["config_package"] = cp` → `entry["main_package"] = cp`
- Line 307: `entry.get("config_package", "")` → `"main_package"`

Update the four inline comments that mention `config_package` (lines 117, 193, 289, 306 area):
- Line 117: `# Back-fill config_package from declared stub...` → `main_package`
- Line 193: `# Derive config_package: prefer is_config_package flag...` → `main_package`
- Line 289: `# Read config_package and labels from config/_framework.yaml...` → `main_package`
- Line 307: (no comment on that line; the comment is on 306 if any)

### `de3-runner`: `infra/_framework-pkg/_config/version_history.md` — modify

Bump 1.12.0 → 1.13.0, append entry:
```markdown
## 1.13.0  (2026-04-25, git: <sha>)
- rename _framework.config_package to _framework.main_package in fw-repo-mgr, read-set-env.py, and scanner.py
```
(Fill sha after committing to de3-runner.)

### `de3-runner`: `infra/_framework-pkg/_config/_framework-pkg.yaml` — modify

Update `_provides_capability: - _framework-pkg: 1.12.0` → `1.13.0`.

### `pwy-home-lab-pkg`: `config/_framework.yaml` — modify

Line 3: `config_package: pwy-home-lab-pkg` → `main_package: pwy-home-lab-pkg`

```yaml
_framework:
  # Use the framework settings in this package.
  main_package: pwy-home-lab-pkg
  labels:
    ...
```

### `pwy-home-lab-pkg`: `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_repo_manager.yaml` — modify

Update the two comments that say `_framework.config_package`:

Line 61:
```yaml
  #   2. Set _framework.main_package to that package name in config/_framework.yaml.
```

Line 65 area — wherever `_framework.config_package` appears in comments, change to
`_framework.main_package`.

## Execution Order

1. **Commit de3-runner changes first** — the code must be updated before `set_env.sh` is sourced
   in pwy-home-lab-pkg, otherwise `_FRAMEWORK_CONFIG_PKG` will be empty after the `config/_framework.yaml`
   rename.
   - Edit `read-set-env.py`, `fw-repo-mgr`, `scanner.py`, `version_history.md`, `_framework-pkg.yaml`
   - Commit to de3-runner

2. **Update pwy-home-lab-pkg** — after de3-runner is committed and the symlink resolves correctly:
   - Edit `config/_framework.yaml`
   - Edit `framework_repo_manager.yaml` comments
   - Commit to pwy-home-lab-pkg

3. **Run `fw-repo-mgr -b`** from pwy-home-lab-pkg to rebuild all managed repos. This writes the
   new `main_package:` key into every generated repo's `config/_framework.yaml` and pushes.

4. **Run `fw-repos-visualizer --refresh`** to regenerate
   `config/tmp/fw-repos-visualizer/known-fw-repos.yaml` with `main_package` fields.

## Verification

After step 1 (de3-runner committed and symlink live):
```bash
cd /home/pyoung/git/pwy-home-lab-pkg
source set_env.sh
echo "_FRAMEWORK_CONFIG_PKG=${_FRAMEWORK_CONFIG_PKG}"
# Expected: pwy-home-lab-pkg
```

After step 2 (pwy-home-lab-pkg committed):
```bash
grep "main_package" config/_framework.yaml
# Expected: "  main_package: pwy-home-lab-pkg"
grep "config_package" config/_framework.yaml
# Expected: (no output)
```

After step 4:
```bash
grep "main_package" config/tmp/fw-repos-visualizer/known-fw-repos.yaml | head -5
grep "config_package" config/tmp/fw-repos-visualizer/known-fw-repos.yaml | head -5
# Expected: main_package lines present, no config_package lines
```
