# Plan: Support Explicit package_type + Rename public → exportable

## Objective

Add an explicit `package_type: embedded | external` field to all entries in
`framework_packages.yaml` so that the embedded/imported distinction is stated in config
rather than inferred from the presence of a `repo:` field. Simultaneously rename the
existing `public` field to `exportable` throughout — a clearer name for what the field
actually controls (whether other repos can import this package via `pkg-mgr list-remote`
/ `pkg-mgr import`).

---

## Context

### Two separate concepts that are currently conflated or implicit

**`package_type`** (new, explicit):
- `embedded` — the package is a real directory under `infra/<pkg>/` in this repo. No
  `repo:` or `source:` field. pkg-mgr does not clone or symlink it. Previously called
  "built-in" in the README.
- `external` — the package is a symlink from an external git repo. Has `repo:` (and
  usually `source:`, `git_ref:`, `import_path:`). Previously called "imported".
- Currently *implied* by presence/absence of `repo:`: no real validation exists.

**`exportable`** (rename of `public`):
- Controls whether `pkg-mgr --list-remote` and `pkg-mgr --import` from *another* repo
  can see and import this package.
- Has nothing to do with embedded vs external.
- `public: true/false` is confusing because "public" sounds like code visibility rather
  than "can a downstream repo import me?"

### Where `public` is currently read/written

| Location | Line(s) | What it does |
|---|---|---|
| `_pkg-mgr/run` `_cmd_list_remote` | 629 | `if not p.get("public", False): continue` — skip non-public |
| `_pkg-mgr/run` `_cmd_import` | 555 | `entry = {"name": ..., "public": False, ...}` — new entry |
| `_pkg-mgr/run` `_cmd_copy` | 1275 | `{"name": src_n, "public": False}` — fallback entry |
| `_pkg-mgr/README.md` | 71, 77 | Schema examples |
| `framework_packages.yaml` | all entries | Data |
| `framework_manager.yaml` | all framework_packages entries | Data |

### Where the embedded/external distinction is inferred (not validated)

| Location | How |
|---|---|
| `_cmd_sync` | `p.get("repo")` — truthy = external |
| `_cmd_status` | `[p for p in pkgs if p.get('repo')]` = imported |
| `_cmd_clean` | `p.get("repo")` — truthy = external |
| `_fw-repo-mgr/run` `_prune_infra` | `entry.is_symlink()` — skip symlinks |

### Current data (all 13 entries)

| Package | embedded/external | public |
|---|---|---|
| `_framework-pkg` | embedded | true |
| `pwy-home-lab-pkg` | embedded | false |
| `aws-pkg`, `azure-pkg`, `de3-gui-pkg`, `demo-buckets-example-pkg`, `gcp-pkg`, `image-maker-pkg`, `maas-pkg`, `mesh-central-pkg`, `mikrotik-pkg`, `proxmox-pkg`, `unifi-pkg` | external | true |

---

## Open Questions

None — ready to proceed.

---

## Files to Create / Modify

### `infra/_framework-pkg/_config/framework_packages.yaml` — modify

Add `package_type` to every entry. Rename `public` → `exportable`. Embedded entries
get no `repo:` fields (unchanged). External entries keep all existing fields.

Update the comment header to document the two new fields:

```yaml
# Parameters for framework packages
#
# package_type (required):
#   embedded  — real directory in this repo; pkg-mgr does not clone or link it
#   external  — symlink from external repo; pkg-mgr clones and links it
#
# exportable (required):
#   true   — pkg-mgr list-remote shows this package; other repos may import it
#   false  — private; not advertised for import
#
# EXAMPLE - Embedded package (lives in this repo as infra/<name>/)
#   - name: my-pkg
#     package_type: embedded
#     exportable: true
#
# EXAMPLE - External package (imported via symlink from another repo)
#   - name: foo-pkg
#     package_type: external
#     exportable: true
#     source: https://github.com/foo/foo-pkg.git
#     repo: foo-pkg
#     import_path: foo-pkg
#     git_ref: main
#
# git_ref (required for all external packages) — which commit to check out after cloning:
#   git_ref: main          # branch name: re-sync pulls latest from that branch
#   git_ref: v1.2.3        # tag: pinned to that tag
#   git_ref: abc1234       # commit SHA (7–40 hex chars): checkout; re-sync stays on that SHA

framework_packages:
  - name: aws-pkg
    package_type: external
    exportable: true
    repo: de3-runner
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: aws-pkg
    config_source: pwy-home-lab-pkg
  - name: azure-pkg
    package_type: external
    exportable: true
    repo: de3-runner
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: azure-pkg
    config_source: pwy-home-lab-pkg
  - name: de3-gui-pkg
    package_type: external
    exportable: true
    repo: de3-runner
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: de3-gui-pkg
    config_source: pwy-home-lab-pkg
  - name: _framework-pkg
    package_type: embedded
    exportable: true
  - name: demo-buckets-example-pkg
    package_type: external
    exportable: true
    repo: de3-runner
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: demo-buckets-example-pkg
    config_source: pwy-home-lab-pkg
  - name: gcp-pkg
    package_type: external
    exportable: true
    repo: de3-runner
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: gcp-pkg
    config_source: pwy-home-lab-pkg
  - name: image-maker-pkg
    package_type: external
    exportable: true
    repo: de3-runner
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: image-maker-pkg
    config_source: pwy-home-lab-pkg
  - name: maas-pkg
    package_type: external
    exportable: true
    repo: de3-runner
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: maas-pkg
    config_source: pwy-home-lab-pkg
  - name: mesh-central-pkg
    package_type: external
    exportable: true
    repo: de3-runner
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: mesh-central-pkg
    config_source: pwy-home-lab-pkg
  - name: mikrotik-pkg
    package_type: external
    exportable: true
    repo: de3-runner
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: mikrotik-pkg
    config_source: pwy-home-lab-pkg
  - name: proxmox-pkg
    package_type: external
    exportable: true
    repo: de3-runner
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: proxmox-pkg
    config_source: pwy-home-lab-pkg
  - name: unifi-pkg
    package_type: external
    exportable: true
    repo: de3-runner
    source: https://github.com/philwyoungatinsight/de3-runner.git
    git_ref: main
    import_path: unifi-pkg
    config_source: pwy-home-lab-pkg
  - name: pwy-home-lab-pkg
    package_type: embedded
    exportable: false
```

### `infra/_framework-pkg/_framework/_pkg-mgr/run` — modify

**1. `_cmd_sync` — add validation block, replace `p.get("repo")` with `package_type` check**

After the `pkgs = yaml.safe_load(...)` line and the existing `missing` check, add a
`package_type` validation block:

```python
# Validate package_type consistency
invalid = []
for p in pkgs:
    pt = p.get("package_type", "")
    if pt not in ("embedded", "external"):
        invalid.append(f"  '{p['name']}': package_type must be 'embedded' or 'external', got '{pt}'")
    elif pt == "external" and not p.get("repo"):
        invalid.append(f"  '{p['name']}': package_type: external requires a repo: field")
    elif pt == "embedded" and p.get("repo"):
        invalid.append(f"  '{p['name']}': package_type: embedded must not have a repo: field")
if invalid:
    for msg in invalid:
        print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)
```

Change the filter for which packages to process in the main loop:

```python
# OLD:
for p in pkgs:
    repo = p.get("repo", "")
    if not repo:
        continue

# NEW:
for p in pkgs:
    if p.get("package_type") != "external":
        continue
    repo = p.get("repo", "")
```

Change the `active_names` block (line ~383):

```python
# OLD:
print(" ".join(p["name"] for p in pkgs if p.get("repo")))

# NEW:
print(" ".join(p["name"] for p in pkgs if p.get("package_type") == "external"))
```

**2. `_cmd_list_remote` — rename `public` → `exportable`**

```python
# OLD (line ~629):
if not p.get("public", False):
    continue

# NEW:
if not p.get("exportable", False):
    continue
```

**3. `_cmd_import` — rename `public` → `exportable`, add `package_type`**

```python
# OLD (line ~555):
entry = {"name": name, "public": False, "repo": repo, "import_path": import_path}

# NEW:
entry = {"name": name, "package_type": "external", "exportable": False, "repo": repo, "import_path": import_path}
```

**4. `_cmd_copy` — rename fallback `public` → `exportable`, add `package_type`**

```python
# OLD (line ~1275):
{"name": src_n, "public": False}

# NEW:
{"name": src_n, "package_type": "embedded", "exportable": False}
```

Note: `_cmd_copy` is only called for local (embedded) packages at this fallback path, so
`package_type: embedded` is correct.

**5. `_cmd_status` — use `package_type` instead of `repo:` inference**

```python
# OLD (line ~779):
imported = [p for p in pkgs if p.get('repo')]
builtin  = [p for p in pkgs if not p.get('repo')]

# NEW:
external = [p for p in pkgs if p.get('package_type') == 'external']
embedded = [p for p in pkgs if p.get('package_type') == 'embedded']
```

Update references throughout `_cmd_status` from `imported`/`builtin` → `external`/`embedded`.

In the packages table Method column:
```python
# OLD:
method  = 'linked_copy' if repo != '—' else 'built-in'

# NEW:
method  = p.get('package_type', 'unknown')
```

**6. `_cmd_clean` — use `package_type` for active_pairs filter**

```python
# OLD (line ~700):
for p in pkgs:
    if not p.get("repo"):
        continue

# NEW:
for p in pkgs:
    if p.get("package_type") != "external":
        continue
```

### `infra/_framework-pkg/_framework/_pkg-mgr/README.md` — modify

Update the Package schema section to show the new fields:

- Replace `public: false` with `package_type: embedded|external` and `exportable: false`
- Update the Nomenclature section to mention `package_type`

Specific changes:

```markdown
## Package schema

`config/framework_packages.yaml` entries use two required fields on every entry:

- **`package_type`**: `embedded` (real directory in this repo) or `external` (symlink from external repo)
- **`exportable`**: `true` if other repos may import this via `pkg-mgr list-remote`; `false` to keep private

```yaml
framework_packages:

  # Embedded — real directory in this repo (no repo: or source:)
  - name: my-pkg
    package_type: embedded
    exportable: true

  # External, Case A — package from a registered parent repo (no own git URL)
  - name: some-pkg
    package_type: external
    exportable: false
    repo: community-infra-pkgs   # clone slug under _ext_packages/
    import_path: some-pkg        # subdir inside <repo>/infra/ (defaults to name)

  # External, Case B — package has its own git repo (source URL present)
  - name: external-foo-pkg
    package_type: external
    exportable: false
    source: https://github.com/foo/bar.git
    repo: bar                    # slug derived from source URL
    import_path: external-foo-pkg
    git_ref: main                # required for all external packages
```
```

### `infra/_framework-pkg/_config/framework_manager.yaml` — modify

Update all `framework_packages` entries to use `package_type` and `exportable` instead of `public`:

```yaml
      framework_packages:
        - name: _framework-pkg
          package_type: embedded
          exportable: true
        - name: proxmox-pkg
          package_type: embedded
          exportable: true
        - name: proxmox-pkg-repo
          package_type: embedded
          exportable: false
```

And the combining example:

```yaml
      framework_packages:
        - name: _framework-pkg
          package_type: embedded
          exportable: true
        - name: proxmox-pkg
          package_type: external
          exportable: true
          repo: proxmox-pkg-repo
          source: https://github.com/philwyoungatinsight/proxmox-pkg-repo.git
          git_ref: main
          import_path: proxmox-pkg
          config_source: my-homelab
        - name: my-homelab
          package_type: embedded
          exportable: false
```

Note: in the `proxmox-pkg-repo` example, all three packages are `embedded` because from the
perspective of the target repo they are all real directories (the source template has them as
real dirs, and fw-repo-mgr prunes/keeps them as real dirs). The `my-homelab` example shows
`proxmox-pkg` as `external` because it is imported via symlink by pkg-mgr sync.

### `infra/_framework-pkg/_framework/_fw-repo-mgr/run` — modify

**`_prune_infra`**: update the comment to reference `package_type: embedded`:

```python
# Prune embedded packages from infra/ that are NOT in the target keep list.
# external packages (symlinks) are left for pkg-mgr sync to handle.
if entry.is_symlink():
    continue          # external packages — pkg-mgr manages these
```

No logic change needed — the `is_symlink()` check already correctly skips external packages.
The change is documentation/comment clarity only.

### `infra/_framework-pkg/_config/_framework-pkg.yaml` — modify

Bump `_provides_capability` from `1.4.1` → `1.4.2`. Append version history entry:

```yaml
# _framework-pkg: 1.4.2  (2026-04-21, git: TBD)
# - framework_packages.yaml: add package_type (embedded|external) field; rename public → exportable
# - pkg-mgr: validate package_type consistency; use package_type in sync/clean/status
# - fw-repo-mgr: comment update only (prune logic unchanged)
```

---

## Execution Order

1. Modify `framework_packages.yaml` — adds `package_type` + renames `public` → `exportable` on all data entries
2. Modify `framework_manager.yaml` — same field updates on example entries
3. Modify `_pkg-mgr/run` — all six code changes (sync validation, sync filter, list-remote, import, copy, status, clean)
4. Modify `_pkg-mgr/README.md` — schema docs update
5. Modify `_fw-repo-mgr/run` — comment-only clarification in `_prune_infra`
6. Modify `_framework-pkg.yaml` — version bump to 1.4.2

---

## Verification

```bash
source set_env.sh

# Status should show 'embedded' and 'external' in Method column
infra/_framework-pkg/_framework/_pkg-mgr/run --status

# Sync should complete without validation errors
infra/_framework-pkg/_framework/_pkg-mgr/run --sync

# fw-repo-mgr status should still work
infra/_framework-pkg/_framework/_fw-repo-mgr/run status

# Manually verify: add a package entry with invalid package_type and confirm error
# python3 -c "
# import yaml, pathlib
# p = pathlib.Path('infra/_framework-pkg/_config/framework_packages.yaml')
# d = yaml.safe_load(p.read_text())
# d['framework_packages'].append({'name': 'test-bad', 'package_type': 'bad', 'exportable': False})
# p.write_text(yaml.dump(d))
# "
# infra/_framework-pkg/_framework/_pkg-mgr/run --sync
# → ERROR: 'test-bad': package_type must be 'embedded' or 'external'
# (then restore the file)
```
