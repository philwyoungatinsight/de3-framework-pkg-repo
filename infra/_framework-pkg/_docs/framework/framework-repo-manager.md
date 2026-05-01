# fw-repo-mgr — Framework Repository Manager

`fw-repo-mgr` creates and maintains de3 framework repos from a template source. Repos are
treated as generic package containers — a package can hold source code, configs,
documentation, build scripts, or any other versioned artifact.

## Concepts

**Toolshed** — a designated framework repo that is the ecosystem entry point. Any repo
discoverable by walking the toolshed tree is part of the framework, enabling browse,
search, and visualisation without a separate registry service.

**Package repo** — a framework repo containing one or more packages. Packages are
self-contained: each owns its Terraform modules, provider templates, config files, and
stack units.

**Why git as the substrate** — the unit of distribution (a repo) and the discovery surface
(the toolshed tree) are transparent and inspectable with standard tools. There is no
proprietary artifact format and no opaque index. If you can clone it, you can audit it.
Registering a new repo requires only linking it from the toolshed — no separate process.

---

# Using `fw-repo-mgr`

## Workflow

```
fw-repo-mgr --build [<name>] [--force-push]   # build/sync all repos or a named one
fw-repo-mgr --validate [<name>]               # check naming rules only
fw-repo-mgr --status                          # show local state of all configured repos
```

All repos are declared in `framework_repo_manager.yaml` under `framework_repos:`.
The tool lives at `infra/_framework-pkg/_framework/_fw-repo-mgr/run` and is
available as `$_FW_REPO_MGR` after sourcing `set_env.sh`.

## Per-repo fields reference

| Field | Type | Purpose |
|-------|------|---------|
| `name` | string | Target repo name; must satisfy `framework_package_naming_rules` |
| `source_repo` | map | Template source — `name` resolves via `source_repo_defaults`; `url`/`ref` override |
| `local_only` | bool | If `true`, build locally but skip all remote pushes (see below) |
| `new_repo_config.git-remotes` | list | Remote targets: `name`, `git-source` URL, `git-ref` |
| `labels` | list | Metadata (`_purpose`, `_docs`) consumed by the fw-repos visualiser |
| `framework_packages` | list | Packages to embed or link; first with `is_main_package: true` anchors settings |

## The `is_main_package` flag

Every repo **must** resolve to exactly one main package. `fw-repo-mgr` resolves it in order:

1. `config_package: <pkg>` on the repo entry — explicit override, takes precedence over all
2. `is_main_package: true` on any `framework_packages` entry — explicit annotation
3. The single embedded package, if exactly one exists — implicit default, no annotation required

If none of the above applies (zero embedded packages, or multiple embedded with none annotated),
`fw-repo-mgr --validate` and `fw-repo-mgr --build` both fail with:

```
ERROR: repos_must_have_main_package: '<repo>' has multiple embedded packages [...] with none marked is_main_package: true
```

Enforce this check by adding to `framework_package_naming_rules`:

```yaml
- name: repos_must_have_main_package
  value: true
```

`fw-repo-mgr` uses the resolved main package to:

1. Write `config/_framework.yaml` with `main_package: <pkg>` — the bootstrap file `set_env.sh`
   reads on every source to export `_FRAMEWORK_MAIN_PACKAGE` and `_FRAMEWORK_MAIN_PACKAGE_DIR`
2. Copy `_framework_settings/` files into `infra/<pkg>/_config/_framework_settings/`
3. Apply `framework_settings_template` overrides (e.g. shared GCS backend) into that directory
4. Write `framework_packages.yaml` into `infra/<pkg>/_config/_framework_settings/`

See [config-files.md](config-files.md#configframeworkyaml----the-one-true-anchor) for what
`main_package` means at runtime — three-tier config lookup, env vars, and discovery.

## Validating a new repo locally before creating remotes — `local_only: true`

Add `local_only: true` to a repo entry to build the full repo structure on disk
**without** creating or pushing to any remote. This lets you inspect the generated
files, run `fw-repo-mgr --status`, and confirm the layout before publishing.

```yaml
framework_repos:
  - name: de3-my-new-pkg-repo
    local_only: true          # ← remove this line once you're happy with the local repo
    source_repo:
      name: de3-framework-pkg-repo
    new_repo_config:
      git-remotes:
        - name: origin
          git-source: https://github.com/you/de3-my-new-pkg-repo.git
          git-ref: main
        - name: gitlab
          git-source: git@gitlab.com:you/de3-my-new-pkg-repo.git
          git-ref: main
    framework_packages:
      - name: my-new-pkg
        package_type: embedded
        exportable: true
        is_main_package: true
```

**`local_only: true` is optional.** Omit it to build and publish in a single pass:

```bash
fw-repo-mgr --build de3-my-new-pkg-repo   # builds locally, creates remotes, pushes — one run
```

Use `local_only: true` only when you want to inspect the generated file layout before any remote is touched.

**What `local_only: true` does:**
- Runs all build steps (rsync source, prune infra, write framework settings, `pkg-mgr --sync`, commit)
- Skips Steps 7–8 entirely — no remote repos are created, no git remotes are added, no push is attempted
- `fw-repo-mgr --status` shows the repo with a `(local-only)` flag in the STATUS column
- `git-auth-check.py` skips auth validation for the repo's `git-remotes` (those hosts may not be set up yet)

**Two-pass workflow** (when you want to inspect before publishing):

Phase 1 — local build:
1. Add the entry with `local_only: true`
2. `fw-repo-mgr --build de3-my-new-pkg-repo` — creates `~/git/de3-generated-framework-repos/de3-my-new-pkg-repo/`
3. Inspect: check file layout, run `git log`, verify packages with `fw-repo-mgr --status`

Phase 2 — publish:
4. Remove `local_only: true` from the YAML entry
5. `fw-repo-mgr --build de3-my-new-pkg-repo` — creates the GitHub repo (via `gh`) and GitLab repo (via `glab api`) automatically, then pushes to both

---

# Appendix A — Mapping to ITSM / ITIL terminology

For readers working in an ITSM context, the following table maps native
concepts in this system to their ITIL equivalents. This mapping is provided as
a crosswalk for governance, audit, and enterprise-architecture review; it is
not a claim that the system implements ITIL as a framework.

| Native concept | ITSM / ITIL equivalent | Notes |
|---|---|---|
| Toolshed repo | Service Catalog &nbsp;/&nbsp; Definitive Media Library (DML) | Authoritative entry point for what is available and where the trusted artifacts live. |
| Package repo | Configuration Item (CI), type *package* | Each repo is a versioned, identifiable CI with known provenance via git history. |
| Toolshed tree | Federated Configuration Management Database (CMDB) | The parent/child structure encodes relationships between CIs and is fully walkable from the root. |
| Cross-repo package dependency | CI relationship (*depends-on* / *composed-of*) | Declared in the dependent repo; resolvable through the toolshed. |
| Generated repo composing existing packages | Release Package (Release & Deployment Management) | Assembled from existing CIs into a deployable unit. |
| Pulling or installing a package | Service Request | Fulfilled against the catalog. |
| Updating a package or repo | Change Record | The git commit history serves as the change log for the corresponding CI. |