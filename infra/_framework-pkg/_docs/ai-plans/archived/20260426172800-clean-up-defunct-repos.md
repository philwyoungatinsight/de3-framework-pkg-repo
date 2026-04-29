# Plan: Clean Up Defunct Repos in fw-repos Visualizer

## Objective

Remove stale/defunct repo entries (`de3-aws-pkg`, `de3-proxmox-pkg`, `proxmox-pkg-repo`,
`de3-demo-buckets-example-pkg`, etc.) from the fw-repos visualizer. Fix the two root causes:
(a) de3-runner's template config triggers a clone of the stale GitHub copy of `pwy-home-lab-pkg`,
which injects old names; (b) the scanner reads `upstream_url`, a legacy field no longer used,
creating two conflicting ways to declare a repo's remote URL.

The fix unifies URL declaration to `new_repo_config.git-remotes` exclusively, removes the
deployment-specific entry from de3-runner's template, and purges the stale cache.

`pwy-home-pkg` (the local repo) is **intentionally left as-is** — `de3-pwy-home-lab-pkg-repo`
will be built by `fw-repo-mgr` from the existing `pwy-home-lab-pkg`, and once that is built
and tested the old repo will be retired.

---

## Why the Current Local Config Alone Doesn't Fix the Diagram

**1. The path `infra/_framework-pkg/_config/_framework_settings/framework_repo_manager.yaml`
in pwy-home-lab-pkg is a symlink into de3-runner**, not the deployment config. The 3-tier
lookup winner is Tier 2: `infra/pwy-home-lab-pkg/_config/_framework_settings/framework_repo_manager.yaml`.

**2. The visualizer BFS-scans cloned remote repos, not just the local config.** Data flow:

```
1. Seed queue from framework_package_repositories.yaml → de3-runner URL
2. Clone de3-runner → read de3-runner's framework_repo_manager.yaml
3. de3-runner declares pwy-home-lab-pkg with upstream_url (GitHub) → enqueue it
4. Clone pwy-home-lab-pkg from GitHub → reads STALE config → old names injected
5. All stale names land in known-fw-repos.yaml → appear in diagram
```

Even a perfect local config can't override what the scanner reads from GitHub clones.

---

## Root Causes

| # | Root cause | Effect |
|---|-----------|--------|
| 1 | de3-runner's `framework_repo_manager.yaml` has an active `pwy-home-lab-pkg` entry with `upstream_url` | Scanner clones stale GitHub copy; old `de3-*-pkg` and `proxmox-pkg-repo` names injected |
| 2 | Scanner reads `upstream_url` field only; new schema uses `new_repo_config.git-remotes` | Two conflicting ways to declare URLs; new `de3-*-repo` stubs have no URL in diagram |
| 3 | Scanner has no awareness of `local_only: true`; tries to clone non-existent repos | Future repos marked `accessible: false` before they're created |
| 4 | `known-fw-repos.yaml` cache is stale | Old data persists until cache is cleared |

---

## Decisions (from user Q&A)

- **Q1 (origin remote / `pwy-home-pkg` name)**: Do not change. `pwy-home-lab-pkg` will become
  `de3-pwy-home-lab-pkg-repo` via `fw-repo-mgr`; the old repo retires afterwards.
- **Q2 (GitHub push)**: Not needed. Same reasoning.
- **Q3 (URL field)**: Fix the scanner to read `new_repo_config.git-remotes[0].git-source`
  as the canonical source. Remove `upstream_url` from all config — one way only.

---

## Files to Modify

### 1. `infra/_framework-pkg/_config/_framework_settings/framework_repo_manager.yaml` (de3-runner) — modify

Comment out the active `pwy-home-lab-pkg` entry. This is root cause 1 — it triggers the
stale GitHub clone. Replace with a generic commented example that uses the new schema.

**Remove** (comment out):
```yaml
  # App-repo: pwy-home-lab-pkg (the user's actual home lab repo)
  - name: pwy-home-lab-pkg
    source_repo:
      name: de3-runner
    upstream_url: https://github.com/philwyoungatinsight/pwy-home-lab-pkg.git
    upstream_branch: main
    framework_packages:
      - name: pwy-home-lab-pkg
        package_type: embedded
        exportable: false
        is_config_package: true
```

**Replace with**:
```yaml
  # Deployment repos belong in the deployment repo's own framework_repo_manager.yaml
  # (Tier 2), not here. Declaring a deployment repo in this template causes every
  # fw-repos scan to clone that repo's remote and read its config, which may be stale.
  #
  # Example — declare your deployment repo in your deployment repo's config:
  #- name: de3-my-deployment-repo
  #  local_only: true          # remove once validated and repos are created
  #  source_repo:
  #    name: de3-runner
  #  new_repo_config:
  #    git-remotes:
  #      - name: origin
  #        git-source: https://github.com/you/de3-my-deployment-repo.git
  #        git-ref: main
  #  framework_packages:
  #    - name: my-deployment-pkg
  #      package_type: embedded
  #      exportable: false
  #      is_config_package: true
```

### 2. `infra/_framework-pkg/_framework/_fw-repos-visualizer/fw_repos_visualizer/scanner.py` — modify

Three changes to `_load_repo_manager()`:

**A. Read URL from `new_repo_config.git-remotes[0].git-source`; drop `upstream_url`.**

```python
# BEFORE (two places — url extraction and declared_repos["url"]):
upstream = fr.get("upstream_url")
...
"url": fr.get("upstream_url") or None,

# AFTER — canonical source only; upstream_url removed:
remotes = (fr.get("new_repo_config") or {}).get("git-remotes", [])
upstream = remotes[0].get("git-source", "") if remotes else ""
...
"url": upstream or None,
```

**B. Skip enqueuing repos with `local_only: true`.**

Repos marked `local_only` don't exist on remote yet. Enqueueing them causes the scanner
to attempt a clone, fail, and mark them `accessible: false`. Instead, only add them as
declared stubs (they already appear in the diagram from `declared_repos`).

```python
# BEFORE:
upstream = fr.get("upstream_url")
if upstream:
    enqueue_fn([{"name": rname, "url": upstream}])

# AFTER:
if upstream and not fr.get("local_only"):
    enqueue_fn([{"name": rname, "url": upstream}])
```

**C. Propagate `local_only` into the declared stub** so the visualizer can render it
distinctively (e.g. dashed border, tooltip explaining it's not yet created):

```python
declared_repos[rname] = {
    "url": upstream or None,
    "created_by": creator,
    "source": "declared",
    "local_only": bool(fr.get("local_only", False)),   # ← add this line
    "settings_dirs": [...],
    ...
}
```

### 3. Delete stale cache files — one-time shell commands

```bash
rm /home/pyoung/git/pwy-home-lab-pkg/config/tmp/fw-repos-visualizer/known-fw-repos.yaml
rm /home/pyoung/git/de3-ext-packages/de3-runner/main/config/tmp/fw-repos-visualizer/known-fw-repos.yaml
```

Both are generated/gitignored; the scanner regenerates them on the next run.

---

## Execution Order

1. **Edit de3-runner's `framework_repo_manager.yaml`** — comment out the active
   `pwy-home-lab-pkg` entry; replace with the generic commented example.

2. **Edit `scanner.py`** — apply changes A, B, C described above.

3. **Verify no other `upstream_url` occurrences remain** in any `framework_repo_manager.yaml`:
   ```bash
   grep -r "upstream_url\|upstream_branch" \
     /home/pyoung/git/pwy-home-lab-pkg/infra/pwy-home-lab-pkg/_config/_framework_settings/ \
     /home/pyoung/git/de3-ext-packages/de3-runner/main/infra/_framework-pkg/_config/_framework_settings/
   ```
   If any appear, remove them (they are now dead config).

4. **Commit de3-runner changes**:
   ```bash
   git -C /home/pyoung/git/de3-ext-packages/de3-runner/main add \
     infra/_framework-pkg/_config/_framework_settings/framework_repo_manager.yaml \
     infra/_framework-pkg/_framework/_fw-repos-visualizer/fw_repos_visualizer/scanner.py
   git -C /home/pyoung/git/de3-ext-packages/de3-runner/main commit -m \
     "fix(fw-repos): remove stale deployment entry; scanner reads git-remotes, respects local_only"
   ```

5. **Delete both `known-fw-repos.yaml` cache files.**

6. **Trigger a rescan** — open the GUI and use the refresh button, or:
   ```bash
   source set_env.sh
   infra/_framework-pkg/_framework/_fw-repos-visualizer/fw-repos-visualizer --refresh --list
   ```

---

## Verification

After rescan, `known-fw-repos.yaml` should contain exactly:

| Repo | source | local_only |
|------|--------|-----------|
| `pwy-home-pkg` | local | — |
| `de3-runner` | cloned | — |
| `de3-_framework-pkg-repo` | declared | true |
| `de3-aws-pkg-repo` | declared | true |
| `de3-azure-pkg-repo` | declared | true |
| `de3-gui-pkg-repo` | declared | true |
| `de3-gcp-pkg-repo` | declared | true |
| `de3-image-maker-pkg-repo` | declared | true |
| `de3-maas-pkg-repo` | declared | true |
| `de3-mesh-central-pkg-repo` | declared | true |
| `de3-mikrotik-pkg-repo` | declared | true |
| `de3-proxmox-pkg-repo` | declared | true |
| `de3-unifi-pkg-repo` | declared | true |
| `de3-pwy-home-lab-pkg-repo` | declared | true |
| `de3-central-index-repo` | declared | true |

**Must NOT appear**: `proxmox-pkg-repo`, `pwy-home-lab-pkg` (cloned node),
any `de3-*-pkg` name (missing `-repo` suffix), `de3-demo-buckets-example-pkg`.

## Open Questions

None — ready to proceed.
