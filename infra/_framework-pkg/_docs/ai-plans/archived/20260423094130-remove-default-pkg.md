# Plan: Remove All `default-pkg` References

## Objective

Replace every surviving reference to the old framework package name `default-pkg` with
the correct new name `_framework-pkg` (or the correct new path when the file was also
reorganised). There are 13 affected locations across 9 files. The rename is purely
mechanical for most cases; two locations require a path correction because the file was
moved into a `_framework_settings/` subdirectory when the package was restructured.

## Context

`default-pkg` was renamed to `_framework-pkg`. Most call-sites were updated, but the
following were missed. None of the changes below touch infrastructure logic — they fix
broken/stale references to a directory that no longer exists under the old name.

Key facts discovered during research:

- `infra/_framework-pkg/_setup/run` — **exists** (confirmed). All six `_setup/run`
  fallback callers can safely point here.
- `infra/_framework-pkg/_framework/_generate-inventory/` — **exists**. The archived
  `query-unifi-switch` script must be updated for historical accuracy (the script is
  archived and not on the hot path, but the broken path is confusing).
- `infra/default-pkg/_config/framework_backend.yaml` → the file was also **moved** into
  `_framework_settings/`; it now lives at
  `infra/_framework-pkg/_config/_framework_settings/framework_backend.yaml` (also
  mirrored in `infra/pwy-home-lab-pkg/_config/_framework_settings/`). The maas playbooks
  must use `_FRAMEWORK_PKG_DIR` env var (always set by `set_env.sh`) rather than a
  hardcoded path.
- `config/tmp/dynamic/config/pwy-home-lab-pkg.yaml` — **generated file** in `config/tmp/`.
  The source YAML already has `_framework-pkg/_modules`. This file will self-correct the
  next time the config generation runs; no manual edit needed.
- `.claude/settings.local.json` contains four stale `sed` allow-list entries from the
  original partial rename. They can be removed.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### Occurrence Table

| # | File | Line(s) | Old value | New value | Notes |
|---|------|---------|-----------|-----------|-------|
| 1 | `.gitignore` | 12 | `infra/default-pkg/_scripts/human-only/setup/pkg-mgr/run sync` | `infra/_framework-pkg/_framework/_pkg-mgr/pkg-mgr sync` | Comment only; script is now named `pkg-mgr`, lives in `_framework/_pkg-mgr/` |
| 2 | `infra/de3-gui-pkg/_setup/run` | 23–24 | `infra/default-pkg/_setup/run` | `infra/_framework-pkg/_setup/run` | Target exists; string replace |
| 3 | `infra/image-maker-pkg/_setup/run` | 17–18 | `infra/default-pkg/_setup/run` | `infra/_framework-pkg/_setup/run` | Target exists; string replace |
| 4 | `infra/maas-pkg/_setup/run` | 19–20 | `infra/default-pkg/_setup/run` | `infra/_framework-pkg/_setup/run` | Target exists; string replace |
| 5 | `infra/mesh-central-pkg/_setup/run` | 14–15 | `infra/default-pkg/_setup/run` | `infra/_framework-pkg/_setup/run` | Target exists; string replace |
| 6 | `infra/proxmox-pkg/_setup/run` | 16–17 | `infra/default-pkg/_setup/run` | `infra/_framework-pkg/_setup/run` | Target exists; string replace |
| 7 | `infra/unifi-pkg/_setup/run` | 14–15 | `infra/default-pkg/_setup/run` | `infra/_framework-pkg/_setup/run` | Target exists; string replace |
| 8 | `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-gate/playbook.yaml` | 41 | `{{ lookup('env', 'GIT_ROOT') }}/infra/default-pkg/_config/framework_backend.yaml` | `{{ lookup('env', '_FRAMEWORK_PKG_DIR') }}/_config/_framework_settings/framework_backend.yaml` | File also moved to `_framework_settings/`; use `_FRAMEWORK_PKG_DIR` env var (always set by `set_env.sh`) |
| 9 | `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-sanity/playbook.yaml` | 31 | `{{ lookup('env', 'GIT_ROOT') }}/infra/default-pkg/_config/framework_backend.yaml` | `{{ lookup('env', '_FRAMEWORK_PKG_DIR') }}/_config/_framework_settings/framework_backend.yaml` | Same fix as #8 |
| 10 | `infra/_framework-pkg/_framework/_ai-only-scripts/archived/query-unifi-switch/run` | 26 | `infra/default-pkg/_generate-inventory/inventory/localhost.yaml` | `infra/_framework-pkg/_framework/_generate-inventory/inventory/localhost.yaml` | Archived script; fix for historical accuracy |
| 11 | `infra/de3-gui-pkg/_application/de3-gui/state/defaults.yaml` | 51 | `default-pkg: false` | `_framework-pkg: false` | UI package filter; old key will appear as unknown package in GUI |
| 12 | `config/tmp/dynamic/config/pwy-home-lab-pkg.yaml` | multiple | `_modules_dir: default-pkg/_modules` | n/a — generated file | Source YAML already correct; self-fixes on next config-gen run. No edit needed. |
| 13 | `.claude/settings.local.json` | 24–27 | Four `Bash(sed -i 's\|default-pkg\|...')` allow entries | Remove the four entries | Stale one-time patch permissions; already executed, now just noise |

---

### `.gitignore` — modify

**Line 12** — update comment to reflect the renamed script and directory:

```
# Remote package repo clones (recreate with: infra/_framework-pkg/_framework/_pkg-mgr/pkg-mgr sync)
```

---

### `infra/de3-gui-pkg/_setup/run` — modify

Lines 23–24: replace both `default-pkg` occurrences with `_framework-pkg`.

---

### `infra/image-maker-pkg/_setup/run` — modify

Lines 17–18: replace both `default-pkg` occurrences with `_framework-pkg`.

---

### `infra/maas-pkg/_setup/run` — modify

Lines 19–20: replace both `default-pkg` occurrences with `_framework-pkg`.

---

### `infra/mesh-central-pkg/_setup/run` — modify

Lines 14–15: replace both `default-pkg` occurrences with `_framework-pkg`.

---

### `infra/proxmox-pkg/_setup/run` — modify

Lines 16–17: replace both `default-pkg` occurrences with `_framework-pkg`.

---

### `infra/unifi-pkg/_setup/run` — modify

Lines 14–15: replace both `default-pkg` occurrences with `_framework-pkg`.

---

### `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-gate/playbook.yaml` — modify

Line 41 — change the `include_vars` file path:

```yaml
# Before:
        file: "{{ lookup('env', 'GIT_ROOT') }}/infra/default-pkg/_config/framework_backend.yaml"
# After:
        file: "{{ lookup('env', '_FRAMEWORK_PKG_DIR') }}/_config/_framework_settings/framework_backend.yaml"
```

---

### `infra/maas-pkg/_wave_scripts/test-ansible-playbooks/maas/maas-lifecycle-sanity/playbook.yaml` — modify

Line 31 — same change as above.

---

### `infra/_framework-pkg/_framework/_ai-only-scripts/archived/query-unifi-switch/run` — modify

Line 26 — update inventory path:

```bash
# Before:
  -i "$GIT_ROOT/infra/default-pkg/_generate-inventory/inventory/localhost.yaml" \
# After:
  -i "$GIT_ROOT/infra/_framework-pkg/_framework/_generate-inventory/inventory/localhost.yaml" \
```

---

### `infra/de3-gui-pkg/_application/de3-gui/state/defaults.yaml` — modify

Line 51 — rename the package filter key:

```yaml
# Before:
      default-pkg: false
# After:
      _framework-pkg: false
```

---

### `.claude/settings.local.json` — modify

Remove the four stale sed allow-list entries (lines 24–27):
```json
"Bash(sed -i 's|infra/default-pkg|infra/_framework-pkg|g' CLAUDE.md)",
"Bash(sed -i 's|default-pkg|_framework-pkg|g' .claude/commands/readme-review.md)",
"Bash(sed -i 's|infra/default-pkg|infra/_framework-pkg|g' /home/pyoung/git/pwy-home-lab-pkg/CLAUDE.md)",
"Bash(sed -i 's|default-pkg|_framework-pkg|g' /home/pyoung/git/pwy-home-lab-pkg/.claude/commands/readme-review.md)"
```

---

## Execution Order

1. Fix six `_setup/run` scripts (entries 2–7) — simple string replace, no dependencies.
2. Fix two maas playbooks (entries 8–9) — path correction, same pattern.
3. Fix archived ai-only script (entry 10) — path correction.
4. Fix `de3-gui-pkg` defaults.yaml (entry 11) — key rename.
5. Fix `.gitignore` comment (entry 1) — comment only.
6. Clean `.claude/settings.local.json` (entry 13) — remove stale entries.
7. Skip `config/tmp/dynamic/…` (entry 12) — generated, self-corrects.
8. Bump `_framework-pkg` version + add `version_history.md` entry (package code changed).
9. Write ai-log entry.
10. Commit everything.

## Verification

After execution:

```bash
# Must return no results (excluding venv/pycache/ai-log/logs/md files):
grep -R 'default-pkg' \
  --include='*.yaml' --include='*.yml' --include='*.hcl' --include='*.tf' \
  --include='*.sh' --include='*.py' --include='*.json' \
  2>/dev/null | grep -Ev 'venv|pycache|ai-log|\.terragrunt-cache|config/tmp'

# Must return no results for shell scripts:
grep -Rn 'default-pkg' --include='run' --include='*.sh' | grep -Ev 'venv|pycache'

# gitignore check:
grep 'default-pkg' .gitignore  # should return nothing
```
