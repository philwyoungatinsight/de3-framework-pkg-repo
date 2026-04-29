# Plan: pkg-mgr Multi-Ref Clone Support

## Objective

Allow two packages from the same source repo to be pinned to different `git_ref` values.
Each (slug, ref) combination gets its own clone directory under `_ext_packages/`.

---

## Problem

Currently `_ext_packages/<slug>/` holds exactly one clone per repo. All packages from the
same repo share it, so all must use the same checked-out ref. This makes it impossible to
have e.g. `maas-pkg` on `main` and `maas-pkg-staging` on a feature branch.

---

## Proposed Layout

```
_ext_packages/
  de3-runner/
    main/           ← clone at git_ref: main
      infra/
        maas-pkg/
        proxmox-pkg/
    feature_foo/    ← clone at git_ref: feature/foo  (/ → _ in dir name)
      infra/
        maas-pkg/
    HEAD/           ← clone with no git_ref (remote default branch)
      infra/
        ...

infra/maas-pkg  →  ../_ext_packages/de3-runner/main/infra/maas-pkg
```

Packages sharing the same (slug, ref) continue to share one clone — only the ref dimension
is split.

---

## Design Decisions

### 1 — `HEAD` as the sentinel for "no git_ref"

When `git_ref` is unset the clone goes to `_ext_packages/<slug>/HEAD/`. This is the git
term for the default checkout and is unambiguous.

### 2 — Sanitise `/` in branch names

Branch names like `feature/foo` cannot be used as directory components. Replace `/` with
`__` (double underscore) for the directory name only; the actual value passed to
`git checkout` is unchanged.

```bash
_ref_to_dir() { echo "${1:-HEAD}" | tr '/' '_' | sed 's|/|__|g'; }
```

Actually simpler with sed or parameter substitution:

```bash
_ref_to_dir() { local r="${1:-HEAD}"; echo "${r//\//__}"; }
```

`feature/foo` → directory `feature__foo`, checkout arg `feature/foo`.

### 3 — Inclusion method stays per-slug

All ref-clones of the same repo share the same `inclusion_method` (local_copy /
linked_copy). No need to key on (slug, ref).

### 4 — Migration: one-time `clean --all && sync`

Old flat clones at `_ext_packages/<slug>/` (no `<ref>` subdirectory) become orphaned under
the new layout. Auto-migration adds complexity for little gain — this is a developer tool
with known users. Document the one-time migration step instead.

### 5 — `add-repo` stays single-ref

Parent repos registered via `add-repo` are browsed for packages; individual packages carry
`git_ref`. Adding per-repo ref to `add-repo` is out of scope.

### 6 — linked_copy: one external clone per (slug, ref)

Each ref gets its own full clone at `<ext_base>/<slug>/<ref_dir>/`. Disk cost is accepted
as a trade-off for correctness.

---

## Files to Modify

| File | Changes |
|------|---------|
| `infra/default-pkg/_framework/_pkg-mgr/run` | All sections below |
| `infra/default-pkg/_framework/_pkg-mgr/README.md` | Update path diagrams + file layout section |

---

## Implementation Strategy

### Step 1 — `_ref_to_dir` helper (new, before `_ensure_cloned`)

```bash
# Converts a git ref to a safe directory name: replaces / with _; defaults to HEAD.
_ref_to_dir() { echo "${1:-HEAD}" | tr '/' '_'; }
```

### Step 2 — `_ensure_cloned`: use two-level path

Replace:
```bash
local dest="$EXT_PACKAGES_DIR/$slug"
```
With:
```bash
local ref_dir; ref_dir=$(_ref_to_dir "$git_ref")
local dest="$EXT_PACKAGES_DIR/$slug/$ref_dir"
```

All subsequent `mkdir -p` calls already cover the parent since `mkdir -p` creates
intermediate directories. No other logic in `_ensure_cloned` changes — it still clones
to `$dest`, which is now the two-level path.

For `linked_copy`, the external clone path becomes `<ext_base>/<slug>/<ref_dir>/`.

### Step 3 — `_create_symlink`: accept and use `git_ref`

```bash
_create_symlink() {
  local pkg_name="$1" repo="$2" import_path="$3" git_ref="${4:-}"
  local ref_dir; ref_dir=$(_ref_to_dir "$git_ref")
  local link="$INFRA_DIR/$pkg_name"
  local target="../_ext_packages/$repo/$ref_dir/infra/$import_path"
  ...
}
```

### Step 4 — `_cmd_sync`: pass `git_ref` to `_create_symlink`

```bash
_create_symlink "$pkg_name" "$repo" "$import_path" "$git_ref"
```

Orphaned-symlink cleanup is unchanged (operates on `infra/<pkg>` symlinks, not clone dirs).

Orphaned-clone cleanup must now walk two levels:

```bash
for clone_dir in "$EXT_PACKAGES_DIR"/*/*/; do   # <slug>/<ref_dir>/
  slug="${...}"   # second-to-last component
  ref_dir="${...}" # last component
  if ! <active (slug,ref_dir) set contains (slug,ref_dir)>; then
    rm -rf "$clone_dir"
  fi
done
```

Active set is built from the Python block by emitting `(slug, ref_dir)` pairs.

### Step 5 — `_cmd_clean` orphan removal

Update the orphan walk to the two-level structure (same pattern as Step 4 sync cleanup).
`clean --all` deletes `_ext_packages/` entirely — unchanged.

### Step 6 — `_cmd_status` repos table

Currently groups by slug. Now group by `(slug, ref_dir)` to show each clone separately.
Add `Ref` column to the repos table (it currently only appears in the packages table).

The packages table `get_active_ref()` call should use the two-level path:
`ext_dir / repo / _ref_to_dir(git_ref_for_pkg)` — but `get_active_ref` is called from
Python where `_ref_to_dir` logic must be replicated:
```python
ref_dir = (git_ref or "HEAD").replace("/", "_")
get_active_ref(ext_dir / repo / ref_dir)
```

### Step 7 — `_resolve_pkg_repo` internal `_ensure_cloned` call

This path handles parent-repo packages (no `git_ref`). It calls `_ensure_cloned slug url`
with no third arg, defaulting to `HEAD` dir. No change needed — the two-level path is
handled by the default in `_ref_to_dir`.

---

## Migration Note

After deploying this change, run once:

```bash
pkg-mgr clean --all   # removes _ext_packages/ entirely (old flat layout)
pkg-mgr sync          # re-clones into new two-level layout
```

Existing `infra/<pkg>` symlinks will be recreated correctly by `sync`.

---

## Resolved Decisions

1. **`HEAD` sentinel** for packages with no `git_ref` — confirmed.
2. **`/` → `__`** (double underscore) in branch names — confirmed.
3. **Migration**: one-time `clean --all && sync` — confirmed, no auto-migration.
4. **Full SHA** as directory name — confirmed.

---

## Commit Strategy

Single commit:
1. `run` changes (Steps 1–7)
2. README update (path diagram + file layout section)
3. ai-log entry
4. Version bump in `default-pkg.yaml`
