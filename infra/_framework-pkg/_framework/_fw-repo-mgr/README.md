# fw-repo-mgr — Framework Repository Manager

Creates and maintains de3 framework ecosystem repos from a template source repo.
Reads configuration from `framework_repo_manager.yaml` (3-tier lookup: ad-hoc override
→ main package → framework defaults) and applies it to a set of target repos.

## Usage

```bash
# From this directory:
make build      # build/sync all configured repos
make validate   # validate naming rules for all repos
make status     # show local/remote state of all configured repos

# Or directly (GNU-style flags):
./fw-repo-mgr --build [<name>] [-F|--force-push]      # build all, or one named repo
./fw-repo-mgr --validate [<name>]                     # validate naming rules
./fw-repo-mgr --status [-f|--format json|yaml]        # show status table (or JSON/YAML)
./fw-repo-mgr --help                                  # show usage

# Via env var from anywhere in the repo (after source set_env.sh):
$_FW_REPO_MGR --status
```

## What It Does

For each target repo in `framework_repos`:

1. **Clone or update** from the configured `source_repo` (rsync for new repos, fetch/pull for existing)
2. **Prune** `infra/` — removes real dirs not in the embedded package list; removes `.gitlab-ci.yml` if it is now a dangling symlink (default-pkg is always pruned)
3. **Write scaffolding** — `config/_framework.yaml`, `framework_packages.yaml`, `_framework_settings/` files
4. **Re-encrypt** any `*.sops.yaml` files using the new `.sops.yaml` keys (via `sops-mgr`)
5. **Sync packages** — runs `pkg-mgr --sync` inside the target repo to create external package symlinks
6. **Commit** changes in the target repo
7. **Create remote repos** — for each git remote, creates the repo on GitHub (via `gh`) or GitLab (via `glab api`) if it does not already exist; skipped when `local_only: true`
8. **Push** to all configured git remotes; skipped when `local_only: true`

## Config Lookup (3-tier)

| Tier | Path | Purpose |
|------|------|---------|
| 1 | `$GIT_ROOT/config/framework_repo_manager.yaml` | Ad-hoc developer override |
| 2 | `$_FRAMEWORK_MAIN_PACKAGE_DIR/_config/_framework_settings/framework_repo_manager.yaml` | Deployment-specific config (e.g. `pwy-home-lab-pkg`) |
| 3 | `$_FRAMEWORK_PKG_DIR/_config/_framework_settings/framework_repo_manager.yaml` | Framework defaults (empty `framework_repos: []`) |

## local_only Mode

`local_only: true` is **optional**. Omit it to build and publish in a single pass.

**Single-pass** (no flag — the default for repos you're confident about):
```bash
$_FW_REPO_MGR --build <name>   # builds locally, creates GitHub/GitLab repos, pushes
```

**Two-pass** (set `local_only: true` to inspect the local result before touching any remote):
```bash
# Phase 1 — local build:
$_FW_REPO_MGR --build <name>   # builds and commits locally; no remote touched
$_FW_REPO_MGR --status         # confirms (local-only) flag in STATUS column

# Phase 2 — publish (remove local_only: true from YAML, then):
$_FW_REPO_MGR --build <name>   # creates GitHub/GitLab repos, then pushes
```
