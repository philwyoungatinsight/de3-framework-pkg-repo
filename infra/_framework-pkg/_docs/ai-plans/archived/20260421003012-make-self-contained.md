# Plan: Make `make` Self-Contained

## Goal

`make` (and `make clean-all && make`) must work end-to-end from a fresh `git clone`
without any manual steps.

## Current state

- `infra/<pkg>` symlinks ARE committed to git (git blob objects containing the relative
  path `../_ext_packages/<repo>/infra/<pkg>`). After a fresh clone they are dangling —
  `_ext_packages/` does not exist yet.
- `make` calls `./run --build`, which calls `setup_packages()`, which globs
  `infra/*/_setup/run`. With dangling symlinks the glob returns nothing and all
  per-package setup is silently skipped.
- `pkg-mgr --sync` populates `_ext_packages/` (clones the repo, creates the
  `_ext_packages/<slug>` symlink) so the `infra/<pkg>` symlinks resolve.
- Nothing currently calls `pkg-mgr --sync` before `./run --build`.

## Required build order

```
make
  └─ ./run --build
       1. sync_packages()      ← NEW: pkg-mgr --sync
       2. setup_packages()     (already there — installs tools via infra/*/_setup/run)
       3. ensure_backend()     (already there — bootstraps GCS state)
       4. apply waves + tests  (already there)
```

Step 1 must come before step 2. `setup_packages()` globs `infra/*/_setup/run` at call
time, so the symlinks must resolve before that glob runs.

## Approach: Makefile calls `./run` multiple times

The Makefile comment says "Do not change this file" but the build target can call `./run`
multiple times with different flags — each step explicit and separately skippable:

```makefile
build: FORCE
	./run --sync-packages
	./run --setup-packages
	./run --build
```

`--build` then drops its internal `setup_packages()` / `ensure_backend()` calls and
becomes purely "apply waves + tests". Each phase is visible, restartable, and composable.

### Alternative (simpler): keep `--build` as-is, add sync inside it

Add `sync_packages()` call inside `./run --build` before `setup_packages()`. The Makefile
stays at one line. Less visible but fewer moving parts.

**Recommended: Makefile approach** — explicit phases are easier to debug and re-run
partially (e.g. `./run --setup-packages` after adding a tool without re-syncing).

## Files to modify

### `infra/default-pkg/_framework/_git_root/run`

Add `-Y|--sync-packages` flag that calls `pkg-mgr --sync`:

```python
PKG_MGR = DEFAULT_PKG_DIR / '_framework' / '_pkg-mgr' / 'run'

def sync_packages():
    """Clone/link external package repos; ensure infra/<pkg> symlinks resolve."""
    _stream([str(PKG_MGR), '--sync'])
```

In argument parser, add:
```python
p.add_argument('-Y', '--sync-packages', action='store_true', dest='sync_packages')
```

In dispatch (standalone mode):
```python
if args.sync_packages and not any([args.build, args.apply, ...]):
    sync_packages()
    return
```

If keeping sync inside `--build` (alternative approach), also call it there before
`setup_packages()` — hard fail (no `ignore` wrapper), since dangling symlinks make
all subsequent steps meaningless.

### `Makefile` (the `build` target)

```makefile
build: FORCE
	./run --sync-packages
	./run --setup-packages
	./run --build
```

`--build` already includes `ensure_backend` + waves + tests. If we go with the explicit
Makefile approach, `--build` keeps its `setup_packages()` + `ensure_backend()` internally
for now (they're idempotent), and sync is just prepended. This avoids restructuring `--build`.

Simplest correct Makefile change:
```makefile
build: FORCE
	./run --sync-packages
	./run --build
```

`--build` already runs `setup_packages()` internally — so sync just needs to precede it.

## Design decisions

- **Hard fail on sync**: if `pkg-mgr --sync` fails, `setup_packages()` silently skips all
  external package setups (dangling symlinks). Abort loudly rather than proceed broken.

- **`--apply` does NOT call sync**: `--apply` is the incremental re-run mode; assumes
  environment is set up. Only `--build` (and the new `--sync-packages` standalone) touch
  package sync.

- **Idempotency**: `pkg-mgr --sync` is fast when packages are already synced (no-op for
  existing clones). Safe to call on every `make`.

- **`make clean-all && make`**: `clean-all` does not touch `_ext_packages/` or committed
  `infra/<pkg>` symlinks. `--sync-packages` on the next `make` finds the clone already
  present and just re-links — fast and correct.

## Open questions

None. Ready to implement.
