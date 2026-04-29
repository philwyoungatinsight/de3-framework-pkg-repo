# Relocate git-root files to `_framework/_git_root`

**Date**: 2026-04-20  
**Plan**: `ai-plans/archived/20260420163106-relocate-git-root-files.md`

## What was done

Moved 8 of the 9 plain files from the git root into
`infra/default-pkg/_framework/_git_root/` and replaced them with relative
symlinks pointing to the new location. The 9th file (`.gitignore`) was
discovered to be incompatible with symlinking and is kept as a real file.

**Files now living in `_git_root/` (symlinked from root):**
- `CLAUDE.md`, `.gitlab-ci.yml`, `Makefile`, `README.md`, `root.hcl`, `run`,
  `set_env.sh`, `.sops.yaml`

**File kept as real file at root:**
- `.gitignore` — git opens `.gitignore` with `O_NOFOLLOW` (confirmed via
  strace), so a symlink produces ELOOP and git silently ignores all exclusion
  rules. The real file must remain at the git root.

## Key discovery

Git intentionally opens `.gitignore` (and similar config files) with
`O_NOFOLLOW` for security reasons. A symlink at `.gitignore` triggers ELOOP
and git emits `warning: unable to access '.gitignore': Too many levels of
symbolic links`, rendering all ignore rules non-functional.

## Verification

- `source set_env.sh` — correct `_GIT_ROOT` and `_FRAMEWORK_DIR` resolved
- SOPS decrypt via `.sops.yaml` symlink — OK
- `git status` — no ELOOP warning, correct typechange entries staged
- All 8 symlink targets readable
