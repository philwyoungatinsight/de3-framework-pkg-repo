# Plan: pkg-mgr Source vs Local git_ref + Remove local_copy

## Objectives

1. **Source vs local ref**: allow a developer to override `git_ref` per-package in their
   local `framework_package_management.yaml` without touching the committed config.
2. **Remove `local_copy`**: only `linked_copy` remains. Eliminates the shallow-clone path
   and the `_repo_inclusion_method` lookup, and simplifies `_ensure_cloned` significantly.

---

## Background

`git_ref` in `framework_packages.yaml` is the *source* ref — it is committed and shared
across all developers. It declares which branch/tag/SHA the package tracks in the team's
setup.

`framework_package_management.yaml` is per-developer (not committed — lives in `_config/`
but is listed in `.gitignore` or treated as a local machine file). It already holds
`external_package_dir`, which is machine-specific.

A developer working on a feature branch of `maas-pkg` needs `infra/maas-pkg` to point to
their local `feature/my-work` clone, not `main`. Today they would have to edit the committed
config (wrong) or manually fix the symlink (fragile, undone by next `sync`).

---

## Design

### local_git_ref

A new optional `local_overrides:` block in `framework_package_management.yaml`:

```yaml
framework_package_management:
  external_package_dir: 'git/de3-ext-packages'

  local_overrides:
    maas-pkg:
      git_ref: feature/my-work     # overrides git_ref from framework_packages.yaml
    proxmox-pkg:
      git_ref: v2.1.0              # pin to a tag locally
```

When `pkg-mgr sync` processes a package:
- If `local_overrides.<pkg-name>.git_ref` is set → use that value as the effective `git_ref`
- Otherwise → use `git_ref` from `framework_packages.yaml` (unchanged behaviour)

The effective `git_ref` determines both the **clone directory** (`_ext_packages/<slug>/<ref_dir>/`)
and the **git checkout** target. Nothing changes in the clone-path logic — `_ref_to_dir` and
`_clone_dir` already handle this correctly.

No new committed fields. No rename of `git_ref`. The override is purely local.

### Remove local_copy

`local_copy` was the default for repos without `external_package_dir` configured. It:
- Shallow-clones directly into `_ext_packages/<slug>/<ref>/`
- Cannot be pushed from
- Requires no `external_package_dir` config

**Why remove it:**
- Every package we use needs `linked_copy` (we push to de3-runner branches)
- The shallow-clone path adds significant code complexity for no real benefit
- `local_copy` ↔ `linked_copy` migration code can be deleted entirely
- `external_package_dir` is already configured on all developer machines

**What changes:**
- `_ensure_cloned` loses the `local_copy` branch entirely — only linked_copy logic remains
- `_repo_inclusion_method` helper is deleted — no longer needed
- `inclusion_method:` key on package entries still parses (ignored gracefully) to avoid
  breaking any existing YAML, but has no effect
- `default_inclusion_method:` in management YAML is ignored (always linked_copy)
- `external_package_dir` is now **required**; `_ensure_cloned` errors immediately if unset

---

## Files to Modify

| File | Changes |
|------|---------|
| `infra/default-pkg/_framework/_pkg-mgr/run` | Core changes (sections below) |
| `infra/default-pkg/_config/framework_package_management.yaml` | Add `local_overrides:` example |
| `infra/default-pkg/_framework/_pkg-mgr/README.md` | Document local_git_ref, remove local_copy section |

---

## Implementation Strategy

### Step 1 — `_read_local_git_ref` helper

```bash
_read_local_git_ref() {
  local pkg_name="$1"
  python3 -c "
import yaml, pathlib
cfg = pathlib.Path('$PKG_MGMT_CFG')
if not cfg.exists(): print(''); exit(0)
d = yaml.safe_load(cfg.read_text()) or {}
overrides = d.get('framework_package_management', {}).get('local_overrides', {})
print(overrides.get('$pkg_name', {}).get('git_ref', '') or '')
" 2>/dev/null || echo ""
}
```

### Step 2 — `_cmd_sync`: apply local override before `_ensure_cloned`

In the `while read` loop, after reading `git_ref` from the Python output:

```bash
local_ref=$(_read_local_git_ref "$pkg_name")
effective_ref="${local_ref:-$git_ref}"
```

Pass `effective_ref` to `_ensure_cloned` and `_create_symlink` instead of `git_ref`.

The `active_pairs` Python block (for orphan cleanup) must also resolve local overrides so
it doesn't prune the locally-overridden clone:

```python
overrides = d.get('framework_package_management', {}).get('local_overrides', {})
# for each pkg, use local_overrides.<pkg>.git_ref if present
```

### Step 3 — Remove `local_copy` from `_ensure_cloned`

Delete:
- The `_repo_inclusion_method` helper function entirely
- The `local_copy` code path in `_ensure_cloned` (the `else` branch after the
  `linked_copy` block, plus both migration blocks)
- The call to `_repo_inclusion_method` at the top of `_ensure_cloned`

What remains in `_ensure_cloned` is only the `linked_copy` block (renamed to just the
function body — no `if [[ "$method" == "linked_copy" ]]` wrapper needed).

Add an early error if `external_package_dir` is unset:

```bash
_ensure_cloned() {
  local slug="$1" url="$2" git_ref="${3:-}"
  local ref_dir; ref_dir=$(_ref_to_dir "$git_ref")

  local ext_base
  ext_base=$(_external_package_dir)
  if [[ -z "$ext_base" ]]; then
    echo "ERROR: external_package_dir is not set in framework_package_management.yaml" >&2
    exit 1
  fi

  local ext_clone="$ext_base/$slug/$ref_dir"
  local dest="$EXT_PACKAGES_DIR/$slug/$ref_dir"
  ...
}
```

The function body then only contains the linked_copy logic (clone, fetch/checkout, symlink).

### Step 4 — `_cmd_status` Python: resolve local overrides for packages table

When building package rows, apply the local override before computing the effective ref and
clone path. Pass `PKG_MGMT_CFG` (already passed as `sys.argv[3]`) to read `local_overrides`.

```python
pm_data   = yaml.safe_load(mgmt_path.read_text()) or {} if mgmt_path.exists() else {}
overrides = pm_data.get('framework_package_management', {}).get('local_overrides', {})

# in the per-package loop:
source_ref   = p.get('git_ref', '')
override_ref = overrides.get(name, {}).get('git_ref', '')
eff_ref      = override_ref or source_ref
ref_dir      = ref_to_dir(eff_ref)
ref          = get_active_ref(ext_dir / repo / ref_dir)
```

Also show `(local)` annotation on the ref label if an override is active, so the user can
see at a glance which packages are on a non-canonical ref.

### Step 5 — `framework_package_management.yaml` example

Add a commented `local_overrides:` block to document the feature:

```yaml
  # Per-developer git_ref overrides. Not committed — edit freely.
  # Overrides git_ref from framework_packages.yaml for sync and symlink resolution.
  # local_overrides:
  #   maas-pkg:
  #     git_ref: feature/my-work
  #   proxmox-pkg:
  #     git_ref: v2.1.0
```

---

## Behaviour Summary

| Scenario | Clone path | Symlink target | Behaviour |
|----------|-----------|----------------|-----------|
| `git_ref: main`, no local override | `<ext>/<slug>/main/` | `…/main/infra/<pkg>/` | unchanged |
| `git_ref: main`, `local_overrides.pkg.git_ref: feature/foo` | `<ext>/<slug>/feature__foo/` | `…/feature__foo/infra/<pkg>/` | developer's branch |
| No `git_ref`, no override | `<ext>/<slug>/HEAD/` | `…/HEAD/infra/<pkg>/` | unchanged |

The `main/` clone for the overridden package still exists if other packages also need it.

---

## Removed Code

- `_repo_inclusion_method` helper (~20 lines)
- `local_copy` clone path in `_ensure_cloned` (~30 lines)
- `linked_copy ↔ local_copy` migration blocks (~30 lines)
- `default_inclusion_method` handling in `_cmd_status` (kept as display-only, no logic)

Net: ~80 lines removed, ~40 lines added.

---

## Open Questions

None — all decisions settled.

---

## Commit Strategy

Single commit:
1. `run` changes (Steps 1–4)
2. `framework_package_management.yaml` update (Step 5)
3. README update
4. ai-log entry
5. Version bump in `default-pkg.yaml` (1.1.1 — feature addition + simplification)
