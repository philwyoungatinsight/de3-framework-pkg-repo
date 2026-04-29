# pkg-mgr: git_ref field support

## What changed

Implemented optional `git_ref` field for `framework_packages.yaml` entries, per plan
`infra/default-pkg/_docs/ai-plans/pkg-mgr-git-branch-support.md`.

## Files modified

- `infra/default-pkg/_framework/_pkg-mgr/run` — four sections changed:
  - Added `_is_commit_sha()` helper (7–40 hex chars → treat as SHA)
  - `_ensure_cloned()`: accepts optional 3rd arg `git_ref`; branches on SHA vs name;
    updates existing clones on re-sync (fetch+checkout); works for both `local_copy`
    and `linked_copy` paths, including migration branches
  - `_cmd_sync`: Python emits 5th field `ref`; `while read` captures `git_ref`;
    passes it to `_ensure_cloned`
  - `_cmd_status`: added `get_active_ref()` helper (git rev-parse); added `Ref` column
    to packages table
  - `_cmd_import`: parses `--git-ref <value>` flag; writes `git_ref:` key to YAML entry
- `infra/default-pkg/_framework/_pkg-mgr/README.md` — documented `git_ref` field,
  clone behaviour, and added `--git-ref` CLI example
- `infra/default-pkg/_config/default-pkg.yaml` — bumped to 1.0.6

## Behaviour

- No `git_ref` → shallow clone of default branch (unchanged)
- `git_ref: main` (or any branch/tag) → `git clone --depth=1 --branch main`; re-sync
  runs `fetch --depth=1 origin main && checkout FETCH_HEAD`
- `git_ref: abc1234` (SHA) → full clone + `git checkout abc1234`; re-sync runs
  `fetch origin && checkout abc1234`
- `pkg-mgr status` now shows checked-out branch or short SHA in a `Ref` column
