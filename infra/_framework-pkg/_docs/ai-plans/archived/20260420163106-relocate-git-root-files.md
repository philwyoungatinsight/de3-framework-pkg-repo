# Plan: Relocate Git-Root Files to `_framework/_git_root`

## Goal

Move all plain files (not directories) from the git root into
`infra/default-pkg/_framework/_git_root/` and replace each with a relative
symlink so every tool that resolves the git-root path continues to work
unchanged.

## Files to Move

| File | Notes |
|------|-------|
| `CLAUDE.md` | Read by Claude Code; symlink is fine |
| `.gitignore` | Git walks up from any subdir; symlink at root is followed |
| `.gitlab-ci.yml` | GitLab reads from repo root; follows symlinks |
| `Makefile` | `make` follows symlinks |
| `README.md` | Documentation only |
| `root.hcl` | Found by Terragrunt `find_in_parent_folders("root.hcl")` — symlink at root is resolved normally |
| `run` | Main runner; referenced as `./run` from root — symlink is transparent |
| `set_env.sh` | Sourced as `$(git rev-parse --show-toplevel)/set_env.sh`; symlink followed by bash `source` |
| `.sops.yaml` | SOPS config (not secrets); SOPS walks up dirs to find it; symlink at root works |

## Risks / Non-Issues

- **Terragrunt `find_in_parent_folders`**: walks up looking for the filename.
  A symlink at the git root resolves to the actual file — Terragrunt reads the
  real content. No issue.
- **`.sops.yaml` vs secrets file**: `.sops.yaml` is the SOPS *configuration*
  (which age/GPG keys to use). The actual secrets live in
  `_config/secrets.sops.yaml`. The root `.sops.yaml` symlink is found by SOPS
  exactly as before.
- **Git symlink tracking**: git stores symlinks as first-class objects.
  The symlinks will be committed; the real files live in `_git_root/`.
- **Executable bits**: `run` and `set_env.sh` are executable. `mv` preserves
  permissions; the symlinks inherit the target's permissions on Linux.
- **`.gitignore` and `.sops.yaml` (dotfiles)**: standard mv + ln -s; no
  special handling needed.

## Implementation Steps

### Step 1 — Verify `_git_root` directory exists (already does; skip if present)

```bash
mkdir -p infra/default-pkg/_framework/_git_root
```

### Step 2 — Move each file and create a relative symlink

Run from git root. The relative symlink target is
`infra/default-pkg/_framework/_git_root/<file>`.

```bash
GIT_ROOT="$(git rev-parse --show-toplevel)"
DEST="infra/default-pkg/_framework/_git_root"

for f in CLAUDE.md .gitignore .gitlab-ci.yml Makefile README.md root.hcl run set_env.sh .sops.yaml; do
    mv "$GIT_ROOT/$f" "$GIT_ROOT/$DEST/$f"
    ln -s "$DEST/$f" "$GIT_ROOT/$f"
done
```

### Step 3 — Verify symlinks

```bash
ls -la "$GIT_ROOT" | grep -E '^l'
# Each moved file should show -> infra/default-pkg/_framework/_git_root/<name>
```

Verify targets are readable:
```bash
for f in CLAUDE.md .gitignore .gitlab-ci.yml Makefile README.md root.hcl run set_env.sh .sops.yaml; do
    test -e "$GIT_ROOT/$f" && echo "OK: $f" || echo "BROKEN: $f"
done
```

### Step 4 — Smoke-test key tools

```bash
# set_env.sh still sources correctly
source "$GIT_ROOT/set_env.sh" && echo "_GIT_ROOT=$_GIT_ROOT"

# root.hcl still found by a representative unit
cd infra/pwy-home-lab-pkg/_stack/null/pwy-homelab/proxmox/install-proxmox
terragrunt validate 2>&1 | head -5
cd "$GIT_ROOT"

# SOPS config still detected
sops --config "$GIT_ROOT/.sops.yaml" --decrypt infra/default-pkg/_config/secrets.sops.yaml > /dev/null && echo "SOPS OK"
```

### Step 5 — Stage and commit

```bash
git add -A
git status   # should show: deleted files at root + new files in _git_root + new symlinks at root
git commit -m "refactor: relocate git-root files to _framework/_git_root, replace with symlinks"
```

## Open Questions

None — this is a mechanical rename + symlink operation. All referenced tooling
(Terragrunt, bash source, make, git, GitLab CI, SOPS) follows symlinks on
Linux. The `_git_root` destination directory already exists and is empty.
