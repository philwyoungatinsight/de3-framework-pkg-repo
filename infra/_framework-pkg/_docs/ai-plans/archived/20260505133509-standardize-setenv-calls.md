# Plan: Standardize set_env.sh Bootstrap Calls Across Framework Scripts

## Objective

Document the definitive standard for how scripts source `set_env.sh`, and fix every
framework script that deviates from it. The standard was established during the
bootstrap env-var refactor (plan `review-concept-of-main-package-and-framework-package-env-vars`)
but was not fully back-applied to `ramdisk-mgr`, `write-exit-status`, `sops-mgr`, and
`clean-all`. This plan fixes those scripts and adds a reference document so the
pattern is unambiguous for future scripts.

## Context

### The bootstrap problem

Framework tool bash entry-points do `cd "${SCRIPT_DIR}" && exec python3 -m module` (or
`exec python3 script.py`). After that `cd`, any `git rev-parse --show-toplevel` inside
Python resolves to the **framework repo clone**, not the consumer repo. The fix is to
set `_FRAMEWORK_PKG_DIR` from `BASH_SOURCE[0]` before sourcing `set_env.sh`, and have
Python tools read `_FRAMEWORK_PKG_DIR` from the environment instead of calling git.

### Four categories of scripts

| Category | Description | Standard |
|----------|-------------|---------|
| **A** | Framework bash entry-points (know their location in the tree) | Set `SCRIPT_DIR`, compute `_FRAMEWORK_PKG_DIR`, source via env var |
| **B** | Framework bash hooks always called by framework (tg-hooks) | Require `_FRAMEWORK_PKG_DIR` already set (`:?` guard) |
| **C** | Consumer bash scripts that may be called standalone | `git rev-parse --show-toplevel` (never cd to framework dir) |
| **D** | Python framework entry-points | Check `_FRAMEWORK_PKG_DIR` env var first, fallback to git |

### Violations found

| Script | Problem |
|--------|---------|
| `ramdisk-mgr` | Uses `_SCRIPT_DIR` (underscore prefix); sources `set_env.sh` inside mode blocks, not at top; redundant `GIT_ROOT=...` inside mode blocks |
| `write-exit-status` | `git rev-parse` without `_FRAMEWORK_PKG_DIR` — should use `:?` guard (Category B) |
| `sops-mgr` | `_source_env()` calls `git rev-parse` without checking `_FRAMEWORK_PKG_DIR` first |
| `clean-all` | `_git_root()` calls `git rev-parse` without checking `_FRAMEWORK_PKG_DIR` first |

### Scripts already conformant

- `config-mgr`, `unit-mgr`, `fw-repos-diagram-exporter`, `pkg-mgr`, `generate-inventory/run` — Category A ✓
- `framework-utils.sh` — Category B `:?` guard ✓
- `wave-mgr`, `fw-repo-mgr`, `config_mgr/main.py`, `unit_mgr/main.py`, `fw_repos_diagram_exporter/config.py` — Category D ✓
- Consumer `_setup/run`, `_wave_scripts/...run`, `_tg_scripts/...run` — Category C ✓ (correct for standalone scripts)
- `gpg-mgr` — intentionally does NOT source set_env.sh (called FROM it) ✓
- `maas-state-cache.sh` — checks `_FRAMEWORK_PKG_DIR` first ✓

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `infra/_framework-pkg/_docs/set-env-bootstrap-standard.md` — create

New reference document defining the four categories with copy-paste examples. Content:

```markdown
# set_env.sh Bootstrap Standard

Every script that needs framework env vars must source `set_env.sh`. This document
defines the correct pattern for each script category. Use the category that matches
where your script lives and how it is called.

## Category A — Framework bash entry-points

**Where**: scripts in `_FRAMEWORK_PKG_DIR/_framework/<tool>/` that are run directly
or added to `$PATH` via set_env.sh.

**Rule**: set `SCRIPT_DIR` and `_FRAMEWORK_PKG_DIR` from `BASH_SOURCE[0]`, then source
`set_env.sh` immediately — BEFORE argument parsing.

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# Compute depth from SCRIPT_DIR to _FRAMEWORK_PKG_DIR for this tool's location.
# Tools at _framework/<tool>/<tool>: SCRIPT_DIR/../.. = _FRAMEWORK_PKG_DIR
export _FRAMEWORK_PKG_DIR="${_FRAMEWORK_PKG_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
. "$_FRAMEWORK_PKG_DIR/../../set_env.sh"
```

**Why not git rev-parse**: these scripts exec Python after `cd SCRIPT_DIR`. Any
git call inside Python would resolve to the framework repo, not the consumer repo.

## Category B — Framework bash hooks (always called by framework)

**Where**: tg-hooks, utilities called exclusively from within the framework context
(terragrunt hooks, wave-mgr, etc.). `_FRAMEWORK_PKG_DIR` is always in the environment.

**Rule**: require `_FRAMEWORK_PKG_DIR` to be set; fail loudly if not.

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
. "${_FRAMEWORK_PKG_DIR:?_FRAMEWORK_PKG_DIR must be set}/../../set_env.sh"
```

**Why not git rev-parse**: these scripts are never called standalone; git rev-parse
is unnecessary overhead, and failing loudly makes misconfiguration obvious.

## Category C — Consumer bash scripts (standalone-callable)

**Where**: `infra/<pkg>/_setup/`, `infra/<pkg>/_wave_scripts/`,
`infra/<pkg>/_tg_scripts/`. May be called by hand from the consumer repo root.

**Rule**: use `git rev-parse --show-toplevel` as the root — it is always correct here
because these scripts never cd to the framework directory.

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
GIT_ROOT="$(git rev-parse --show-toplevel)"
. "$GIT_ROOT/set_env.sh"
```

## Category D — Python framework entry-points

**Where**: Python scripts that are the entry-point of a framework tool and need the
consumer repo root.

**Rule**: check `_FRAMEWORK_PKG_DIR` first (set by the bash wrapper that launched
this Python process); fall back to git only if missing.

```python
_fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
if _fw_pkg:
    git_root = str(Path(_fw_pkg).parent.parent)
else:
    git_root = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    ).strip()
```

## Quick Reference

| Script location | Call context | Category |
|----------------|-------------|----------|
| `_framework/<tool>/<tool>` (bash) | Direct / $PATH | A |
| `_framework/_utilities/tg-scripts/` | Terragrunt hook | B |
| `infra/<pkg>/_tg_scripts/` | Terragrunt hook / standalone | C |
| `infra/<pkg>/_wave_scripts/` | wave-mgr / standalone | C |
| `infra/<pkg>/_setup/` | Standalone | C |
| `_framework/<tool>/` (Python, after bash cd) | Via bash wrapper | D |
```

### `infra/_framework-pkg/_framework/_ramdisk-mgr/ramdisk-mgr` — modify

Three changes:
1. `_SCRIPT_DIR` → `SCRIPT_DIR` on the first line after `set -euo pipefail`.
2. Move `. "$_FRAMEWORK_PKG_DIR/../../set_env.sh"` to immediately after the `export _FRAMEWORK_PKG_DIR` line (before the `# Argument parsing` section).
3. Remove the two redundant `GIT_ROOT="$(dirname "$(dirname "$_FRAMEWORK_PKG_DIR")")"` lines from the setup and teardown mode blocks (set_env.sh is already sourced at this point).

Result — top of file should be:
```bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
export _FRAMEWORK_PKG_DIR="${_FRAMEWORK_PKG_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
. "$_FRAMEWORK_PKG_DIR/../../set_env.sh"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
```

Setup mode block (line ~68): remove `GIT_ROOT=...` and `source "$_FRAMEWORK_PKG_DIR/../../set_env.sh"`:
```bash
# BEFORE:
if [[ "$MODE" == "setup" ]]; then
    GIT_ROOT="$(dirname "$(dirname "$_FRAMEWORK_PKG_DIR")")"
    source "$_FRAMEWORK_PKG_DIR/../../set_env.sh"
    ...

# AFTER:
if [[ "$MODE" == "setup" ]]; then
    ...
```

Teardown mode block: same — remove the two lines.

### `infra/_framework-pkg/_framework/_utilities/tg-scripts/write-exit-status/write-exit-status` — modify

Replace the `git rev-parse` source with the Category B pattern. Add `SCRIPT_DIR` for consistency. Change:
```bash
# BEFORE:
source "$(git rev-parse --show-toplevel)/set_env.sh"

# AFTER:
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
. "${_FRAMEWORK_PKG_DIR:?_FRAMEWORK_PKG_DIR must be set}/../../set_env.sh"
```

The script lives at `_FRAMEWORK_PKG_DIR/_framework/_utilities/tg-scripts/write-exit-status/`.
`set_env.sh` path: `_FRAMEWORK_PKG_DIR/../../set_env.sh` ✓ (same as framework-utils.sh).

### `infra/_framework-pkg/_framework/_sops-mgr/sops-mgr` — modify

Update `_source_env()` to check `_FRAMEWORK_PKG_DIR` first (Category D). Change:
```python
# BEFORE:
def _source_env() -> dict:
    git_root = subprocess.check_output(
        ['git', 'rev-parse', '--show-toplevel'], text=True
    ).strip()
    raw = subprocess.check_output(
        ['bash', '-c', f'source {git_root}/set_env.sh && env -0'],
        text=True,
    )

# AFTER:
def _source_env() -> dict:
    _fw_pkg = os.environ.get('_FRAMEWORK_PKG_DIR')
    if _fw_pkg:
        git_root = str(Path(_fw_pkg).parent.parent)
    else:
        git_root = subprocess.check_output(
            ['git', 'rev-parse', '--show-toplevel'], text=True
        ).strip()
    raw = subprocess.check_output(
        ['bash', '-c', f'source {git_root}/set_env.sh && env -0'],
        text=True,
    )
```

(`Path` is already imported in sops-mgr.)

### `infra/_framework-pkg/_framework/_clean_all/clean-all` — modify

Update `_git_root()` to check `_FRAMEWORK_PKG_DIR` first (Category D). Change:
```python
# BEFORE:
def _git_root():
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ERROR: not in a git repository")
    return Path(r.stdout.strip())

# AFTER:
def _git_root():
    fw_pkg = os.environ.get("_FRAMEWORK_PKG_DIR")
    if fw_pkg:
        return Path(fw_pkg).parent.parent
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("ERROR: not in a git repository")
    return Path(r.stdout.strip())
```

(`os` and `Path` are already imported in clean-all.)

### `infra/_framework-pkg/_docs/README.md` (or relevant section) — no change needed

The standard doc is self-contained. No existing README covers this.

## Execution Order

1. **Create `set-env-bootstrap-standard.md`** — write the reference doc first so the plan commits it as its anchor.
2. **Fix `ramdisk-mgr`** — bash fix; self-contained, no deps.
3. **Fix `write-exit-status`** — bash fix; self-contained.
4. **Fix `sops-mgr`** — Python fix; self-contained.
5. **Fix `clean-all`** — Python fix; self-contained.

All five steps are independent and can be reviewed in order.

## Verification

```bash
# 1. Source set_env.sh fresh — ramdisk-mgr is called from startup checks
unset _FRAMEWORK_PKG_DIR _UTILITIES_DIR
source set_env.sh
echo "ramdisk-mgr OK: $_RAMDISK_MGR"

# 2. Confirm no _SCRIPT_DIR variable in ramdisk-mgr
grep '_SCRIPT_DIR' infra/_framework-pkg/_framework/_ramdisk-mgr/ramdisk-mgr
# should print nothing

# 3. Confirm set_env.sh source is before argument parsing in ramdisk-mgr
grep -n "set_env\|# Argument parsing\|while \[\[" infra/_framework-pkg/_framework/_ramdisk-mgr/ramdisk-mgr | head -10
# set_env line number should be LOWER than Argument parsing line

# 4. Confirm write-exit-status uses _FRAMEWORK_PKG_DIR pattern
grep "git rev-parse" infra/_framework-pkg/_framework/_utilities/tg-scripts/write-exit-status/write-exit-status
# should print nothing

# 5. Confirm sops-mgr checks _FRAMEWORK_PKG_DIR
grep "_FRAMEWORK_PKG_DIR\|git rev-parse" infra/_framework-pkg/_framework/_sops-mgr/sops-mgr
# should show _FRAMEWORK_PKG_DIR check, no bare git rev-parse call

# 6. Confirm clean-all checks _FRAMEWORK_PKG_DIR
grep "_FRAMEWORK_PKG_DIR\|git rev-parse" infra/_framework-pkg/_framework/_clean_all/clean-all | head -5
# should show _FRAMEWORK_PKG_DIR check in _git_root()

# 7. Grep for any remaining non-conformant git rev-parse calls in framework scripts
grep -r "git rev-parse" \
  infra/_framework-pkg/_framework/ \
  --include="*.sh" --include="*.py" | grep -v "^Binary\|#.*git rev-parse"
# should show zero hits (or only in string literals / error messages)
```
