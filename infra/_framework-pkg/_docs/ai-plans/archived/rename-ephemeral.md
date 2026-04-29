# Plan: Rename ephemeral → ramdisk-mgr

## Objective

The directory, scripts, config files, YAML keys, and environment variables that manage
RAM-backed (tmpfs) directories are currently named "ephemeral" — a vague term that
describes the *property* (data doesn't persist) rather than the *purpose* (it is a
RAM disk manager). This plan renames everything to `ramdisk-mgr`, making the tool's
role immediately clear.

Changes span two repos: `de3-runner` (the external framework package) and
`pwy-home-lab-pkg` (the consumer deployment package).

---

## Context

### What exists today

**In `de3-runner` (`/home/pyoung/git/de3-ext-packages/de3-runner/main/`):**

| What | Current path/name |
|------|-------------------|
| Tool directory | `infra/_framework-pkg/_framework/_ephemeral/` |
| Main script | `_ephemeral/ephemeral` |
| Generic utility | `_ephemeral/ephemeral.sh` |
| Tool README | `_ephemeral/README.md` |
| Framework config | `infra/_framework-pkg/_config/_framework_settings/framework_ephemeral_dirs.yaml` |
| YAML key | `framework_ephemeral_dirs:` |
| Human-only wrapper | `_framework/_human-only-scripts/setup-ephemeral-dirs/setup-ephemeral-dirs` |
| Human-only dir | `_human-only-scripts/setup-ephemeral-dirs/` |
| Framework README | `_framework/README.md` (table row for `_ephemeral/`) |
| Framework docs | `_docs/framework/config-files.md` (table row for `framework_ephemeral_dirs.yaml`) |
| `set_env.sh` export | `_EPHEMERAL="$_FRAMEWORK_DIR/_ephemeral/ephemeral"` |
| `set_env.sh` export | `_EPHEMERAL_DIR="$_DYNAMIC_DIR/ephemeral"` |
| `set_env.sh` PATH | `"$_FRAMEWORK_DIR/_ephemeral"` in PATH loop |
| `set_env.sh` mkdir | `"$_EPHEMERAL_DIR"` in `_set_env_create_dirs` |
| `_git_root/run` | `_EPHEMERAL_RUN = Path(ENV['_EPHEMERAL'])` |

**In `pwy-home-lab-pkg`:**

| What | Current path/name |
|------|-------------------|
| `set_env.sh` | Symlink to de3-runner's `set_env.sh` — no separate copy |
| Config override | `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_ephemeral_dirs.yaml` — **staged for deletion** (was `size_mb: 0` override, no longer needed) |

**Stale reference found:**
`setup-ephemeral-dirs` script calls `exec "$GIT_ROOT/infra/_framework-pkg/_ephemeral/run"` —
but the script is now named `ephemeral`, not `run`. This is already broken; the rename
will fix it as a side effect by using the correct new name.

---

## Open Questions

None — ready to proceed.

---

## Files to Create / Modify

All changes in de3-runner are at
`/home/pyoung/git/de3-ext-packages/de3-runner/main/`.
All changes in pwy-home-lab-pkg are at `/home/pyoung/git/pwy-home-lab-pkg/`.

---

### `infra/_framework-pkg/_framework/_ephemeral/` → `_ramdisk-mgr/` — rename dir (de3-runner)

```bash
cd /home/pyoung/git/de3-ext-packages/de3-runner/main
git mv infra/_framework-pkg/_framework/_ephemeral \
       infra/_framework-pkg/_framework/_ramdisk-mgr
```

---

### `_ramdisk-mgr/ephemeral` → `_ramdisk-mgr/ramdisk-mgr` — rename script (de3-runner)

```bash
git mv infra/_framework-pkg/_framework/_ramdisk-mgr/ephemeral \
       infra/_framework-pkg/_framework/_ramdisk-mgr/ramdisk-mgr
```

Update string literals inside the script (all say "ephemeral:" in print statements):
- Line 13: `"ephemeral: non-interactive context detected, skipping."` → `"ramdisk-mgr: non-interactive context detected, skipping."`
- Line 17: `EPHEMERAL_SH="$_FRAMEWORK_DIR/_ephemeral/ephemeral.sh"` → `RAMDISK_MGR_SH="$_FRAMEWORK_DIR/_ramdisk-mgr/ramdisk-mgr.sh"`
- Line 18: `EPHEMERAL_DIRS_YAML="$_FRAMEWORK_PKG_DIR/_config/framework_ephemeral_dirs.yaml"` → `RAMDISK_DIRS_YAML="$_FRAMEWORK_PKG_DIR/_config/framework_ramdisk_dirs.yaml"`
- Line 20: `python3 - "$EPHEMERAL_DIRS_YAML" "$EPHEMERAL_SH" <<'PYEOF'` → `python3 - "$RAMDISK_DIRS_YAML" "$RAMDISK_MGR_SH" <<'PYEOF'`
- Line 22: `ephemeral_dirs_yaml, ephemeral_sh = sys.argv[1], sys.argv[2]` → `ramdisk_dirs_yaml, ramdisk_mgr_sh = sys.argv[1], sys.argv[2]`
- Line 24: `with open(ephemeral_dirs_yaml) as f:` → `with open(ramdisk_dirs_yaml) as f:`
- Line 27: `entries = cfg.get("framework_ephemeral_dirs", [])` → `entries = cfg.get("framework_ramdisk_dirs", [])`
- Line 29: `print("ephemeral: no ephemeral_dirs declared in framework_ephemeral_dirs.yaml")` → `print("ramdisk-mgr: no ramdisk_dirs declared in framework_ramdisk_dirs.yaml")`
- Line 51: `cmd = [ephemeral_sh, "--path", path, ...]` → `cmd = [ramdisk_mgr_sh, "--path", path, ...]`
- Line 59: `print(f"ephemeral: mounting ...")` → `print(f"ramdisk-mgr: mounting ...")`
- Line 63: `print(f"ephemeral: ERROR ...")` → `print(f"ramdisk-mgr: ERROR ...")`

---

### `_ramdisk-mgr/ephemeral.sh` → `_ramdisk-mgr/ramdisk-mgr.sh` — rename utility (de3-runner)

```bash
git mv infra/_framework-pkg/_framework/_ramdisk-mgr/ephemeral.sh \
       infra/_framework-pkg/_framework/_ramdisk-mgr/ramdisk-mgr.sh
```

Update the usage/comment block at the top of the script (lines 1–33):
- Title line: `# ephemeral.sh — mount a RAM-backed filesystem...` → `# ramdisk-mgr.sh — mount a RAM-backed filesystem...`
- Usage lines: `ephemeral.sh --path ...` → `ramdisk-mgr.sh --path ...`
- Example lines: `./ephemeral.sh ...` → `./ramdisk-mgr.sh ...`

---

### `_ramdisk-mgr/README.md` — modify (de3-runner)

Rewrite to use new names throughout:
- Title: `# ephemeral` → `# ramdisk-mgr`
- All references to `ephemeral.sh` → `ramdisk-mgr.sh`
- All references to `ephemeral/run` or `ephemeral` script → `ramdisk-mgr`
- `setup-ephemeral-dirs` → `setup-ramdisk-mounts`
- Config key `framework.ephemeral_dirs` → `framework.ramdisk_dirs`
- Env var `_EPHEMERAL_DIR` → `_RAMDISK_DIR`

---

### `framework_ephemeral_dirs.yaml` → `framework_ramdisk_dirs.yaml` — rename + update key (de3-runner)

```bash
git mv infra/_framework-pkg/_config/_framework_settings/framework_ephemeral_dirs.yaml \
       infra/_framework-pkg/_config/_framework_settings/framework_ramdisk_dirs.yaml
```

Update content — change YAML key and comments:

```yaml
# Directories that should be RAM-backed (tmpfs on Linux, HFS+ RAM disk on macOS).
# Each entry names an env var (exported by set_env.sh) that holds the full path.
# Run `_framework/_human-only-scripts/setup-ramdisk-mounts/setup-ramdisk-mounts` once after login.
# Re-running is safe: changed parameters are applied in place without disk writes.
#
# Fields:
#   env_var     (required) Env var name holding the full directory path.
#   size_mb     (optional) RAM drive size in MB. Default: 64.
#   mode        (optional) Octal directory permissions. Default: 770.
#   owner_user  (optional) Owner user. Default: current user.
#   owner_group (optional) Owner group. Default: current user's primary group.
framework_ramdisk_dirs:
  - env_var: _RAMDISK_DIR
    size_mb: 64
```

---

### `_human-only-scripts/setup-ephemeral-dirs/` → `setup-ramdisk-mounts/` — rename dir (de3-runner)

```bash
git mv infra/_framework-pkg/_framework/_human-only-scripts/setup-ephemeral-dirs \
       infra/_framework-pkg/_framework/_human-only-scripts/setup-ramdisk-mounts
```

---

### `setup-ramdisk-mounts/setup-ephemeral-dirs` → `setup-ramdisk-mounts/setup-ramdisk-mounts` — rename script + fix stale ref (de3-runner)

```bash
git mv infra/_framework-pkg/_framework/_human-only-scripts/setup-ramdisk-mounts/setup-ephemeral-dirs \
       infra/_framework-pkg/_framework/_human-only-scripts/setup-ramdisk-mounts/setup-ramdisk-mounts
```

Fix stale reference (current script calls `_ephemeral/run` which doesn't exist):

```bash
#!/usr/bin/env bash
# Mount all framework ramdisk dirs as RAM drives.
# Run once after login; re-running is safe (already-mounted dirs are skipped).
# Dirs are declared in framework_ramdisk_dirs.yaml under framework_ramdisk_dirs.
set -euo pipefail

GIT_ROOT="$(git rev-parse --show-toplevel)"
exec "$GIT_ROOT/infra/_framework-pkg/_framework/_ramdisk-mgr/ramdisk-mgr"
```

---

### `infra/_framework-pkg/_framework/_git_root/set_env.sh` — modify (de3-runner)

Four changes:

1. Line 36 — env var name and path:
   ```bash
   # Before:
   export _EPHEMERAL="$_FRAMEWORK_DIR/_ephemeral/ephemeral"          # RAM-backed dir manager (tmpfs)
   # After:
   export _RAMDISK_MGR="$_FRAMEWORK_DIR/_ramdisk-mgr/ramdisk-mgr"   # RAM-backed dir manager (tmpfs)
   ```

2. Line 53 — dir env var name and subdir name:
   ```bash
   # Before:
   export _EPHEMERAL_DIR="$_DYNAMIC_DIR/ephemeral"          # RAM-backed scratch space (managed by _EPHEMERAL)
   # After:
   export _RAMDISK_DIR="$_DYNAMIC_DIR/ramdisk"              # RAM-backed scratch space (managed by _RAMDISK_MGR)
   ```

3. Lines 101–105 — PATH loop entry:
   ```bash
   # Before:
   "$_FRAMEWORK_DIR/_ephemeral" \
   # After:
   "$_FRAMEWORK_DIR/_ramdisk-mgr" \
   ```

4. Line 116 — mkdir call:
   ```bash
   # Before:
   mkdir -p "$_CONFIG_TMP_DIR" "$_DYNAMIC_DIR" "$_WAVE_LOGS_DIR" "$_GUI_DIR" "$_EPHEMERAL_DIR" "$_CONFIG_DIR"
   # After:
   mkdir -p "$_CONFIG_TMP_DIR" "$_DYNAMIC_DIR" "$_WAVE_LOGS_DIR" "$_GUI_DIR" "$_RAMDISK_DIR" "$_CONFIG_DIR"
   ```

---

### `infra/_framework-pkg/_framework/_git_root/run` — modify (de3-runner)

Two changes:

1. Variable declaration (line 109):
   ```python
   # Before:
   _EPHEMERAL_RUN      = Path(ENV['_EPHEMERAL'])
   # After:
   _RAMDISK_MGR_RUN    = Path(ENV['_RAMDISK_MGR'])
   ```

2. Usage (line 120):
   ```python
   # Before:
   subprocess.run(['/bin/bash', str(_EPHEMERAL_RUN)], check=False)
   # After:
   subprocess.run(['/bin/bash', str(_RAMDISK_MGR_RUN)], check=False)
   ```

---

### `infra/_framework-pkg/_framework/README.md` — modify (de3-runner)

Update the tool directory table row:
```
# Before:
| `_ephemeral/` | RAM-backed directory management. `ephemeral` reads `framework.ephemeral_dirs` from `framework.yaml` and mounts each declared directory as a `tmpfs` (Linux) or HFS+ RAM disk (macOS). Idempotent — skipped if already mounted with matching parameters; remounts on size change; applies `chmod`/`chown` on mode/owner change. Skips silently in CI. |
| `_human-only-scripts/` | Standalone utilities for manual operator use (e.g. `setup-ephemeral-dirs`, `purge-gcs-status`). Not invoked by automation. |

# After:
| `_ramdisk-mgr/` | RAM-backed directory management. `ramdisk-mgr` reads `framework_ramdisk_dirs.yaml` and mounts each declared directory as a `tmpfs` (Linux) or HFS+ RAM disk (macOS). Idempotent — skipped if already mounted with matching parameters; remounts on size change; applies `chmod`/`chown` on mode/owner change. Skips silently in CI. |
| `_human-only-scripts/` | Standalone utilities for manual operator use (e.g. `setup-ramdisk-mounts`, `purge-gcs-status`). Not invoked by automation. |
```

---

### `infra/_framework-pkg/_docs/framework/config-files.md` — modify (de3-runner)

Update the table row:
```
# Before:
| `framework_ephemeral_dirs.yaml` | `config/` | Deployment |

# After:
| `framework_ramdisk_dirs.yaml` | `config/` | Deployment |
```

---

### `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_ephemeral_dirs.yaml` — delete (pwy-home-lab-pkg)

Already staged for deletion (`git status` shows `D`). Confirm deletion with `git rm` if not already done. No replacement file is needed — the framework default (`framework_ramdisk_dirs.yaml`) already uses `size_mb: 64`, which is appropriate.

---

### `infra/pwy-home-lab-pkg/_config/_framework_settings/README.md` — verify (pwy-home-lab-pkg)

This file is shown as modified (`M`) in git status. Verify it does not contain any `ephemeral` references that need updating. If it mentions `framework_ephemeral_dirs.yaml`, update to `framework_ramdisk_dirs.yaml`.

---

## Execution Order

1. **de3-runner** — rename directory and scripts:
   - `git mv _ephemeral/ _ramdisk-mgr/`
   - `git mv _ramdisk-mgr/ephemeral _ramdisk-mgr/ramdisk-mgr`
   - `git mv _ramdisk-mgr/ephemeral.sh _ramdisk-mgr/ramdisk-mgr.sh`
   - `git mv _human-only-scripts/setup-ephemeral-dirs/ _human-only-scripts/setup-ramdisk-mounts/`
   - `git mv setup-ramdisk-mounts/setup-ephemeral-dirs setup-ramdisk-mounts/setup-ramdisk-mounts`

2. **de3-runner** — update script internals:
   - Edit `ramdisk-mgr` script (string literals, variable names, YAML key reference)
   - Edit `ramdisk-mgr.sh` (comments and usage block only — logic unchanged)
   - Edit `setup-ramdisk-mounts` (fix stale `_ephemeral/run` reference)

3. **de3-runner** — rename + update config file:
   - `git mv framework_ephemeral_dirs.yaml framework_ramdisk_dirs.yaml`
   - Update YAML key `framework_ephemeral_dirs:` → `framework_ramdisk_dirs:` and env var reference
   - Update comments (run command, field descriptions)

4. **de3-runner** — update `set_env.sh`:
   - `_EPHEMERAL` → `_RAMDISK_MGR`, path updated
   - `_EPHEMERAL_DIR` → `_RAMDISK_DIR`, subdir `ephemeral` → `ramdisk`
   - PATH loop entry updated
   - `mkdir -p` call updated

5. **de3-runner** — update `_git_root/run`:
   - Variable name `_EPHEMERAL_RUN` → `_RAMDISK_MGR_RUN`
   - `ENV['_EPHEMERAL']` → `ENV['_RAMDISK_MGR']`

6. **de3-runner** — update docs:
   - `_framework/README.md` — table rows
   - `_docs/framework/config-files.md` — table row

7. **de3-runner** — update `_ramdisk-mgr/README.md`

8. **de3-runner** — commit all changes together

9. **pwy-home-lab-pkg** — confirm `framework_ephemeral_dirs.yaml` is deleted (`git rm` if not already staged)

10. **pwy-home-lab-pkg** — check `infra/pwy-home-lab-pkg/_config/_framework_settings/README.md` for ephemeral refs

11. **pwy-home-lab-pkg** — sync de3-runner to pick up the renamed scripts (`pkg-mgr sync` or `./run --sync-packages`)

12. **pwy-home-lab-pkg** — commit

---

## Verification

After execution:

```bash
# Confirm no stale "ephemeral" references remain in script/config code
# (excluding ai-log/ai-plans historical docs and MaaS "ephemeral installer" refs):
grep -r "_ephemeral\|EPHEMERAL\|ephemeral_dirs\|framework_ephemeral\|setup-ephemeral" \
  /home/pyoung/git/de3-ext-packages/de3-runner/main/infra/_framework-pkg/_framework/ \
  /home/pyoung/git/de3-ext-packages/de3-runner/main/infra/_framework-pkg/_config/ \
  /home/pyoung/git/pwy-home-lab-pkg/set_env.sh \
  2>/dev/null

# Source set_env.sh and confirm new vars are exported
source /home/pyoung/git/pwy-home-lab-pkg/set_env.sh
echo "_RAMDISK_MGR=$_RAMDISK_MGR"
echo "_RAMDISK_DIR=$_RAMDISK_DIR"

# Confirm new config file is parseable
python3 -c "import yaml; cfg=yaml.safe_load(open('$_FRAMEWORK_PKG_DIR/_config/_framework_settings/framework_ramdisk_dirs.yaml')); print(cfg)"

# Confirm ramdisk-mgr is on PATH
which ramdisk-mgr
```
