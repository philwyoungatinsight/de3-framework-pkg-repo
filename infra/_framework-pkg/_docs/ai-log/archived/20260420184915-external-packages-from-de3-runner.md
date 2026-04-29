# External Packages Wired to de3-runner

## Summary

This repo was forked from the de3-runner framework and had only `default-pkg` and
`pwy-home-lab-pkg` present locally. The remaining packages required by
`_requires_capability` (unifi-pkg, proxmox-pkg, maas-pkg, gcp-pkg, aws-pkg, azure-pkg,
image-maker-pkg, mesh-central-pkg, mikrotik-pkg, de3-gui-pkg, demo-buckets-example-pkg)
now resolve by fetching from the upstream de3-runner repo. Three bugs in the
`pkg-mgr sync` command were also found and fixed.

## Changes

- **`infra/default-pkg/_config/framework_packages.yaml`** — added `repo`, `source`, and `import_path` fields to all 11 external packages pointing at `https://github.com/philwyoungatinsight/de3-runner.git`
- **`infra/default-pkg/_config/framework_package_repositories.yaml`** — registered `de3-runner` repo entry
- **`infra/default-pkg/_framework/_pkg-mgr/run`** — fixed 3 bugs (see Root Cause)
- **`infra/default-pkg/_config/default-pkg.yaml`** — added `_provides_capability: default-pkg: 1.0.1` and version history block
- **`infra/default-pkg/_framework/_git_root/CLAUDE.md`** — added package version history convention under Conventions

## Root Cause (bugs fixed)

Three bugs in `pkg-mgr sync` and `pkg-mgr remove-repo`:

1. **Heredoc terminator not recognised** — `PYEOF | while ...` and `PYEOF | read ...` had
   the pipe on the same line as the `PYEOF` delimiter. Bash only recognises a heredoc
   terminator when it is alone on the line; anything after it (including `|`) prevents
   recognition and passes that text to Python as stdin, causing a `SyntaxError`. Fix:
   move the `| while ...` / `| read ...` to the `python3` invocation line.

2. **`| read -r active_names` subshell variable loss** (`_cmd_sync`) — each component
   of a bash pipeline runs in a subshell, so `read` in a pipe never assigns to the
   parent shell's variable. `active_names` was always empty, meaning stale symlinks
   were never pruned. Fix: use command substitution `active_names=$(python3 ... <<'PYEOF' ...)`.

3. **Same subshell issue for `pkg_names`** (`_cmd_remove_repo`) — `remove-repo` silently
   skipped removing all imported packages from the repo being deregistered. Same fix.

## Notes

- `pkg-mgr sync` is now the canonical way to restore symlinks after a fresh clone (once
  `_ext_packages/de3-runner` is present). On a fresh clone with no `_ext_packages/`,
  `sync` will auto-clone the repo from the `source:` URL in `framework_packages.yaml`.
- `de3-gui-pkg` was still tracked as real files in HEAD; this commit replaces them with
  the symlink to de3-runner, which is the correct long-term state.
