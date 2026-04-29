# pkg-mgr — Remote Package Manager

## Nomenclature

**Embedded package** — a package that lives directly in this repo as a real directory under
`infra/<pkg>/`. Has `package_type: embedded` in `framework_packages.yaml`. Always present;
`pkg-mgr` does not clone or symlink it.

**External package** — a package that lives in an external git repo. Has `package_type: external`
in `framework_packages.yaml`. `infra/<pkg>` is a symlink into
`_ext_packages/<repo>/<ref>/infra/<pkg>/`. Registered with a `repo:` field. Two sub-types:

- **Case A — parent-repo package**: the package's external repo was registered as a *parent
  repo* (see below). No `source:` URL on the package entry — the clone URL is stored in
  `framework_package_repositories.yaml`. `pkg-mgr sync` cannot re-clone parent repos
  automatically; run `pkg-mgr add-repo <url>` after a fresh `git clone`.

- **Case B — self-hosted package**: the package has its own `source:` URL in
  `framework_packages.yaml`. `pkg-mgr sync` clones it automatically.

**Parent repo** — an external git repository registered in `config/framework_package_repositories.yaml`
via `pkg-mgr add-repo <url>`. It is a *catalog* repo that may contain many packages. You
browse its packages with `list-remote` and import individual ones with `import`. The repo
is cloned once into `_ext_packages/<slug>/` and all Case A packages from it share that clone.

**Repo slug** — the short name used as the clone directory under `_ext_packages/`. For parent
repos the slug is chosen at registration time (defaults to the last URL component without
`.git`). For Case B packages the slug is derived automatically from the `source:` URL by the
same rule: `https://github.com/foo/bar.git` → `bar`. The slug appears as the `repo:` value
in `framework_packages.yaml` and as `_ext_packages/<slug>/`.

**`_ext_packages/`** — the gitignored directory at the repo root where all external clones
land. Symlinks at `infra/<pkg>` point into subdirectories here. Recreate the entire directory
by running `pkg-mgr sync` (Case B) or `pkg-mgr add-repo` for each parent repo (Case A).

---

## Purpose

`framework/pkg-mgr/run` manages packages that come from external git repos. It owns all
filesystem operations — cloning repos, creating/removing `infra/<pkg>` symlinks, and running
collision checks — so that the GUI and other callers only need to edit two YAML config files
and invoke `pkg-mgr sync`.

**Responsibility split:**

- **`config/framework_packages.yaml`** — lists every package (built-in and imported). Imported
  packages have `repo:` and optionally `source:` set.
- **`config/framework_package_repositories.yaml`** — lists registered parent repos (repos that
  are browsed for packages, not necessarily the repo a specific package lives in).
- **`pkg-mgr`** — reconciles the filesystem with those two files: clones repos, creates
  `infra/<pkg>` symlinks, removes stale symlinks, checks for collisions.
- **GUI** — opens the two config files in the file viewer for editing. After saving, the user
  clicks **↻ Sync** to run `pkg-mgr sync`.

Symlinks at `infra/<pkg-name>` pointing into `_ext_packages/<repo>/infra/<pkg-name>/` are
**committed to git**. The `_ext_packages/` clone directory is gitignored — recreate it on a
fresh clone by running `pkg-mgr sync`.

---

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

  # External, Case B — package has its own git repo (source URL present)
  - name: external-foo-pkg
    package_type: external
    exportable: false
    source: https://github.com/foo/bar.git
    repo: bar                    # slug derived from source URL (last component, no .git)
    git_ref: main                # required for all external packages
```

**`git_ref` field** (required): the *source* ref — committed and shared across all
developers. Determines which branch, tag, or commit SHA the package tracks.

- Branch or tag name → clone then `git checkout <git_ref>`; re-sync updates to latest.
- Commit SHA (7–40 hex chars) → clone then `git checkout <sha>`.

`git_ref` is required on all imported packages to ensure each clone lands in a predictable
subdirectory (`_ext_packages/<slug>/<ref_dir>/`) with no ambiguity.

**Slug derivation rule** (for `source:` entries): strip `.git`, take the last `/`-separated
component. `https://github.com/foo/bar.git` → `bar`.

The symlink created in both cases is:

```
infra/<name>  →  ../_ext_packages/<repo>/infra/<name>
```

---

## CLI Usage

```bash
./framework/pkg-mgr/run <command> [args]
```

### Commands

| Command | Description |
|---------|-------------|
| `clean` | Routine maintenance: remove dangling `infra/<pkg>` symlinks (target missing) and orphaned `_ext_packages/<slug>/` clones (slug not referenced by any active `repo:` entry) |
| `clean --all` | Destructive reset: remove every `infra/<pkg>` symlink pointing into `_ext_packages/` and delete `_ext_packages/` entirely. Run `sync` afterwards to restore |
| `sync` | Reconcile filesystem with current `framework_packages.yaml`: clone missing repos (for entries with `source:`), create missing `infra/<pkg>` symlinks, remove symlinks for packages no longer in config |
| `add-repo <url> [<name>]` | Clone a parent repo and register it in `framework_package_repositories.yaml`. `<name>` defaults to the URL slug |
| `remove-repo <name>` | Remove all packages imported from `<name>`, delete `_ext_packages/<name>/`, and deregister the repo. Does **not** touch GCS state (imported packages' state lives in the external repo's bucket) |
| `import <repo> <pkg> --git-ref <ref>` | Import one package from an already-cloned repo: runs collision check, creates symlink, adds entry to `framework_packages.yaml`. `--git-ref` is required |
| `remove <pkg>` | Remove one imported package: deletes `infra/<pkg>` symlink, removes entry from `framework_packages.yaml`. Does **not** delete the clone or touch GCS state |
| `list-remote <repo>` | List public packages in a registered repo with `already_imported` flag |
| `check <repo> <pkg>` | Run collision check and print results; exits 0=clean, 1=collision |
| `status` | Print table of all imported packages: repo, source URL, symlink state |
| `rename <src> <dst>` | Rename a package: filesystem + config YAML + SOPS secrets + GCS state + internal dep patches. Options: `--dry-run`, `--skip-state` |
| `copy <src> <dst>` | Copy a package to a new name. `--skip-state` or `--with-state` is required. Options: `--dry-run`, `--skip-state`, `--with-state` |

### Examples

```bash
# Rename a local package (renames dir, config YAML, SOPS file, GCS state, internal deps)
./framework/pkg-mgr/run rename old-pkg new-pkg

# Preview a rename without changing anything
./framework/pkg-mgr/run rename old-pkg new-pkg --dry-run

# Copy a package (filesystem only, no GCS state)
./framework/pkg-mgr/run copy src-pkg dst-pkg --skip-state

# Copy a package including GCS Terraform state blobs
./framework/pkg-mgr/run copy src-pkg dst-pkg --with-state

# Routine maintenance — remove orphaned clones and dangling symlinks
./framework/pkg-mgr/run clean

# Full reset — wipe all ext-package symlinks and clones, then restore
./framework/pkg-mgr/run clean --all && ./framework/pkg-mgr/run sync

# Browse packages in a registered repo
./framework/pkg-mgr/run list-remote community-infra-pkgs

# Import a single package (--git-ref is required)
./framework/pkg-mgr/run import community-infra-pkgs some-pkg --git-ref main

# Import pinned to a specific branch
./framework/pkg-mgr/run import community-infra-pkgs some-pkg --git-ref develop

# Check for collisions before importing
./framework/pkg-mgr/run check community-infra-pkgs some-pkg

# Sync filesystem after editing YAML directly
./framework/pkg-mgr/run sync

# Register a parent repo
./framework/pkg-mgr/run add-repo https://github.com/org/community-infra-pkgs

# Remove an imported package (keeps clone)
./framework/pkg-mgr/run remove some-pkg

# See all imported packages
./framework/pkg-mgr/run status
```

---

## Rename and Copy

### `rename <src-pkg> <dst-pkg>`

Renames a package. Supports both **local** (real directory) and **imported** (symlink)
packages. Operations are sequential, not atomic — if interrupted mid-run, recovery requires
manual steps (see the log output to identify which phases completed).

**Local package phases** (in order):
1. `git mv infra/<src> infra/<dst>` — filesystem rename
2. `git mv infra/<dst>/_config/<src>.yaml infra/<dst>/_config/<dst>.yaml` then rename the
   top-level YAML key (`<src>:` → `<dst>:`) and all `config_params` sub-keys in-place
   (uses `ruamel.yaml` to preserve comments)
3. Decrypt SOPS secrets, rename `<src>_secrets:` key and config_params sub-keys, `git mv`
   the file, re-encrypt with `sops --encrypt --output` — **single write, no vulnerability window**
4. String-substitute `infra/<src>/` → `infra/<dst>/` in all `.hcl` files under the new dir
   (patches internal `dependencies` blocks)
5. Scan all `.hcl` files across the repo; warn about external references that need manual update
6. Migrate GCS Terraform state files (`gsutil cp` + `gsutil rm` per file) — skipped with
   `--skip-state`
7. Update `name:` field in `framework_packages.yaml`

**Imported package**: only renames the symlink and updates `framework_packages.yaml`.
No config/GCS work — the external code is untouched.

**Options**: `--dry-run` (print actions, execute nothing), `--skip-state` (skip GCS migration)

> **`--skip-state` warning**: only use this for packages that have never been deployed. If
> GCS state exists under the old name and you pass `--skip-state`, that state becomes
> unreachable after the rename (the tool will print a warning with the manual recovery
> commands).

### `copy <src-pkg> <dst-pkg>`

Copies a package to a new name. `--skip-state` or `--with-state` is **required** — there
is no default, because the choice has significant operational implications:

| Flag | Effect |
|------|--------|
| `--skip-state` | Filesystem + config + SOPS copied; new package starts with no GCS state (safe default for creating a template or new environment) |
| `--with-state` | Also copies GCS state blobs (source files are preserved); the new package inherits the deployed state of the source. Both packages now reference the same deployed infrastructure until one is re-applied |

**Local package phases**: same as rename phases 1–8, except phase 1 uses `cp -r` (not
`git mv`), `.terragrunt-cache/` directories are deleted from the copy, and the destination
config file is renamed/re-keyed inline. GCS state is copied (not moved) when `--with-state`.

**Imported package**: creates a second symlink alias pointing to the same external code and
adds a new entry in `framework_packages.yaml`.

> **After `copy`**: `config_params` values (IPs, names, passwords) are copied verbatim from
> the source. Update all deployment-specific values before running `./run --build` against
> the new package.

**Options**: `--dry-run` (print actions, execute nothing)

---

## Collision Detection

Two independent checks run before any import. Both are reported; unit-collisions block
import while config-collisions are warnings.

### Unit collision (hard error)

Two packages would place a `terragrunt.hcl` file at the same path under `infra/`. Checked
by walking the candidate package's `_stack/` tree and comparing relative paths against all
existing `infra/` units.

### Config collision (warning)

The candidate package's `_config/<pkg>.yaml` and an existing package's `_config/<pkg>.yaml`
both define the same `config_params` key path with different values. Silent overwrites on
deep-merge can corrupt config; the warning lets the user decide before proceeding.

`pkg-mgr check` exits 0 if neither type is found, 1 if any collision is present.

---

## File Layout

```
framework/pkg-mgr/
  run          # bash script — sources set_env.sh, implements all commands
  README.md    # this document

config/
  framework_packages.yaml              # package list (built-in + imported)
  framework_package_repositories.yaml  # registered parent repos

_ext_packages/                         # gitignored — cloned repos land here
  <repo-slug>/
    main/        ← clone at git_ref: main  (branch/tag names used as-is)
      infra/
        <pkg-name>/
    feature__foo/  ← clone at git_ref: feature/foo  (/ replaced by __)
      infra/
        <pkg-name>/
    HEAD/        ← clone with no git_ref (remote default branch)
      infra/
        <pkg-name>/

infra/
  <pkg-name>   ← symlink → ../_ext_packages/<repo>/<ref-dir>/infra/<pkg-name>/
```

Each `(repo-slug, ref)` pair gets its own clone directory, so two packages from the same
repo can be pinned to different refs without conflict. Packages sharing the same
`(repo-slug, git_ref)` continue to share one clone.

---

## GUI Integration

The **Packages** panel in the GUI exposes three buttons in its top bar:

- **`📄 framework_packages.yaml`** — opens the file in the file viewer for editing
- **`📄 pkg-repos.yaml`** — opens `framework_package_repositories.yaml` in the file viewer
- **`↻ Sync`** — runs `pkg-mgr sync` in the background and shows a collapsible output strip

After editing either config file in the file viewer and saving, click **↻ Sync** to reconcile
the filesystem. The sync strip turns green on success or red on failure and shows the full
`pkg-mgr` output.

The `remove` button on an external-repo chip calls `pkg-mgr remove-repo <name>`, which removes
all packages from that repo and deletes the clone.

Each package card in the expanded view also exposes **Rename** and **Copy** buttons. Clicking
either opens a modal dialog that collects the destination name (and, for Copy, whether to
include GCS state), then runs `pkg-mgr rename` or `pkg-mgr copy` in the background and
displays the output inline.

---

## Migration from Flat Layout

Earlier versions stored clones at `_ext_packages/<slug>/` (no `<ref>` subdirectory).
The new layout is `_ext_packages/<slug>/<ref>/`. After upgrading, run once:

```bash
pkg-mgr clean --all   # removes _ext_packages/ entirely
pkg-mgr sync          # re-clones into the new two-level layout
```

Existing `infra/<pkg>` symlinks are recreated correctly by `sync`.

---

## Fresh Clone Recovery

After a fresh `git clone` the `_ext_packages/` directory is absent and `infra/<pkg>` symlinks
are dangling. Restore them:

```bash
./framework/pkg-mgr/run sync
```

This re-clones all repos referenced by `source:` entries and creates any missing symlinks.
Parent repos (Case A packages with no `source:`) must be re-added manually via `add-repo`
since their clone URL is stored in `framework_package_repositories.yaml` but the actual clone
is gitignored.

---

## YAML Safety

`pkg-mgr` never uses shell redirect (`>`) to write YAML files. All writes use a `.tmp` file
followed by an atomic `os.replace()` so a failed write never truncates a config file.
