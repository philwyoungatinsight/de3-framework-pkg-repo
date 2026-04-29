# Plan: Consolidate Top-Level Dirs into default-pkg

**Goal:** Move all framework code, config, docs, scripts, and utilities that currently live outside `infra/` into `infra/default-pkg/`, leaving only true entry-points at the repo root (`run`, `Makefile`, `set_env.sh`, `root.hcl`, `CLAUDE.md`, `.sops.yaml`, `.gitlab-ci.yml`, `.gitignore`).

---

## Design Decisions

### New `_`-prefixed dirs in `infra/default-pkg/`
| New dir | Source | Notes |
|---|---|---|
| `_config/` (already exists) | `config/` | Merge; keep runtime `tmp/` subdir here |
| `_docs/` (already exists, has `.gitkeep`) | `docs/` | Merge with existing `README.md` |
| `_scripts/` | `scripts/` | Keep `ai-only/` and `human-only/` subdirs |
| `_utilities/` | `utilities/` | Direct move; all content |
| `_clean_all/` (already exists, empty) | `framework/clean-all/` | Populate with `run` script |
| `_ephemeral/` | `framework/ephemeral/` | New dir |
| `_generate-inventory/` | `framework/generate-ansible-inventory/` | New dir |
| `_unit-mgr/` | `framework/unit-mgr/` | New dir |
| `_pkg-mgr/` | `framework/pkg-mgr/` | New dir |

### Config files (`config/` → `_config/`)
- All `.yaml` files, `tech-debt/` subdir, `.gitignore`, `README.md` move into `infra/default-pkg/_config/`
- Runtime dir `config/tmp/` becomes `infra/default-pkg/_config/tmp/` — `_CONFIG_TMP_DIR` updated in `set_env.sh`
- `.sops.yaml` at repo root stays at repo root — SOPS walks up the tree from encrypted files, so root-level `.sops.yaml` covers all subdirs. The symlink in `config/` is removed.
- `framework.yaml` and `waves_ordering.yaml`: `run` already has fallback logic searching `infra/*/_config/` — **no code change needed**.

### Docs (`docs/` → `_docs/`)
- All content moves directly; existing `infra/default-pkg/_docs/README.md` (which describes default-pkg roles) is kept as `_docs/default-pkg-overview.md` and the new top-level `README.md` takes over from `docs/README.md`.

### Scripts (`scripts/` → `_scripts/`)
- `ai-only-scripts/` → `_scripts/ai-only/`
- `human-only-scripts/` → `_scripts/human-only/`
- CLAUDE.md script placement table updated to reflect new paths.

### Utilities (`utilities/` → `_utilities/`)
- Direct subtree move; no internal path changes needed because utilities are addressed via `$_UTILITIES_DIR` env var.

### Framework tools (`framework/` → subfolders under default-pkg)
- Each tool directory becomes its own `_`-prefixed sibling in `default-pkg/`.
- After all moves `framework/` is empty and deleted.

---

## Files to Modify

### 1. `set_env.sh`
Change 4 exported path variables and 2 hardcoded script calls:

```bash
# Before → After
_UTILITIES_DIR="$_GIT_ROOT/utilities"                              → "$_GIT_ROOT/infra/default-pkg/_utilities"
_ANSIBLE_ROLES_DIR="$_UTILITIES_DIR/ansible/roles"                → (unchanged — derived from _UTILITIES_DIR)
_CONFIG_TMP_DIR="$_GIT_ROOT/config/tmp"                           → "$_GIT_ROOT/infra/default-pkg/_config/tmp"
_GENERATE_INVENTORY="$_GIT_ROOT/framework/generate-ansible-inventory/run"  → "$_GIT_ROOT/infra/default-pkg/_generate-inventory/run"

python3 "$_GIT_ROOT/utilities/python/validate-config.py"          → python3 "$_UTILITIES_DIR/python/validate-config.py"
bash "$_GIT_ROOT/framework/ephemeral/run"                         → bash "$_GIT_ROOT/infra/default-pkg/_ephemeral/run"
```

### 2. `run` (Python, lines 121–125 and 455)
```python
# Before → After
FRAMEWORK_DIR    = STACK_ROOT / 'framework'                         → (remove; no longer used as a dir)
GENERATE_INVENTORY = FRAMEWORK_DIR / 'generate-ansible-inventory/run' → STACK_ROOT / 'infra/default-pkg/_generate-inventory/run'
NUKE_ALL           = FRAMEWORK_DIR / 'clean-all/run'               → STACK_ROOT / 'infra/default-pkg/_clean_all/run'
INIT_SH            = STACK_ROOT / 'utilities/bash/init.sh'         → STACK_ROOT / 'infra/default-pkg/_utilities/bash/init.sh'
```

### 3. `CLAUDE.md`
- Script placement table: `scripts/ai-only-scripts/` → `infra/default-pkg/_scripts/ai-only/`, `scripts/human-only-scripts/` → `infra/default-pkg/_scripts/human-only/`
- `set_env.sh` sourcing example remains identical (sourcing still lives at git root)
- `docs/ai-log/`, `docs/ai-plans/`, `docs/ai-screw-ups/` references → `infra/default-pkg/_docs/ai-log/` etc.
- `$_UTILITIES_DIR` and `$_CONFIG_TMP_DIR` are env-var references so they don't need path changes
- Add note: framework tools live under `infra/default-pkg/_<tool>/`

### 4. `README.md` (top-level)
- Update directory layout section to reflect new structure.

### 5. Scripts with hardcoded paths (audit required)
The following may have hardcoded references to `utilities/`, `scripts/`, `docs/`, or `config/` that don't go through env vars — check each at execution time:
- `scripts/ai-only-scripts/*/run` — use `GIT_ROOT` + relative path; grep for `utilities/`, `config/`, `docs/`
- `scripts/human-only-scripts/*/run`
- `framework/*/run` — these move, but may reference sibling scripts
- `utilities/bash/*.sh` — check for internal cross-references

---

## Execution Order

Move operations are git `mv` to preserve history:

1. **Config**
   ```bash
   git mv config/framework.yaml          infra/default-pkg/_config/
   git mv config/waves_ordering.yaml     infra/default-pkg/_config/
   git mv config/gcp_seed.yaml           infra/default-pkg/_config/
   git mv config/gcp_seed_secrets.sops.yaml infra/default-pkg/_config/
   git mv config/framework_packages.yaml infra/default-pkg/_config/
   git mv config/framework_package_repositories.yaml infra/default-pkg/_config/
   git mv config/tech-debt               infra/default-pkg/_config/tech-debt
   git mv config/README.md               infra/default-pkg/_docs/config-overview.md
   # Remove config/.sops.yaml symlink (root .sops.yaml covers everything)
   # Update config/.gitignore → infra/default-pkg/_config/.gitignore
   # config/tmp/ is runtime-generated; remove from git and let set_env.sh recreate at new path
   ```

2. **Docs**
   ```bash
   # Rename existing _docs/README.md to _docs/default-pkg-overview.md first
   git mv infra/default-pkg/_docs/README.md infra/default-pkg/_docs/default-pkg-overview.md
   git mv docs/README.md         infra/default-pkg/_docs/README.md
   git mv docs/ai-log            infra/default-pkg/_docs/ai-log
   git mv docs/ai-log-summary    infra/default-pkg/_docs/ai-log-summary
   git mv docs/ai-plans          infra/default-pkg/_docs/ai-plans
   git mv docs/ai-screw-ups      infra/default-pkg/_docs/ai-screw-ups
   git mv docs/framework         infra/default-pkg/_docs/framework
   git mv docs/claude-md-history infra/default-pkg/_docs/claude-md-history
   git mv docs/*.md              infra/default-pkg/_docs/   # remaining loose files
   ```

3. **Scripts**
   ```bash
   mkdir -p infra/default-pkg/_scripts
   git mv scripts/ai-only-scripts  infra/default-pkg/_scripts/ai-only
   git mv scripts/human-only-scripts infra/default-pkg/_scripts/human-only
   git mv scripts/README.md        infra/default-pkg/_scripts/README.md
   ```

4. **Utilities**
   ```bash
   git mv utilities infra/default-pkg/_utilities
   ```

5. **Framework tools**
   ```bash
   git mv framework/clean-all/*             infra/default-pkg/_clean_all/
   git mv framework/ephemeral               infra/default-pkg/_ephemeral
   git mv framework/generate-ansible-inventory infra/default-pkg/_generate-inventory
   git mv framework/unit-mgr                infra/default-pkg/_unit-mgr
   git mv framework/pkg-mgr                 infra/default-pkg/_pkg-mgr
   # framework/ is now empty; remove it
   ```

6. **Update `set_env.sh`** — 4 variable path changes + 2 script call paths

7. **Update `run`** — GENERATE_INVENTORY, NUKE_ALL, INIT_SH path constants

8. **Audit and fix hardcoded paths** — grep all moved scripts for `utilities/`, `config/`, `docs/`, `scripts/`, `framework/`

9. **Update CLAUDE.md** — script paths, docs paths

10. **Update top-level `README.md`**

11. **Commit**

---

## Open Questions

1. **`config/tmp/` in `.gitignore`**: the top-level `config/.gitignore` currently ignores `tmp/`. After moving, `infra/default-pkg/_config/.gitignore` needs to ignore `tmp/`. Confirm this is sufficient or if root `.gitignore` also needs an entry for the new path.

2. **`framework/pkg-mgr/`**: the working directory is currently inside `framework/pkg-mgr/` — this suggests active work. Should `pkg-mgr` be moved as part of this plan or treated as a separate step once current work is committed?

3. **Wave scripts referencing `_docs/`**: some `wave-scripts` may log to `docs/ai-log/` via direct paths (not env vars). Grep required before moving docs.

4. **`.sops.yaml` symlink**: `config/.sops.yaml` is a symlink to `/.sops.yaml`. After moving, this symlink disappears. Encrypted files in `infra/default-pkg/_config/` will still find `/.sops.yaml` via SOPS's upward search. No action needed, but worth confirming SOPS version used here supports upward traversal (it does since v3).

5. **CI/CD** (`.gitlab-ci.yml`): may reference `docs/`, `scripts/`, `utilities/` with hardcoded paths. Check before executing.
