# Plan: Call sops-mgr from fw-repo-mgr After Writing .sops.yaml

## Objective

After `fw-repo-mgr` writes a `.sops.yaml` key-config file into a target repo, it must
re-encrypt any existing `*.sops.yaml` secrets files in that repo using the new key
recipients.  Today this step is absent, so a repo whose `.sops.yaml` was updated by
`framework_settings_sops_template` could contain secrets encrypted to the old key set —
silently inaccessible to anyone whose key is in the new `.sops.yaml`.

The re-encryption must be done by calling `sops-mgr --re-encrypt` (not by calling
`sops updatekeys` directly) so that:
1. Every SOPS operation in the codebase is traceable by grepping for `sops-mgr`.
2. The logic stays in one place; future improvements (logging, dry-run, etc.) propagate
   automatically to all callers.
3. The README and CLAUDE.md "why use framework tools" rule stay factually correct.

This plan also adds a `--infra-dir` flag to `sops-mgr` so automation can scope the
file search to a specific target repo's `infra/` directory, and updates the README to
remove the "not called by automation" claim.

## Context

- **`sops-mgr`**: `infra/_framework-pkg/_framework/_sops-mgr/sops-mgr`
  - `_find_sops_files()` hardcodes `INFRA_DIR` from env (= parent repo's `infra/`).
  - Needs an optional `--infra-dir <path>` argument so callers can override the search
    root to a target repo's `infra/`.
  - `$_SOPS_MGR` is exported by `set_env.sh` so scripts call it as `"$_SOPS_MGR"`.

- **`fw-repo-mgr`**: `infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr`
  - Already sources `set_env.sh` at startup, so `$_SOPS_MGR` is available.
  - `_write_sops_yaml "$repo_dir"` (line 557) writes `.sops.yaml` into the target.
  - Re-encryption must happen immediately AFTER `_write_sops_yaml`, before `pkg-mgr sync`,
    so that any SOPS files copied by `_copy_framework_settings` are re-keyed before
    the commit at Step 5.

- **Graceful no-op**: `sops-mgr` already prints "no *.sops.yaml files found" and returns
  without error when there are no secrets files — correct behaviour for brand-new repos.

## Open Questions

None — ready to proceed.

## Files to Create / Modify

### `infra/_framework-pkg/_framework/_sops-mgr/sops-mgr` — modify

**Change 1**: Add `--infra-dir` to `parse_args()`.

```python
p.add_argument('-d', '--infra-dir', dest='infra_dir', default=None,
               metavar='PATH',
               help='search PATH for *.sops.yaml instead of $_INFRA_DIR '
                    '(used by automation to scope to a target repo)')
```

**Change 2**: Pass `infra_dir` override into `_find_sops_files()` and both command
functions.

```python
def _find_sops_files(infra_dir: Path | None = None) -> list[Path]:
    root = infra_dir if infra_dir is not None else INFRA_DIR
    return sorted(
        f for f in root.rglob('*.sops.yaml')
        if f.name != '.sops.yaml'
    )

def cmd_re_encrypt(infra_dir: Path | None = None):
    files = _find_sops_files(infra_dir)
    ...

def cmd_verify(infra_dir: Path | None = None):
    files = _find_sops_files(infra_dir)
    ...
```

**Change 3**: In `main()`, resolve the override and forward it:

```python
def main():
    args = parse_args()
    infra_dir = Path(args.infra_dir).resolve() if args.infra_dir else None
    if args.re_encrypt:
        cmd_re_encrypt(infra_dir)
    elif args.verify:
        cmd_verify(infra_dir)
```

### `infra/_framework-pkg/_framework/_sops-mgr/README.md` — modify

- Remove the "Why automation does not use this" section header and rewrite it as
  "When automation calls this", describing the fw-repo-mgr integration.
- Update the CLI reference to include `-d|--infra-dir`.
- Remove the sentence "It is **not called by automation**" from the Purpose section.

New "When automation calls this" section text:

```
## When automation calls this

`fw-repo-mgr` calls `sops-mgr --re-encrypt --infra-dir <target-repo>/infra/` immediately
after writing `.sops.yaml` into a generated repo.  This ensures that any `*.sops.yaml`
files already present in the repo (e.g. `gcp_seed_secrets.sops.yaml` copied from
`_framework_settings/`) are re-encrypted to the key set declared in the new `.sops.yaml`.

`$_SOPS_MGR` is exported by `set_env.sh` so scripts can invoke it as
`"$_SOPS_MGR" --re-encrypt --infra-dir "$repo_dir/infra"`.

Using `sops-mgr` (rather than calling `sops updatekeys` directly) means every SOPS
re-encryption operation in the codebase is discoverable by grepping for `sops-mgr` —
audit coverage, key-rotation traceability, and future improvements are all in one place.
```

### `infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr` — modify

After the existing `_write_sops_yaml "$repo_dir"` call (line 557), add:

```bash
  # Re-encrypt *.sops.yaml in the target repo using the keys just written to .sops.yaml.
  # No-op if the repo has no secrets files yet (new repos).
  echo "Re-encrypting SOPS files in $repo_dir ..."
  "$_SOPS_MGR" --re-encrypt --infra-dir "$repo_dir/infra"
```

### `CLAUDE.md` — modify

Add a new section after the "SOPS — CRITICAL RULES" block:

```markdown
# Why Use Framework Tools (Not Equivalent Shell Commands)

**Always call framework tools (`sops-mgr`, `pkg-mgr`, `unit-mgr`, etc.) instead of
their underlying shell equivalents (`sops updatekeys`, `pip install`, etc.).**

- **Traceability**: every SOPS re-encryption in the repo is discoverable by
  `grep -r sops-mgr`.  If you call `sops updatekeys` directly, that call is invisible
  to auditors, key-rotation reviewers, and future automation.
- **Single source of truth**: improvements (dry-run, logging, error formatting) land
  once in the tool and propagate to all callers automatically.
- **Consistency**: the framework tool enforces the correct flags, file-discovery scope,
  and error-exit behaviour — re-implementing these inline invites divergence.

This rule applies whenever a framework tool exists for the operation you need.  Do not
inline the equivalent shell command "for simplicity" — the cost is invisible operations.
```

## Execution Order

1. Edit `sops-mgr`: add `--infra-dir` to argparse, thread it into `_find_sops_files`,
   `cmd_re_encrypt`, `cmd_verify`, and `main`.
2. Edit `sops-mgr README.md`: remove "not called by automation", add "When automation
   calls this", update CLI reference.
3. Edit `fw-repo-mgr`: insert the `"$_SOPS_MGR" --re-encrypt --infra-dir` call after
   `_write_sops_yaml`.
4. Edit `CLAUDE.md`: add the "Why Use Framework Tools" section.
5. Write memory file and update `MEMORY.md`.
6. Bump `_provides_capability` and append `version_history.md` entry for
   `_framework-pkg` (code change in the framework).
7. Commit everything with an ai-log entry.

## Verification

```bash
# 1. Confirm sops-mgr --help shows --infra-dir
"$_SOPS_MGR" --help | grep infra-dir

# 2. Confirm fw-repo-mgr build calls sops-mgr (dry-run: grep the script)
grep -n "sops-mgr\|_SOPS_MGR" infra/_framework-pkg/_framework/_fw-repo-mgr/fw-repo-mgr

# 3. Run fw-repo-mgr build on one repo that has a .sops.yaml and check output for
#    "Re-encrypting SOPS files" and "sops-mgr: re-encrypt complete"
# (Requires a configured target repo with at least one *.sops.yaml.)
```
