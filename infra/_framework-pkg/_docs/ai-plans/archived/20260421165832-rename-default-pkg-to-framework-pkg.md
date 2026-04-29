# Plan: Rename `_framework-pkg` → `_framework-pkg`

## Objective

Rename the `infra/_framework-pkg/` directory and all associated references to
`infra/_framework-pkg/`. The underscore prefix follows the repo's convention that
`_`-prefixed names are reserved/special — appropriate because this package IS the
framework that orchestrates all other packages.

## Scope

**82 files, ~513 occurrences.** This is a pure rename with no behavioural changes.

---

## Open Questions (resolve before executing)

1. **Environment variable name**: `_DEFAULT_PKG_DIR` → `_FRAMEWORK_PKG_DIR`?
   - Recommendation: yes, rename for consistency. All 20+ references must change atomically.
   - Alternative: keep `_DEFAULT_PKG_DIR` to avoid env-var churn in users' shells.

2. **YAML secrets key**: The secrets file is loaded and accessed via key `framework_secrets`
   (root.hcl line ~79). The file itself is currently named `_framework-pkg.secrets.yaml`.
   - Recommendation: rename file to `_framework-pkg.secrets.yaml`. Key stays `framework_secrets`.

3. **Version history comments in config yaml**: 11 historical version entries reference
   `_framework-pkg:` in comment lines. Rename them (clean history) or leave as-is (accurate history)?
   - Recommendation: update them — comments that say `_framework-pkg: 1.0.0` would be confusing.

4. **CLAUDE.md**: Contains ~4 references to `infra/_framework-pkg/`. Update as part of this plan.

5. **ai-log and ai-plans docs**: 30+ `.md` files in `_docs/ai-log/` and `_docs/ai-plans/archived/`
   reference `_framework-pkg` in historical narrative. Recommendation: leave historical docs unchanged
   (they describe what happened at the time); only update forward-facing docs like `_docs/README.md`,
   `_docs/framework/`, `_docs/known-pitfalls.md`, `_docs/idempotence-and-tech-debt.md`, CLAUDE.md.

---

## Files to Create / Rename

| Action | From | To |
|--------|------|----|
| Rename dir | `infra/_framework-pkg/` | `infra/_framework-pkg/` |
| Rename file | `infra/_framework-pkg/_config/_framework-pkg.yaml` | `infra/_framework-pkg/_config/_framework-pkg.yaml` |
| Rename file | `infra/_framework-pkg/_config/tmp/dynamic/config/_framework-pkg.yaml` | `infra/_framework-pkg/_config/tmp/dynamic/config/_framework-pkg.yaml` |
| Rename file | `infra/_framework-pkg/_docs/_framework-pkg-overview.md` | `infra/_framework-pkg/_docs/_framework-pkg-overview.md` |

---

## Files to Modify

### 1. YAML config (`_framework-pkg/_config/_framework-pkg.yaml`)
- Top-level key: `_framework-pkg:` → `_framework-pkg:`
- `_provides_capability: - _framework-pkg: 1.3.1` → `_provides_capability: - _framework-pkg: 1.3.1`
- All 11 version history comment entries: `_framework-pkg: X.Y.Z` → `_framework-pkg: X.Y.Z`

### 2. YAML config (`_framework-pkg/_config/framework_packages.yaml`)
- `- name: _framework-pkg` → `- name: _framework-pkg`

### 3. Environment / shell (`_framework-pkg/_framework/_git_root/set_env.sh`)
- `_DEFAULT_PKG_DIR=...infra/_framework-pkg` → `_FRAMEWORK_PKG_DIR=...infra/_framework-pkg`
- Update the `export` line
- Path string literal: `infra/_framework-pkg` → `infra/_framework-pkg`

### 4. Terragrunt root (`_framework-pkg/_framework/_git_root/root.hcl`)
- Line ~57: backend config path `infra/_framework-pkg/_config/...` → `infra/_framework-pkg/_config/...`
- Line ~77: `_fw_sec_path` value `_framework-pkg.secrets.yaml` → `_framework-pkg.secrets.yaml`
- Lines ~117, 120, 133, 134, 141, 148: comments + path strings `_framework-pkg/` → `_framework-pkg/`
- Variable name `DEFAULT_PKG_DIR` → `FRAMEWORK_PKG_DIR` (if env var renamed)

### 5. Terragrunt run (`_framework-pkg/_framework/_git_root/run`)
- `DEFAULT_PKG_DIR` variable → `FRAMEWORK_PKG_DIR`

### 6. Python utilities (hardcoded fallback paths + env var name)
All files below have the pattern:
`os.environ.get("_DEFAULT_PKG_DIR") or str(root / "infra" / "_framework-pkg")`
→ `os.environ.get("_FRAMEWORK_PKG_DIR") or str(root / "infra" / "_framework-pkg")`

- `_framework/_config-mgr/config_mgr/packages.py` (lines 13, 22)
- `_framework/_config-mgr/config_mgr/main.py` (lines 40, 147)
- `_framework/_unit-mgr/unit_mgr/main.py` (lines 44–46, 75, 190, 196)
- `_framework/_generate-inventory/generate_ansible_inventory.py` (lines 862, 865)
- `_framework/_utilities/python/framework_config.py` (line 30)
- `_framework/_utilities/python/validate-config.py` (lines 48, 150, 221)
- `_framework/_utilities/python/gcs_status.py` (line 12)

### 7. Bash utilities (hardcoded fallback paths + env var name)
- `_framework/_utilities/bash/gcs-status.sh` (lines 3, 8)
- `_framework/_human-only-scripts/purge-gcs-status/run` (line 26)
- `_framework/_clean_all/run` (1 reference)
- `_framework/_ephemeral/run` (1 reference)
- `_framework/_pkg-mgr/run` (3 references)
- `_setup/run`

### 8. Forward-facing documentation
- `infra/_framework-pkg/_docs/README.md`
- `infra/_framework-pkg/_docs/framework/waves.md`
- `infra/_framework-pkg/_docs/framework/skip-parameters.md`
- `infra/_framework-pkg/_docs/known-pitfalls.md`
- `infra/_framework-pkg/_docs/idempotence-and-tech-debt.md`
- `infra/_framework-pkg/_docs/ai-screw-ups/README.md`
- `/.claude/commands/readme-review.md`
- `/CLAUDE.md` (~4 path references)

### 9. README tracker
- `infra/_framework-pkg/_docs/readme-maintenance/README-tracker.md` — all path entries

---

## Design Decisions

### Why `_framework-pkg` not `framework-pkg`?
Underscore prefix signals "reserved/special" in this repo. The framework package is
not a domain package — it runs the other packages. Using `_` makes this clear at a
glance in directory listings.

### Why rename `_DEFAULT_PKG_DIR` → `_FRAMEWORK_PKG_DIR`?
The variable name is an internal framework detail (used in fallback paths, not exposed
to end-users). Renaming it keeps the codebase self-consistent. The only cost is
updating ~20 references; all of them are in the framework package itself.

### Historical docs: leave unchanged
`ai-log/` and `ai-plans/archived/` documents describe what happened at a specific
point in time. Updating them would be historically inaccurate. Only forward-facing
operational docs (framework guides, CLAUDE.md, known-pitfalls) get updated.

---

## Execution Strategy

Because this is a pure rename across many files, use `sed -i` / `find` with a
well-tested pattern rather than editing file-by-file. Key replacements in order:

```bash
# Step 1: rename the directory
git mv infra/_framework-pkg infra/_framework-pkg

# Step 2: rename config files
git mv infra/_framework-pkg/_config/_framework-pkg.yaml \
       infra/_framework-pkg/_config/_framework-pkg.yaml

# Step 3: bulk string replacements (run from repo root)
# Replace path strings
find infra/_framework-pkg -type f \( -name '*.py' -o -name '*.sh' -o -name '*.hcl' \
     -o -name '*.yaml' -o -name 'run' \) \
  | xargs sed -i 's|infra/_framework-pkg|infra/_framework-pkg|g'

# Replace env var name
find infra/_framework-pkg -type f \( -name '*.py' -o -name '*.sh' -o -name '*.hcl' \
     -o -name 'run' \) \
  | xargs sed -i 's|_DEFAULT_PKG_DIR|_FRAMEWORK_PKG_DIR|g'

# Replace YAML key / package name
find infra/_framework-pkg/\_config -name '*.yaml' \
  | xargs sed -i 's|_framework-pkg:|_framework-pkg:|g; s|name: _framework-pkg|name: _framework-pkg|g'

# Replace remaining path references in CLAUDE.md and .claude/
sed -i 's|infra/_framework-pkg|infra/_framework-pkg|g' CLAUDE.md
sed -i 's|infra/_framework-pkg|infra/_framework-pkg|g' .claude/commands/readme-review.md

# Step 4: update DEFAULT_PKG_DIR → FRAMEWORK_PKG_DIR in HCL/run files
find infra/_framework-pkg -type f \( -name '*.hcl' -o -name 'run' \) \
  | xargs sed -i 's|DEFAULT_PKG_DIR|FRAMEWORK_PKG_DIR|g'

# Step 5: verify no remaining references to "_framework-pkg" in non-historical files
grep -r "_framework-pkg" infra/_framework-pkg \
  --include="*.py" --include="*.sh" --include="*.hcl" \
  --include="*.yaml" --include="run" \
  --exclude-dir=ai-log --exclude-dir=archived
```

After bulk replacements: manual review of `root.hcl` (most complex file) and
`set_env.sh` (entry point) before committing.

---

## Verification Steps

1. `source infra/_framework-pkg/_framework/_git_root/set_env.sh` — no errors, `_FRAMEWORK_PKG_DIR` exported
2. `grep -r "_framework-pkg" infra/_framework-pkg --include="*.py" --include="*.hcl" --include="*.sh"` — zero results (excluding historical docs)
3. `cd infra/_framework-pkg/_framework/_git_root && terragrunt hcl-fmt --check` — no parse errors
4. `python3 infra/_framework-pkg/_framework/_utilities/python/validate-config.py` — exits 0
5. `make` dry-run (no actual build) to confirm framework initialises correctly
6. `grep -r "_framework-pkg" CLAUDE.md .claude/` — zero results

---

## Commit Strategy

Single commit titled:
`refactor(framework): rename _framework-pkg → _framework-pkg`

Include ai-log entry at:
`infra/_framework-pkg/_docs/ai-log/<timestamp>-rename-_framework-pkg-to-framework-pkg.md`

Bump `_provides_capability` in `_framework-pkg.yaml`:
- `1.3.1` → `1.4.0` (minor bump — package renamed, no behavioural change but breaking
  change for any external reference to the old name)
