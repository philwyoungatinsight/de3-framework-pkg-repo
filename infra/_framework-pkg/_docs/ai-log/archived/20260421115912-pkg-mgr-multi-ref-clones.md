# pkg-mgr: multi-ref clone support (_ext_packages/<slug>/<ref>/)

## What changed

Implemented two-level clone layout so packages from the same repo can pin to different
`git_ref` values without conflict. Plan: `pkg-mgr-multi-ref-clones.md`.

## New layout

`_ext_packages/<slug>/<ref_dir>/` — one clone per (slug, ref) pair.
`infra/<pkg>` symlinks now point to `../_ext_packages/<repo>/<ref_dir>/infra/<pkg>/`.

- Branch/tag `feature/foo` → directory `feature__foo` (`/` replaced with `__`)
- No `git_ref` → `HEAD/` directory
- Packages sharing the same (slug, git_ref) still share one clone

## Files modified

- `infra/default-pkg/_framework/_pkg-mgr/run`:
  - Added `_ref_to_dir()` helper: converts git ref to safe dir name (`/` → `__`, empty → `HEAD`)
  - Added `_clone_dir()` helper: `_ext_packages/<slug>/<ref_dir>/`
  - `_ensure_cloned`: uses two-level dest; `mkdir -p` creates slug parent dir
  - `_create_symlink`: accepts `git_ref` param; uses `<ref_dir>` in target path
  - `_check_unit_collisions`, `_check_config_collisions`, `_check_collisions`: thread `git_ref`
  - `_resolve_pkg_repo`: uses `_clone_dir` for parent_cfg path (defaults to `HEAD/`)
  - `_cmd_sync`: passes `git_ref` to `_create_symlink`
  - `_cmd_import`: passes `git_ref` to `_check_collisions` and `_create_symlink`
  - `_cmd_list_remote`: uses `_clone_dir` for remote_cfg path
  - `_cmd_clean`: orphan walk now two levels; removes empty slug dirs
  - `_cmd_status` Python: repos table groups by (slug, ref_dir) with new `Ref` column;
    packages table `get_active_ref` uses two-level path
- `infra/default-pkg/_framework/_pkg-mgr/README.md`: updated file layout diagram,
  added migration note
- `infra/default-pkg/_config/default-pkg.yaml`: bumped to 1.1.0 (feature bump)

## Migration

Existing flat-layout clones at `_ext_packages/<slug>/` are incompatible. Run once:
```
pkg-mgr clean --all && pkg-mgr sync
```
