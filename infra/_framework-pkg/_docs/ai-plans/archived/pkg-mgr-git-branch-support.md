# Plan: pkg-mgr Git Branch Support

## Objective

Add optional `git_ref` support to the package management system so a package entry can
pin to a specific branch, tag, or commit SHA.  The default behaviour (shallow clone of
the default branch) must not change.

---

## Context

### Current system (local_copy path)

`infra/default-pkg/_framework/_pkg-mgr/run`

- `_ensure_cloned` (line 63): `git clone --depth=1 "$url" "$dest"` — always clones the
  remote HEAD, no ref selection.
- `_cmd_sync` (line 390): emits `ENTRY <name> <repo> <import_path> <source_url>` tuples
  from a Python heredoc, then calls `_ensure_cloned slug url`.  Only four fields are
  emitted; there is no channel for a ref.
- `_cmd_status` (line 745): Python table — shows symlink health but not current branch/commit.

### linked_copy path

Same gap: `git clone "$url" "$ext_clone"` (line 84/96) with no `--branch`.

### framework_packages.yaml schema (current)

```yaml
- name: some-pkg
  repo: slug
  source: https://github.com/org/repo.git   # optional
  import_path: some-pkg                       # optional, defaults to name
```

---

## Design Decisions

### 1 — Single `git_ref` field (not separate branch/tag/commit fields)

One field, one source of truth.  The clone command uses `--branch` for both branch names
and tags (Git treats them the same).  For a commit SHA the user must set `git_tag` (tag
that points to the SHA) or accept that we do a full clone and checkout.

**Chosen approach:** single `git_ref: <value>` field.  Heuristic at sync time:

- If `git_ref` is a 40- or 7-char hex string → treat as commit SHA → full clone, then
  `git checkout <sha>`.
- Otherwise → `git clone --branch <git_ref>` with `--depth=1` preserved.

### 2 — No breaking changes to existing entries

Packages without `git_ref` continue to get a shallow clone of the default branch.

### 3 — `git_ref` is advisory during linked_copy

For `linked_copy`, the external clone is a full repo; `git_ref` changes the initial
checkout, but the user controls updates. We call `git fetch && git checkout <git_ref>`
during sync if the clone already exists (same as current no-op for no-ref case).

### 4 — Status table shows active ref

Add a `ref` column to the `pkg-mgr status` output: shows the currently checked-out
branch or commit (short SHA).

### 5 — `_ensure_cloned` idempotency for ref changes

If the dest already exists and a `git_ref` is specified, run
`git -C "$dest" fetch --depth=1 origin <git_ref> && git -C "$dest" checkout FETCH_HEAD`
to update without a full re-clone.  For commit SHAs (no depth), use
`git fetch origin && git checkout <sha>`.

---

## Files to Modify

| File | Change |
|------|--------|
| `infra/default-pkg/_framework/_pkg-mgr/run` | Core changes (4 sections below) |
| `infra/default-pkg/_config/framework_packages.yaml` | Schema is backward-compatible; no forced changes, but document the new field |
| `infra/default-pkg/_framework/_pkg-mgr/README.md` | Document `git_ref` field |

---

## Implementation Strategy

### Step 1 — `_ensure_cloned`: accept optional `git_ref` param

```bash
_ensure_cloned() {
  local slug="$1" url="$2" git_ref="${3:-}"
  ...
}
```

**local_copy branch (lines 111–139):**

```bash
# New helper: is this a commit SHA?
_is_commit_sha() { [[ "$1" =~ ^[0-9a-f]{7,40}$ ]]; }

# Clone
if [[ -z "$git_ref" ]]; then
  git clone --depth=1 "$url" "$dest"
elif _is_commit_sha "$git_ref"; then
  git clone "$url" "$dest"              # full clone — depth would block SHA checkout
  git -C "$dest" checkout "$git_ref"
else
  git clone --depth=1 --branch "$git_ref" "$url" "$dest"
fi

# Existing repo — update to ref
if [[ -d "$dest" ]]; then
  if [[ -n "$git_ref" ]] && ! _is_commit_sha "$git_ref"; then
    git -C "$dest" fetch --depth=1 origin "$git_ref"
    git -C "$dest" checkout FETCH_HEAD
  elif [[ -n "$git_ref" ]]; then
    git -C "$dest" fetch origin
    git -C "$dest" checkout "$git_ref"
  fi
  return 0
fi
```

**linked_copy branch (lines 70–109):**

After the clone (or for existing clone), add:

```bash
if [[ -n "$git_ref" ]]; then
  git -C "$ext_clone" fetch origin
  git -C "$ext_clone" checkout "$git_ref"
fi
```

### Step 2 — `_cmd_sync`: emit and thread `git_ref`

Replace the Python heredoc at line 394 to emit a 5th field:

```python
ref = p.get("git_ref", "")
print(f"ENTRY {name} {repo} {import_path} {source} {ref}")
```

Update the `while read` line:

```bash
| while read -r _ pkg_name repo import_path source_url git_ref; do
```

Pass `git_ref` to `_ensure_cloned`:

```bash
_ensure_cloned "$slug" "$source_url" "$git_ref"
```

### Step 3 — `_cmd_status`: add ref column

In the Python block (line 745+), after resolving the symlink target, add:

```python
def get_active_ref(clone_path):
    import subprocess
    try:
        branch = subprocess.check_output(
            ["git", "-C", str(clone_path), "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        if branch == "HEAD":  # detached
            return subprocess.check_output(
                ["git", "-C", str(clone_path), "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL, text=True
            ).strip()
        return branch
    except Exception:
        return ""
```

Add a `ref` column to the imported-packages table showing the result.

### Step 4 — `_cmd_import` / `_cmd_add`: preserve `git_ref`

When `pkg-mgr import` writes a new entry to `framework_packages.yaml`, include
`git_ref` if `--git-ref <value>` is passed on the CLI.  This is a minor addition:

```bash
pkg-mgr import <url> <pkg-name> [--git-ref <ref>]
```

The underlying Python that writes the YAML entry gains an optional `git_ref` key.

---

## Testing Plan

1. Add a test entry to `framework_packages.yaml` with `git_ref: main` (explicit branch).
   Run `pkg-mgr sync` — verify clone succeeds and `git branch` inside the ext dir shows `main`.

2. Change `git_ref` to an older tag (e.g. `v0.1.0`) and re-run sync — verify checkout
   switches to the tag.

3. Try a 7-char commit SHA — verify full clone + detached HEAD at correct commit.

4. Remove `git_ref` — verify sync still works (shallow clone of default branch).

5. Run `pkg-mgr status` — verify ref column shows correct branch/short-SHA.

6. Run `pkg-mgr sync` on an entry with no `source:` (parent-repo style) — existing
   behaviour unchanged (no ref tracking for parent repos in this iteration).

---

## Open Questions

1. **Parent repo (`repo:` without `source:`) + `git_ref`**: currently parent repos are
   pre-cloned by the user.  Should `git_ref` force a checkout inside the parent repo clone?
   *Proposal: yes, but only emit a warning if the parent repo isn't cloned yet (same as today).*

2. **`pkg-mgr sync` update cadence for branches**: for a mutable branch ref (e.g.
   `git_ref: develop`), should `sync` always `git pull` or only on first clone?
   *Proposal: always update (fetch + checkout) so `sync` is the canonical "get latest"
   command.  Shallow clones gain `--update-shallow` on re-fetch.*

3. **Capability version vs. git_ref**: if a package provides `_provides_capability: foo: 1.2.0`
   but `git_ref: develop`, the capability version could be stale.  Out of scope for this
   plan — treat capability version as whatever the checked-out tree declares.

---

## Commit Strategy

Single PR with:
1. `run` changes (Steps 1–4)
2. README update
3. ai-log entry
4. Version bump in `default-pkg.yaml` (`_provides_capability`)
