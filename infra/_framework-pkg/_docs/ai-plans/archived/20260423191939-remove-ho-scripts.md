# Plan: Remove human-only-scripts Feature

## Objective

The `_human-only-scripts` directory concept is defunct — the directory is empty and the
feature is no longer used. Remove all traces: the empty directory, its entry in the
framework README, and item 4 of the Script Placement rule in both copies of CLAUDE.md
(root and the `_git_root` scaffold copy).

## Context

- `infra/_framework-pkg/_framework/_human-only-scripts/` exists but is empty (user already
  removed the scripts).
- The root `CLAUDE.md` is a symlink → `infra/_framework-pkg/_framework/_git_root/CLAUDE.md`.
  They are the same file. Only one edit is needed.
- `_git_root/CLAUDE.md` (line 150) lists it as decision step 4 in the Script Placement
  section:
  `4. Standalone utility (manual only) → infra/_framework-pkg/_scripts/human-only/<name>/`
  Note: the path in CLAUDE.md (`_scripts/human-only/`) differs from the actual directory
  (`_framework/_human-only-scripts/`) — the path was already stale.
- `infra/_framework-pkg/_framework/README.md` line 19 has a table row for `_human-only-scripts/`.
- `.idea/workspace.xml` has an IDE recents entry — not source code, safe to leave.
- All changes are in the de3-runner repo (`_ext_packages/de3-runner/main/`); committed there.
- The ai-only-scripts feature remains and is the correct replacement for any manual-operator
  scripts (per the existing CLAUDE.md rule: "If a temporary manual task is required, make
  an ai-only script and run it manually.").

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `infra/_framework-pkg/_framework/_human-only-scripts/` — delete directory

Remove the empty directory with `git rm -r` (or `rmdir` + `git add`).

```bash
git rm -r infra/_framework-pkg/_framework/_human-only-scripts/
```

If `git rm` fails because the directory has no tracked files, use:

```bash
rmdir infra/_framework-pkg/_framework/_human-only-scripts/
git add -u infra/_framework-pkg/_framework/_human-only-scripts/
```

### `infra/_framework-pkg/_framework/README.md` — modify

Remove the `_human-only-scripts/` table row (line 19):

**Remove:**
```
| `_human-only-scripts/` | Standalone utilities for manual operator use (e.g. `setup-ephemeral-dirs`, `purge-gcs-status`). Not invoked by automation. |
```

### `infra/_framework-pkg/_framework/_git_root/CLAUDE.md` — modify

Remove item 4 from the Script Placement decision list (line 150). Because the root
`CLAUDE.md` is a symlink to this file, editing this file updates both at once.

**Remove:**
```
4. Standalone utility (manual only) → `infra/_framework-pkg/_scripts/human-only/<name>/`
```

The list becomes 3 items; no renumbering needed since items 1–3 stay as-is.

## Execution Order

1. Delete the empty directory (`rmdir` since there are no tracked files in it).
2. Edit `infra/_framework-pkg/_framework/README.md` (remove table row).
3. Edit `infra/_framework-pkg/_framework/_git_root/CLAUDE.md` (remove item 4).
4. Write ai-log entry.
5. Commit all changes in the de3-runner repo.

## Verification

Run from the de3-runner repo root (`_ext_packages/de3-runner/main/`):

```bash
# No human-only references remain (except "human action required" in polling docs — unrelated)
grep -r "human-only" . --include="*.md" --include="*.yaml" --include="*.sh" --include="*.py" --include="*.hcl"

# Directory is gone
ls infra/_framework-pkg/_framework/_human-only-scripts/ 2>&1  # should: No such file or directory

# README table no longer has the row
grep "_human-only-scripts" infra/_framework-pkg/_framework/README.md  # should: no output

# CLAUDE.md clean (one file — symlink target)
grep "human-only" infra/_framework-pkg/_framework/_git_root/CLAUDE.md  # should: no output
```
