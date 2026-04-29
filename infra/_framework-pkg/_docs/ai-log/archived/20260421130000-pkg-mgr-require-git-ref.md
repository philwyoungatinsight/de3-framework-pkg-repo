# pkg-mgr: require git_ref on all imported packages

## What changed

Forced `git_ref` to be specified on every imported package to prevent directory conflicts
under `_ext_packages/<slug>/`. Without this requirement, a package with no `git_ref` would
clone into `_ext_packages/<slug>/HEAD/` while a package with an explicit ref clones into
`_ext_packages/<slug>/<ref>/`. If both existed simultaneously the slug directory would
contain a mix of git repos and subdirectories depending on layout version, causing ambiguity.

- `_cmd_sync` Python block: validates all packages with `repo:` have `git_ref:` before
  emitting ENTRY lines; exits 1 with per-package errors if any are missing
- `_cmd_import`: `--git-ref <ref>` is now required; errors immediately if omitted
- `framework_packages.yaml`: fixed `aws-pkg` (had `git_ref` commented out); updated header
  comment to say `git_ref` is **required** with a note on why
- `README.md`: updated `git_ref` field docs (optional → required), CLI table, and examples

## Files modified

- `infra/default-pkg/_framework/_pkg-mgr/run`
- `infra/default-pkg/_config/framework_packages.yaml`
- `infra/default-pkg/_framework/_pkg-mgr/README.md`
- `infra/default-pkg/_config/default-pkg.yaml` — bumped to 1.2.1
