# AI Log Summary

Reverse-chronological summary of significant AI-assisted work sessions.
Individual logs deleted after consolidation here.

---

## 2026-04-26 — Right-click context menu on Framework Repos canvas

- Removed left-click git URL opening from Mermaid class diagram nodes (was triggering accidentally during canvas drag)
- Added right-click context menu on repo nodes with two actions: "Open Git URL" and "Open framework_package_repositories.yaml"
- URL items grey out when data is unavailable (local-only repo = no URL; no `main_package` = no yaml link)
- Menu dismisses on click-outside or Escape; position clamped to viewport
- README updated to describe current Mermaid-based view (was still describing old Cytoscape implementation)

---

## 2026-04-26 — Clean up defunct repos in fw-repos visualizer; add local_only support

- `fw-repos-visualizer` scanner now reads URL from `new_repo_config.git-remotes[0].git-source` exclusively; `upstream_url` removed from all config and scanner
- Scanner skips BFS enqueue for repos with `local_only: true`; propagates the flag into declared stubs for visualizer rendering
- de3-runner's `framework_repo_manager.yaml`: removed active `pwy-home-lab-pkg` entry (was triggering stale GitHub clone); replaced with generic commented example using new schema
- Both `known-fw-repos.yaml` cache files deleted to force fresh scan
- `fw-repo-mgr build`: skips remote push for repos with `local_only: true`; `status` command shows `(local-only)` flag
- `fw-repo-mgr`: `local_only` documented in usage and in `framework-repo-manager.md`; README updated with new doc link
- `_framework-pkg` version bumped (de3-runner)

---

## 2026-04-26 — feat(fw-repos): clickable hyperlinks in DOT output

- Package nodes (ellipses) now carry `URL=` pointing to the repo browse URL
- Repo cluster labels now carry `URL=` linking to `framework_repo_manager.yaml` via GitHub `/blob/HEAD/`
- `scanner.py`: fixed missing `main_package` backfill from declared stubs so cluster URLs populate correctly
- `renderer.py`: `_to_browse_url()` normalizes git URLs; `_fw_repo_mgr_url()` builds the config file link
- `_framework-pkg` bumped `1.13.0` → `1.14.0`

---

## 2026-04-23 — Add Framework Repos Cytoscape view to de3-gui

- New "Framework Repos" explorer root added to the de3-gui dropdown, visualising repos as Cytoscape compound nodes with packages as children
- Reads `config/tmp/fw-repos-visualizer/known-fw-repos.yaml`; Refresh button re-runs `fw-repos-visualizer --list`
- Layout algorithms: Force (cose), Tree (breadthfirst), Layered (dagre via `cytoscape-dagre`), Saved (preset from file)
- Per-repo collapse/expand and bulk Collapse All/Expand All via Collapse dropdown
- All display toggles (packages, lineage edges, source badge, URL, type badge, exportable) in Appearance dropdown
- Node positions persisted to `state/fw-repos-layout.yaml` (GUI-owned, never touched by fw-repos-visualizer)
- `de3-gui-pkg` version bumped to 0.4.0

---

## 2026-04-23 — Fix wave-mgr crash after ephemeral→ramdisk rename

- `wave-mgr` crashed with `KeyError: '_EPHEMERAL'` on every `./run` invocation after the rename commit
- `_EPHEMERAL_RUN` variable renamed to `_RAMDISK_MGR_RUN`; env lookup updated from `ENV['_EPHEMERAL']` to `ENV['_RAMDISK_MGR']`
- Root cause: rename commit updated `set_env.sh` but did not grep for consumers of `_EPHEMERAL` in the codebase

---

## 2026-04-23 — Consolidate 3-tier framework settings resolution

- `config-mgr fw-setting <name>` subcommand added — resolves a framework settings filename through the canonical 3-tier lookup and prints the absolute path of the winning file
- `ramdisk-mgr` both inline 3-tier bash blocks (setup and teardown modes) replaced with `"$_CONFIG_MGR" fw-setting framework_ramdisk` — single source of truth
- `framework_config.py` new public `fw_cfg_path(root, filename)` function available to any Python tool without importing config-mgr internals
- `unit-mgr::_read_framework_backend()` fixed — was reading from wrong path (missing `_framework_settings/`) with no 3-tier resolution; now uses `fw_cfg_path()`

---

## 2026-04-23 — Document set_env.sh and rewrite config-overview.md

- `set_env.sh` reorganised with section headers (root paths / tool paths / dynamic dirs / config pkg / GCS) and inline comments for every non-obvious variable
- 3-tier GCS bucket lookup and config-package resolution now documented in comments
- `_CONFIG_MGR` comment updated to reflect its full CLI: `generate/get/set/set-raw/move`
- `config-overview.md` rewritten as a developer landing page; every link in the old file was broken
- New doc covers: `set_env.sh` entry point, two config kinds (package vs framework), 3-tier `_framework_settings/` lookup, `$_CONFIG_MGR` subcommands table, SOPS rules, further reading links

---

## 2026-04-22 — Ephemeral dir: skip creation when size_mb=0

- `framework_ephemeral_dirs.yaml` now accepts `size_mb: 0` to disable ephemeral RAM-drive setup for an entry
- `_ephemeral/run` skips the entry entirely (no `mkdir`, no mount) when `size_mb == 0`
- `_EPHEMERAL_DIR` entry set to `size_mb: 0` to opt out of ephemeral dir creation

---

## 2026-04-21 — Three-tier framework config lookup via `config/_framework.yaml`

- New `config/_framework.yaml` declares the "config package" (`pwy-home-lab-pkg`); this is the single bootstrap anchor
- `set_env.sh` reads it and exports `_FRAMEWORK_CONFIG_PKG` / `_FRAMEWORK_CONFIG_PKG_DIR`; pre-existing env var wins
- All framework config lookups now use three tiers: `_framework-pkg/_config/` → `_FRAMEWORK_CONFIG_PKG/_config/` → `config/`
- `framework_config.py`, `packages.py`, `pkg-mgr/run`, `root.hcl`, `set_env.sh` all updated with the middle tier
- Deployment-specific `framework_*.yaml` files can now live in `pwy-home-lab-pkg/_config/` instead of top-level `config/`
- `config-files.md` updated to document three-tier lookup and the `_framework.yaml` anchor concept

---

## 2026-04-21 — Move framework_packages.yaml to config/

- `framework_packages.yaml` moved from `infra/_framework-pkg/_config/` to `config/`
- Prior "bootstrap anchor" rationale was stale — `find_framework_config_dirs()` does not read this file
- `packages.py:load_framework_packages()` and `pkg-mgr/run:FRAMEWORK_PKGS_CFG` updated to use two-path helpers
- `_framework-pkg/_config/` now contains only `_framework-pkg.yaml`
- `config-files.md` hardcoded-paths table removed; no framework config files are hardcoded to a single path

---

## 2026-04-21 — Move remaining framework config files to config/

- `framework_config_mgr.yaml`, `framework_package_management.yaml`, `framework_package_repositories.yaml` moved from `_framework-pkg/_config/` to `config/`
- `packages.py`: added `_fw_cfg_path()` two-path helper for `framework_config_mgr.yaml`
- `pkg-mgr/run`: added `_fw_cfg()` shell helper for `framework_package_*.yaml`
- `_framework-pkg/_config/` now contains only two files: `framework_packages.yaml` (anchor) and `_framework-pkg.yaml`
- `config-files.md`: new section documents discovery pattern, hardcoded paths, and full location inventory

---

## 2026-04-21 — Organize framework config: deployment overrides via `config/`

- 11 deployment-specific files moved from `infra/_framework-pkg/_config/` to `config/` at git root
- `framework_config.py`: new `find_framework_config_dirs()` returns `[_framework-pkg/_config/, config/]`; `load_framework_config()` now accepts a list, later dirs override earlier
- `root.hcl`: `framework_backend.yaml` found via `fileexists()` — checks `config/` first, falls back to `_framework-pkg/_config/`
- `set_env.sh`: `_GCS_BUCKET` export now checks `config/framework_backend.yaml` first
- `clean_all/run`, `validate-config.py`, `run`, `pkg-mgr`: all updated to use `find_framework_config_dirs()`
- `_framework-pkg/_config/` now contains only 5 framework-owned files (packages, config-mgr, pkg-mgr config, version)

---

## 2026-04-21 — pkg-mgr: add package_type field; rename public → exportable

- Added explicit `package_type: embedded | external` to all 13 entries in `framework_packages.yaml`
- Renamed `public` → `exportable` throughout config and code — clearer name for "can other repos import this?"
- `pkg-mgr --sync` now validates `package_type` consistency and errors on missing/wrong values
- `_cmd_status`, `_cmd_clean`, `_cmd_list_remote`, `_cmd_import`, `_cmd_copy` all updated to use `package_type`
- Status output now shows `embedded`/`external` in Method column; footer shows `N external · N embedded`
- `framework_manager.yaml` examples updated; README Nomenclature and schema section rewritten

---

## 2026-04-21 — Add fw-repo-mgr: framework repository manager

- New tool `infra/_framework-pkg/_framework/_fw-repo-mgr/run` for building and maintaining downstream framework repos
- Supports two workflows: **splitting** (clone multi-pkg source, prune to one pkg) and **combining** (clone template, import pkgs from separate repos via pkg-mgr)
- `fw-repo-mgr -b <name>`: clone source → prune `infra/` → overwrite `framework_packages.yaml` → `pkg-mgr --sync` → commit → push
- `fw-repo-mgr status`: table showing all configured targets with clone/dirty/clean status
- Config in `framework_manager.yaml`: `source_repos` registry (reusable named source URLs) + `framework_repos` target list

---

## 2026-04-21 — Make `make` self-contained via --sync-packages

- `make build` now runs `./run --sync-packages` before `./run --build`
- Fresh `git clone` + `make` works end-to-end without manually running `pkg-mgr --sync`
- Added `sync_packages()` function and `-Y|--sync-packages` flag to `./run`
- Hard-fails if `pkg-mgr` is missing — dangling symlinks cause silent skips in `setup_packages()`
- README updated to document the self-contained build flow

---

## 2026-04-21 — pkg-mgr: auto-migrate inclusion method changes

- `--sync` now migrates repos when `inclusion_method` changes in config
- `local_copy` → `linked_copy`: detects real dir, full-clones to external dir, replaces with symlink
- `linked_copy` → `local_copy`: detects symlink, removes it, shallow-clones in place; notes unused external clone
- Previously: `local_copy → linked_copy` errored; `linked_copy → local_copy` silently did nothing

---

## 2026-04-20 — pkg-mgr: flag-style CLI and verbose status

- `pkg-mgr` now uses `--flag` style (`--sync`, `--status`, `--rename`, etc.) matching `./run`
- Added `-V|--status-verbose`: same table as `--status` plus a "Path" column with the resolved absolute path of each package
- Added `_usage` function; short flags: `-S` status, `-V` verbose, `-s` sync, `-c/-C` clean, `-A` add-repo, `-i` import, `-r` remove, `-l` list-remote
- GUI (`homelab_gui.py`) updated: `"sync"` → `"--sync"`, `"remove-repo"` → `"--remove-repo"`, rename/copy args use `f"--{mode}"`

---

## 2026-04-20 — pkg-mgr status: rich ANSI/unicode table output

- `pkg-mgr status` now renders a three-section table matching the `./run --list-waves` visual style
- Section 1: config header (default_inclusion_method, external_package_dir)
- Section 2: repos summary table with Repo/Method/Source/Clone/#pkgs columns
- Section 3: packages table with #/Package/Repo/Method/Version/S columns
- Version read from `_provides_capability` in each package's YAML (fault-tolerant — empty cell if missing)
- `framework_package_management.yaml` committed (was untracked from previous session)

---

## 2026-04-20 — External packages wired to de3-runner; pkg-mgr bugs fixed

- `framework_packages.yaml`: added `repo`, `source`, `import_path` for 11 external packages pointing at `philwyoungatinsight/de3-runner`
- `framework_package_repositories.yaml`: registered `de3-runner` repo
- `pkg-mgr run`: fixed 3 bugs — heredoc terminator not recognised (`PYEOF |` on same line), and two `| read` subshell variable-loss bugs in `sync` and `remove-repo`
- `_framework-pkg.yaml`: added `_provides_capability: _framework-pkg: 1.0.1` with version history block
- `CLAUDE.md`: new convention — bump `_provides_capability` + append version history entry on every package code change

---

## 2026-04-20 — Add `/readme-review` skill documentation

- New `.claude/commands/readme-review.md` skill: processes one pending README per invocation using `readme-maintenance/README-tracker.md`
- Skill reads surrounding code, assesses accuracy, updates README if stale, marks tracker row `updated` or `ok`, and commits
- `infra/_framework-pkg/_docs/claude-skills.md` updated with `/readme-review` section covering algorithm and README writing rules

---

## 2026-04-20 — Relocate git-root files to `_framework/_git_root`

- 8 root-level files moved to `infra/_framework-pkg/_framework/_git_root/` and replaced with relative symlinks
- `.gitignore` kept as a real file at root — git opens it with `O_NOFOLLOW` and a symlink produces ELOOP, silently breaking all ignore rules
- Files relocated: `CLAUDE.md`, `.gitlab-ci.yml`, `Makefile`, `README.md`, `root.hcl`, `run`, `set_env.sh`, `.sops.yaml`
- All tools verified working post-move: `source set_env.sh`, SOPS decrypt, `git status` (no warnings)

---

## 2026-04-20 — GUI run script: use _activate_python_locally from python-utils.sh

- `infra/de3-gui-pkg/_application/de3-gui/run`: removed custom `_ensure_venv`; venv setup now delegates to `_activate_python_locally` from `_utilities/bash/python-utils.sh`
- Call moved to global scope so every subcommand (`--run`, `--build`, `--test`) gets a venv with requirements, not just `--deps`
- Handles stale venvs automatically (path mismatch after directory move)
- `--deps` is now a no-op; `make deps` likewise — setup is unconditional at startup

---

## 2026-04-19 — GUI run script: venv setup via uv

- `infra/de3-gui-pkg/_application/de3-gui/run`: added `_ensure_venv()` — checks for active venv, creates `.venv` via `uv` if absent, activates it; fails clearly if `uv` not installed
- `_deps()` now calls `_ensure_venv` before installing requirements, ensuring packages land in the venv not the system
- File had been accidentally deleted by a prior bad commit; restored from git history with new changes applied

---

## 2026-04-19 — ephemeral --mode flag, set_env.sh refactor, HWE monitor path fix

- `framework/ephemeral/ephemeral.sh`: added `--mode` flag for configurable directory permissions; mode-only changes apply without remount; Linux size changes now use `/dev/shm` staging + umount instead of `mount --move`
- `framework/ephemeral/run`: reads `mode` field from `framework.yaml` and passes `--mode` to `ephemeral.sh`
- `set_env.sh`: refactored into three named functions; `exit` → `return` for sourced-script safety; calls `framework/ephemeral/run` automatically when `validate-config.py` actually fires (mtime < 5s check)
- `infra/maas-pkg/_modules/maas_machine/main.tf`: HWE monitor scripts moved from `/tmp` to `$_DYNAMIC_DIR/hwe-monitor/`
- `config/framework.yaml`: improved ephemeral_dirs field docs; added explicit `size_mb: 64` to default entry

---

## 2026-04-19 — Fix unit-mgr / pkg-mgr bugs (review-unit-pkg-mgr)

- `sops_secrets.py`: eliminated vulnerability window in same-package move — two SOPS writes collapsed into one; old keys removed and renamed keys added in a single atomic `_sops_encrypt_from_dict` call
- `config_yaml.py`: `_rename_keys_inplace` rewritten to accept `old_to_new: dict[str, str]`; dead `if k in new_keys` branch (always False) removed; call site now builds an explicit mapping
- `main.py`: removed dead `external_outbound` filter and log line (scanner never produces this category)
- `pkg-mgr/run`: `_gcs_bucket` subprocess calls reduced from 3 to 1 in the `--skip-state` warning block
- `unit-mgr/README.md`: removed phantom "External outbound" row from Phase 2 category table
- `pkg-mgr/README.md`: collapsed 8-item rename phase list to 7 (items 2+3 were one code phase)

---

## 2026-04-19 — Ephemeral dirs automation

- `set_env.sh`: added `_EPHEMERAL_DIR=$_DYNAMIC_DIR/ephemeral` alongside other dynamic dirs
- `config/framework.yaml`: added `ephemeral_dirs` section — list of `{env_var, size_mb}` entries declaring RAM-backed dirs
- `framework/make-ephemeral-dirs/run`: new script reads the YAML, resolves env vars at runtime, calls `ephemeral.sh` for each; skips in CI/non-interactive contexts
- `scripts/human-only-scripts/setup-ephemeral-dirs/run`: now delegates to `framework/make-ephemeral-dirs/run` instead of hardcoding a path
- Adding more ephemeral dirs now requires only a YAML entry + env var in `set_env.sh` — no script changes

---

## 2026-04-19 — pkg-mgr rename/copy commands + GUI dialog

- `framework/pkg-mgr/run`: added `rename` and `copy` commands with full 7-phase local-package logic (git mv, config YAML key migration, SOPS file rename, HCL dep patch, GCS state migration) and symlink-only path for imported packages
- `framework/pkg-mgr/run`: `copy` requires explicit `--skip-state` or `--with-state` — no default — to prevent silent GCS state inheritance
- `framework/pkg-mgr/README.md`: added rename/copy rows, examples, and "## Rename and Copy" section
- `homelab_gui.py`: added `_float_pkg_op_dialog()` modal and Rename/Copy buttons in `_pkg_card()` expanded header; 6 new event handlers drive the dialog
- `framework/unit-mgr/run`: fixed pre-existing relative import bug (`python3 -m unit_mgr.main` instead of `python3 path/to/main.py`)

---

## 2026-04-19 — Rename manage-unit → unit-mgr

- `framework/manage-unit/` renamed to `framework/unit-mgr/` via `git mv`
- `framework/unit-mgr/manage_unit/` renamed to `framework/unit-mgr/unit_mgr/`
- `framework/unit-mgr/run` updated: path string and invocation style fixed (pre-existing bug: relative imports require `python3 -m unit_mgr.main`, not `python3 path/to/main.py`)
- `framework/unit-mgr/unit_mgr/main.py`: docstring and `argparse` prog name updated
- `framework/unit-mgr/README.md`: all `manage-unit`/`manage_unit` occurrences replaced
- `homelab_gui.py`: helper functions `_find_manage_unit_run`/`_parse_manage_unit_json` renamed and all call sites, path strings, and comments updated

---

## 2026-04-18 — Remote Package System

- `config/framework_package_repositories.yaml` created: registry of external git repos containing packages
- `config/framework_packages.yaml` updated: added `repo:` and `import_path:` fields; `external-foo-pkg` example documents the schema
- `scripts/human-only-scripts/pkg-mgr/run` created: central script for package lifecycle (sync, add-repo, remove-repo, import, remove, list-remote, check, status)
- `homelab_gui.py`: packages panel top bar now has `📄 framework_packages.yaml`, `📄 pkg-repos.yaml`, and `↻ Sync` buttons replacing the old `+ Repo` dialog
- `homelab_gui.py`: `sync_packages` background handler calls `pkg-mgr sync` and shows output strip; all filesystem ops delegated to `pkg-mgr`
- `.gitignore`: added `_ext_packages/` (cloned repos recreated by `pkg-mgr sync`)

---

## 2026-04-18 — GUI: Sync Defaults from Current State

- `_load_state()` now falls back to `state/defaults.yaml` when `current.yaml` is absent (first boot / fresh clone / wiped container)
- `state/defaults.yaml` created: snapshot of the tuned look — dark theme, `pwy-home-lab-pkg` only, all preferred panel/wave display toggles, transient fields zeroed
- `scripts/ai-only-scripts/snapshot-gui-defaults/run` added: re-snapshots `defaults.yaml` from live `current.yaml` on demand
- Fixes: GUI previously fell back to stale Python class defaults on first boot, showing wrong theme, filters, and panel sizes

---

## 2026-04-18 — GUI: Dropdown Tooltips on All Menu Items

- `_appearance_menu_item()` helper gained optional `tooltip: str = ""` param; applied as native `title=` attribute when non-empty
- All 16 `_appearance_menu_item()` calls in `appearance_menu()` now pass descriptive tooltips (8 sections)
- All 4 `_appearance_menu_item()` calls in `panels_menu()` now pass descriptive tooltips
- All 6 `rx.dropdown_menu.item()` calls in `help_menu()` now have `title=`
- All 4 `rx.dropdown_menu.item()` calls in `_explorer_root_selector()` now have `title=`
- Used native browser `title=` throughout — `rx.tooltip()` avoided as it closes dropdowns on hover

---

## 2026-04-18 — GUI: Persistent Status Bar

- Added `show_status_bar` state var (default `True`, persisted) and `app_activity_active` computed var
- `static_status_bar()` component: 26px permanent bottom strip, highlighted (accent) when syncing, empty when idle
- `index()` converted to flex column (`display="flex", flex_direction="column", height="100vh"`)
- Main area wrapped in `flex="1" / min_height="0"` box; status bar appended at bottom gated on `show_status_bar`
- `startup_status_banner()` floating overlay gated on `~show_status_bar` (falls back when bar is off)
- Three internal `height="100vh"` / `height="calc(100vh - 36px)"` changed to `height="100%"` to fill flex parent
- "Status bar" checkbox added to Appearance → Layout section above "Floating panels mode"

---

## 2026-04-18 — GUI: Show GCS Sync Steps in Startup Banner

- Added `gcs_unit_sync_running` and `gcs_wave_sync_running` bool state vars to track background sync task progress
- `app_status_message` now has 5 states: initializing, inventory-only, inventory+GCS, unit-only, wave-only, both — banner stays visible until all syncs complete
- `sync_unit_status_from_gcs` sets flag on entry (in existing `async with self` block), wraps full body in `try/finally` to clear flag on all exit paths
- `sync_wave_status_from_gcs` updated identically
- Fixes: banner was clearing as soon as inventory completed, even though GCS syncs (gsutil ls + per-object cat) were still running

---

## 2026-04-18 — Update claude-skills.md with All Current Skills

- Added `/doit-with-watchdog`, `/watchdog-off`, `/work-on-maas`, `/annihilate-maas-machine` — all were missing from the doc
- Updated `/watchdog` to reflect runtime path resolution via `set_env.sh`, correct `*/2` schedule, and watchdog report structure
- Updated `/doit` to document resume mode (kebab-case plan stem) and the archive step
- Updated `/ship` algorithm to include the ai-log archival step

---

## 2026-04-18 — Add /doit-with-watchdog Skill

- New skill `.claude/commands/doit-with-watchdog.md` combines `/doit` plan execution with build watchdog monitoring
- Accepts `<plan-name> [polling-minutes]` — polling interval defaults to 2 min, configurable 1–59
- Registers watchdog cron job (idempotent) before executing plan; tears it down after `/ship` completes
- Inlines steps from `/watchdog`, `/doit` (Steps 8–10), and `/watchdog-off` since skills cannot call other skills
- Cron expression derived from polling interval: `*/N * * * *`; literal paths substituted at registration time

---

## 2026-04-18 — Remove Hardcoded Paths from /watchdog Skill

- `/watchdog` skill was silently failing: cron job pointed at `/home/pyoung/git/pwy-home-lab/...` (old repo name)
- Added Step 0 to resolve `GIT_ROOT` and `_DYNAMIC_DIR` at skill-invocation time via `git rev-parse` + `set_env.sh`
- All bash paths (`WATCHDOG_SCRIPT`, `WATCHDOG_LOG`, `WATCHDOG_REPORT`) now derived from runtime env vars
- Cron prompt: added explicit instruction to embed literal resolved paths before `CronCreate` (vars don't expand at fire time)
- Corrected log path from `~/.build-watchdog.log` to `${_DYNAMIC_DIR}/watchdog/build-watchdog.log`

---

## 2026-04-18 — Remove Empty Waves

- Removed `external.servers`, `external.storage`, `external.power` — all had no units assigned
- `external.servers` was vestigial: pve-1/pve-2 nodes are foundation units (no `_wave:`) that always run
- `external.storage` was a placeholder with no resources; `external.power` had a test playbook but nothing to test

---

## 2026-04-18 — Wave Renames — vm.proxmox.* → vms.proxmox.*

- 6 VM waves renamed: `vm.proxmox.mesh-central` → `vms.proxmox.utility.mesh-central`, `vm.proxmox.ubuntu/rocky` → `vms.proxmox.from-web.*`, `vm.proxmox.image-maker` → `vms.proxmox.custom-images.image-maker`, `vm.proxmox.packer/kairos` → `vms.proxmox.from-packer/from-kairos`
- Updated 15 `_wave:` fields in `pwy-home-lab-pkg.yaml`, wave definitions in 3 package configs, 8 test script comments
- Also committed `maas.servers` → `maas.servers.all` rename from prior session

---

## 2026-04-18 — Wave Renames — Clarify Wave Names Across the Stack

- Six waves renamed to consistent `<domain>.<subdomain>.<action>` scheme (e.g. `pxe.maas.seed-server` → `maas.servers`)
- `pxe.maas.machine-entries` → `maas.machine.config.power`; `pxe.maas.configure-plain-hosts` → `maas.machine.config.networking`
- `hw.proxmox.storage` → `external.proxmox.isos-and-snippets`; `pxe.maas.test-vms` → `maas.test.proxmox-vms`
- New doc `infra/maas-pkg/_docs/wave-machine-config-power.md` documents the power-driver registration wave
- `maas.machine.config.power` wave description updated in `maas-pkg.yaml` to accurately describe what it does
- `infra/de3-gui-pkg/_application/de3-gui/run` restored after accidental deletion from disk

---

## 2026-04-18 — Reorganize MaaS docs into maas-pkg/_docs

- Created `infra/maas-pkg/_docs/troubleshooting.md` with commission/stuck-in-New troubleshooting (moved from framework)
- `docs/framework/troubleshooting.md` MaaS sections replaced with stub + link
- `docs/background-jobs.md` MaaS job descriptions replaced with short summary + link to `maas-pkg/_docs/background-processes.md`
- Stale Tier 1 reference removed from GUI local state watcher description in `background-jobs.md`
- Two new GUI GCS sync tasks added to quick-reference diagram and inventory table
- `background-tasks.md` Tier 0b section links to `maas-pkg/_docs/background-processes.md`

---

## 2026-04-18 — Fix GUI terminal broken by hardcoded ports

- `_BACKEND_PORT = 8000` in `homelab_gui.py` broke the terminal iframe — app runs on 9000, not 8000
- All port references now read `HOMELAB_GUI_BACKEND/FRONTEND_PORT` env vars (set by `run` script from YAML)
- `de3-gui-pkg.yaml` is the single source of truth: `frontend_port: 9080`, `backend_port: 9000`
- `run` script fallbacks corrected from 8080/8000 to 9080/9000; smoke-test and browser-test defaults fixed
- `de3-gui-pkg.yaml` comments clarified to distinguish Reflex defaults from project values

---

## 2026-04-18 — GCS-native unit and wave build status

- `write-exit-status/run` now publishes `unit_status/<unit_path>/<ts>.json` to GCS on every apply/destroy (fire-and-forget; never blocks apply)
- Wave runner (`run`) writes `wave_status/<wave_name>/<ts>.json` at phase start (`running`) and end (`ok`/`fail`) via `utilities/python/gcs_status.py`
- GUI Tier 1 (`.terragrunt-cache` mtime scan + GCS cat fallback) removed; unit status now flows exclusively through Tier 0 exit-status YAMLs
- On load the GUI runs two new background tasks: `sync_unit_status_from_gcs` (recover prior-session unit statuses) and `sync_wave_status_from_gcs` (recover wave history)
- `refresh_wave_log_statuses()` merges GCS-derived wave entries for waves absent from the current session's `run.log`
- `scripts/human-only-scripts/purge-gcs-status/run`: prune old GCS status objects, keep last N per group
- GCS bucket gets 180-day lifecycle Delete rule on `unit_status/` and `wave_status/` prefixes via `gcp-pkg/_setup/seed`

---

## 2026-04-18 — Seed Packages: _setup/seed Convention and make seed

- `make seed` / `./run --seed-packages` now runs login→seed→test for every `infra/*/_setup/seed` script
- Seed logic moved from standalone script into `infra/<pkg>/_setup/seed` (aws, gcp, azure) — mirrors `_setup/run` tool-install convention
- `_setup/run` now delegates any args to `./seed` so the split is transparent to callers
- `infra/<pkg>.yaml` gains a `seed:` sub-key for account IDs, bucket names, region; secrets in `<pkg>_secrets.sops.yaml`
- Fixed Starlette 1.0 API break in GUI (`add_route` removed); fixed Mac venv `pip` missing via `install-requirements.sh`
- `utilities/python/install-requirements.sh`: omits `--system` when `VIRTUAL_ENV` is set to avoid uv permission error
- Framework docs (`package-system.md`, `README.md`, `docs/README.md`) updated with `_setup/seed` convention and `make seed` target

---

## 2026-04-17 — Eliminate remaining out-of-repo runtime paths

- `validate-config.py`: flag file moved from `~/.cache/pwy-home-lab/validate-config-last-run` to `<repo>/config/tmp/validate-config-last-run` — now isolated per checkout
- `config/framework.yaml`: removed now-unused `flag_file` key under `validate_config:`
- `homelab_gui.py`: replaced hardcoded `Path.home() / "git/de3"` fallback with `_find_repo_root()` that walks up from `__file__` looking for `root.hcl` as repo-root sentinel (`set_env.sh` could not be used as sentinel — the GUI app contains its own)
- `homelab_gui.py`: `gui_preview.html` path now uses `Path(os.environ.get("_GUI_DIR", "/tmp")) / "gui_preview.html"` to avoid collision between two running instances

---

## 2026-04-17 — Consolidate all runtime paths under _DYNAMIC_DIR

- Added `_WAVE_LOGS_DIR` and `_GUI_DIR` to `set_env.sh`; both dirs created under `_DYNAMIC_DIR`
- Wave runner (`run`) reads `_WAVE_LOGS_DIR` instead of hardcoded `~/.run-waves-logs`
- GUI (`homelab_gui.py`): `_TEST_APPLIED_MARKER`, state-check marker, and apply exit files now under `$_GUI_DIR`; unit-state.yaml moved to `$_DYNAMIC_DIR/unit-state/`; all `wave_logs_dir` YAML lookups replaced with `_wave_logs_dir()` helper
- `de3-gui-pkg.yaml`: removed `wave_logs_dir` key; `wave_tail_cmd` updated to use `$_WAVE_LOGS_DIR`
- `framework/clean-all/run`: removed `stage_move_wave_logs()` and `_read_move_wave_logs()` — logs are already in `_DYNAMIC_DIR`, nothing to move
- `config/framework.yaml`: removed `move_wave_logs: true` under `clean_all`

---

## 2026-04-17 — Isolate "pwy" naming to infra/pwy-home-lab-pkg

- Renamed `infra/gcp-pkg/_stack/gcp/us-central1/dev/test-bucket-pwy-3/` → `test-bucket-3/` (git mv)
- Updated comments/docstrings in `set_env.sh`, `manage-unit/main.py`, `lab_config.py`, `validate-config.py` from "pwy-home-lab" to "de3"
- Fixed `CLAUDE.md`: `pwy-home-lab-GUI` → `de3-gui-pkg`
- Updated package docs in `mikrotik-pkg`, `maas-pkg`, `image-maker-pkg`, `unifi-pkg` to use generic example names
- Fixed GUI (`homelab_gui.py`): default repo path, description string, and synthetic Cytoscape/ReactFlow demo element paths now use `pwy-home-lab-pkg/_stack/proxmox` and `pwy-home-lab-pkg/_stack/unifi` (not `proxmox-pkg`/`unifi-pkg`)
- Remaining `pwy` hits are GCP resource identifiers (bucket/project names) or frozen historical docs — intentionally left as-is

---

## 2026-04-17 — MaaS docs update: mgmt_wake_via_plug, commissioning scripts, Rocky 9 workarounds

- Machine table corrected: ms01-02 has `mgmt_wake_via_plug: true` (AMT loses standby when fully off); ms01-03 has a smart plug but no flag (AMT always up).
- "ms01-01 only" qualifier removed from all docs; each machine now documented individually with reason for flag or absence.
- New "Custom Commissioning Scripts" section in `maas-lifecycle-waves.md`: documents `maas-00-install-lldpd` (active), `21-fix-lldpctl` (historical/removed), and multi-phase commissioning mechanics.
- `maas-state-machine.md` Commissioning Script Exclusions expanded with pointer to custom scripts doc and `parallel: none` / `parallel: any` semantics.
- Rocky 9 deployment workarounds added to troubleshooting table (grub2-install wrapper from snafu-25; zzz_1_cloud_init_success from snafu-26).
- Memory file updated: ms01-01 and ms01-02 both listed with per-machine reasons for `mgmt_wake_via_plug`.

---

## 2026-04-17 — Remove dead `_skip_on_build_without_inheritance`; two skip features only

- Removed `_skip_on_build_without_inheritance` and its `_skip_on_build_exact` local from `root.hcl` — it had zero usages in any config_params YAML.
- Exclude block simplified: `!_force_delete && (_wave_skip || _skip_on_build)` — two conditions, not three.
- Removed "Terragrunt only allows one exclude block" complaint from all docs/comments — it was a misframing; root.hcl always ORed multiple conditions in one block.
- Two skip features now: wave-level `_skip_on_wave_run` (Python orchestrator) and unit-level `_skip_on_build` (HCL exclude).
- Updated `docs/framework/skip-parameters.md`, `unit_params.md`, `CLAUDE.md`.

---

## 2026-04-17 — Rename `_skip_on_clean` → `_skip_on_wave_run`; skip on build + clean

- Renamed wave-level skip flag from `skip_on_clean`/`_skip_on_clean` to `_skip_on_wave_run` across all YAML configs (10 waves in `waves_ordering.yaml`, 5 per-package yamls).
- Extended semantics: `_skip_on_wave_run` now skips during both `make` (build) and `make clean`; previously only skipped on clean.
- Added missing `_skip_on_wave_run: true` to `hw.proxmox.storage` in `proxmox-pkg.yaml` (was in `waves_ordering.yaml` only).
- `run` script filter restructured: skip filter now runs before `if args.clean` block, covering both paths.
- GUI: renamed all `skip_on_clean` state vars/methods/keys; toggle button color changed from orange to blue; `is_recent` row highlight changed from accent (red) to blue.
- Docs updated: `skip-parameters.md`, `waves.md`, `unit_params.md`, `CLAUDE.md`, `docs/README.md`, `idempotence-and-tech-debt.md`.

---

## 2026-04-16 — Fix: wave row id pre-computed in state, not via Var string concat

- `"wave-row-" + item["name"]` raised TypeError at Reflex compile time (Var concat bug documented in CLAUDE.md).
- Fixed by adding `row_id` as a pre-computed string to `waves_with_visibility` and `waves_folder_rows` dicts.
- Components now use `id=item["row_id"]` (Var subscript) instead of string concatenation.

---

## 2026-04-16 — Waves panel auto-scrolls active wave into view

- Wave rows now have `id="wave-row-<name>"` in both list and folder views.
- `refresh_wave_log_statuses` yields a `scrollIntoView({block:'start'})` call script when `recent_wave_name` changes.
- Active wave scrolls to the top of the table viewport so it's always the first visible row.
- Scroll fires only on `recent_wave_name` change (not every poll), so it doesn't fight manual scrolling.
- Converted `return AppState.refresh_unit_build_statuses` to `yield` to allow the function to yield multiple events.

---

## 2026-04-16 — Tail terminals skip bash --login; watchdog check writes YAML report

- `_start_ttyd` and `open_ssh_terminal` now accept `login=False` to skip `bash --login`, preventing `~/.bash_profile` (and its `clear`) from running on tail open.
- `tail_current_file` and `tail_wave_log` pass `login=False`; no more blink when tailing.
- `wave_tail_cmd` simplified to plain `tail -99f run.log` — the `while/timeout/sleep` restart loop was the second blink source and is unnecessary with ttyd.
- `build-watchdog/check` now writes the YAML report itself (atomic tmp file); watchdog skill just reads it.

---

## 2026-04-16 — Terminal panel shows filename when tailing

- New `shell_label` state var in AppState; shown in terminal panel header when non-empty.
- `tail_current_file` sets label to `"tail: <filename>"` after opening the terminal.
- `tail_wave_log` sets label to `"tail: run.log"` after opening.
- All other terminal-open paths (`open_shell`, `open_ssh_terminal`) clear the label so non-tail terminals still show the CWD path.

---

## 2026-04-16 — Tail uses configured terminal backend; ttyd default + auto-install

- `tail_current_file` and `tail_wave_log` now route through `open_ssh_terminal`, so tail commands use the configured backend (ttyd, native, or embedded) instead of always using the embedded terminal.
- Default `terminal_backend` changed from `"embedded"` to `"ttyd"` when ttyd is available (both at state init and in `on_load` fallback).
- `_try_install_ttyd_background()` added: runs `apt install -y ttyd` (or brew) in a daemon thread at startup if ttyd is not found; re-detects backends on success; requires page reload to activate.

---

## 2026-04-16 — Watchdog Report File

- `/watchdog` skill now writes a structured YAML report to `$_DYNAMIC_DIR/watchdog-report/watchdog_report.yaml` after each run.
- Archives previous report with timestamp prefix before writing the new one.
- `user_input_needed` flag triggers a direct user question if build is unexpectedly stopped, same ERROR repeats 3+ times, or MaaS is unreachable.
- Cron prompt updated with the same report-writing instructions so periodic agents also produce reports.
- Schedule changed from `*/1 * * * *` to `*/2 * * * *` (every 2 minutes).

---

## 2026-04-16 — Curtin debug logging, waves config, README updates

- Added `aa_debug` late_command to both Rocky 9 curtin templates; runs first (alphabetically), writes disk layout + mount state to `/tmp/curtin-late.log` and copies to deployed target for post-deploy diagnosis.
- Made intermediate curtin late_commands non-fatal so `zz_signal_maas` always runs even if `copy_ssh_keys` fails.
- Removed `skip_on_clean: true` from `pxe.maas.seed-server` and `pxe.maas.test-vms` waves.
- Added README content for `scripts/ai-only-scripts/archived/` and `build-watchdog/`.

---

## 2026-04-16 — Fix waves panel sticky header (v3)

- `waves_content` box now uses `display="flex"` + `flex_direction="column"` so `rt-TableRoot` is a true flex item.
- Table roots (`_wave_list_table`, `_wave_folder_table`) use `flex="1"` + `min_height="0"` instead of `height="100%"`; `flex:1` as inline style overrides Radix's class-level `flex-shrink:0`.
- `overflow_y="auto"` on a flex item with flex-determined bounded height = working scroll container for `position:sticky` in `<thead>`.

---

## 2026-04-16 — Fix Auto button TypeError (datetime vs str in max())

- `_read_unit_state()` now converts PyYAML-parsed `datetime.datetime` timestamp fields back to ISO-8601 strings on read, fixing mixed-type `max()` comparisons.
- `flip_auto_select_recent_unit` and `local_state_watcher` max() key lambdas also wrap with `str()` as a guard.

---

## 2026-04-16 — MaaS annihilation grace period + NET-1 skip_ssh_check + sticky header v2

- `maas-lifecycle-gate`: extended 60-second grace period to cover `Deploying` candidates (not just `Commissioning`); the filter now removes machines that transitioned to `Deployed` during the pause.
- `maas-lifecycle-gate`: added `skip_ssh_check` to `_all_machines`; NET-1 loop now rejects machines with `skip_ssh_check: true` so ms01-02 (long GRUB wait) doesn't fail `deployed:post`.
- Waves panel sticky header second fix: replaced `overflow="visible"` approach with `height="100%"` + `overflow_y="auto"` on `rx.table.root`, making `rt-TableRoot` the scroll container that CSS sticky anchors to.

---

## 2026-04-16 — Fix waves panel sticky header

- Wave table header (Wave, Actions, Pre, Run, Test columns) now stays frozen when scrolling.
- Root cause: Radix `Table.Root` renders `div.rt-TableRoot` with `overflow: auto`, intercepting CSS sticky before the real scroll container (`waves_content`) could anchor it.
- Fix: `overflow="visible"` on both `rx.table.root` calls (`_wave_list_table` and `_wave_folder_table`).

---

## 2026-04-16 — Document all background/looping jobs

- New `docs/background-jobs.md`: central index covering all 9 continuously-running processes across maas-pkg, de3-gui-pkg, and scripts; includes inventory table, prose descriptions, shared-infrastructure section.
- New `infra/maas-pkg/_docs/background-processes.md`: per-script detail (state machine position, env vars, stuck detection, recovery, GUI integration via `unit-status/` YAMLs).
- New `infra/de3-gui-pkg/_docs/background-tasks.md`: GUI task detail (Tier 0/0b/1/3 detection, `unit-state.yaml` v2 schema, accelerated polling, global singletons).
- Updated `build-watchdog/run` header to document trigger, env vars, output format, and MaaS state flags.
- Updated `local_state_watcher` docstring to describe the current four-tier architecture instead of the outdated GCS-only description.

---

## 2026-04-16 — Add /annihilate-maas-machine skill + fix stuck-commissioning abort

- New `/annihilate-maas-machine <name>` skill: deletes machine from MaaS (with pre-abort/release), wipes all GCS TF state under `machines/<name>/`, and reports what was deleted — one-command clean slate before re-running waves.
- `wait-for-ready.sh`: abort stuck commissioning regardless of power state (previously only aborted if power was off; GRUB-looping machines are powered on but still stuck).
- Precheck playbook: `_machines_not_in_maas` now checks both hostname AND PXE MAC address so machines that enrolled with random hostnames (e.g. "awake-buck") are not treated as unenrolled.

---

## 2026-04-16 — curtin late_commands ordering, GUI flex fixes, Chrome profile picker

- curtin late_commands execute in alphabetical key order; renamed `maas:` → `zz_signal_maas:` and `poweroff:` → `zzz_poweroff:` so GRUB reinstall runs before MaaS is signaled and machine powers off.
- GUI panel headers added `flex_shrink="0"` to prevent collapsing; `top_right_panel` content area fixed to `flex="1"` + `min_height="0"` (replaces broken `height="100%"` inside flex container).
- Claude Code terminal URL picker filter identified: hides Chrome profiles where `is_using_default_avatar == true AND is_consented_primary_account == true`; `/tmp/add-google-profiles.linux-only.sh` fix script sets `is_using_default_avatar: false` in Local State for hidden profiles.
- Added `reimport-rocky9` ai-only script for re-importing the Rocky 9 boot resource when the MaaS image is stale.
- build-watchdog pgrep extended to also match `run -b` shorthand.

---

## 2026-04-15 — maas-snafu-16: Rocky 9 Deploy Race + Double-Boot Commission Race

- "Failed deployment" race on Rocky 9: curtin signals completion via `node_disable_pxe_url`, but machine then rebooted (MaaS injects `power_state: reboot` cloud-config). Machine PXE-booted back into deploy env while MaaS was still in "Deploying" → 404 for `custom/amd64/ga-24.04/rocky-9` kernel → "Failed deployment".
- Fixed by adding `poweroff: [sh, -c, 'poweroff']` as final `late_command` in `curtin_userdata_rocky9.j2`. Machine now powers off cleanly after signaling completion; cloud-init never runs; MaaS transitions to Deployed cleanly.
- Double-boot commission race diagnosed: MaaS auto-commissions on enrollment; explicit `maas machine commission` from deploying wave races with it → two competing PXE boots → "Failed commissioning". Mitigated by re-enrolling from clean New state; root fix documented in snafu-16 for follow-up.
- ms01-02 successfully deployed as Rocky 9 (system_id: gkhdsy) after re-enrollment from New state with no race condition.

---

## 2026-04-15 — maas-snafu-15: AMT SSL Fix, Deploy IP Conflict, nuc-1 Removal

- AMT "Error determining BMC task queue" had two causes: (1) management subnet 10.0.11.0/24 missing from MaaS → `UnroutablePowerWorkflowException`; (2) rack controller's rackd/maas-agent spawned wsman without `OPENSSL_CONF` (pebble doesn't propagate env to children) → OpenSSL 3.0 blocked legacy TLS renegotiation.
- Fixed by patching `/etc/ssl/openssl.cnf` system-wide on BOTH region AND rack (reliable; all processes read it regardless of env), and adding management subnet to `managed_networks` config.
- `fix-maas-amt-ssl.yaml` now included in rack configure playbook (was missing); MaaS API wait made conditional (skips on rack — no local API).
- `trigger-deploy.sh` now queries BMC power state before deploy: if machine is ON (old OS holding provisioning IP), powers it off and waits 15s before issuing deploy (fixes ARP conflict rejection).
- nuc-1 permanently removed: MaaS deleted, GCS state wiped, all unit files + config entries purged.

---

## 2026-04-15 — maas-snafu-14: Webhook BMC Task Queue Failure (localhost URL)

- Root cause: webhook `power_query_uri` used `localhost:7050` → MaaS extracted `127.0.0.1` → not on any managed subnet → `UnroutablePowerWorkflowException` on every power operation.
- Bug was masked by old `trigger-commission.sh` power_type=manual override (snafu-13); became visible after that workaround was removed.
- Fixed all machine `terragrunt.hcl` files: `_proxy = "http://localhost:7050"` → `_proxy = "http://${maas_host}:7050"` (both top-level and deploying).
- Fixed `smart-plug-proxy.py`: bind address changed from `127.0.0.1` to `0.0.0.0` (env var `SMART_PLUG_HOST` to override); deployed immediately via ai-only-script without waiting for full MaaS re-run.
- nuc-1 annihilated and build restarted; new physical issue discovered: nuc-1 switch port DOWN after plug cycle — machine not auto-starting, likely BIOS "Power on after AC loss" not functioning.

---

## 2026-04-15 — maas-snafu-12: AMT Power State Fixes

- Fixed PowerState=10 on S5 machines: AMT accepts hard-reset command with rc=0 but ignores it for powered-off machines — script now queries `CIM_AssociatedPowerManagementService` first and uses PowerState=2 (power on) for non-S0 states.
- Added 30s timeout to all wsman `subprocess.run()` calls — previously wsman could hang indefinitely (reproduced: 10+ min hang on ms01-02 with wrong password).
- Fixed inverted `invoke()` ReturnValue check: `not in` → `in` — success response `<ReturnValue>0</ReturnValue>` was treated as failure, printing spurious "ChangeBootOrder failed" warnings.
- ms01-01 and ms01-03 now enroll in MaaS correctly; ms01-02 blocked by wrong AMT password (user action required — see snafu-12 plan).
- Confirmed ms01-02 diagnosis: each ms01 has an independently configured AMT password; ms01-02's SOPS entry did not match what was in firmware (HTTP 401); ms01-01/ms01-03 authenticated independently (HTTP 500). Do not assume shared passwords.

---

## 2026-04-15 — GUI: Fix floating panel drag — switch to document mousemove/mouseup

- `setPointerCapture` was silently failing in the Reflex/Radix/React 18 environment — `pointermove` never fired on the header element, so drag never worked.
- All five init functions (`init_float_file_viewer`, `init_float_terminal`, `init_float_object_viewer`, `init_popup_drag`, `init_float_refactor`) switched from pointer-capture drag to `mousedown` + `document.addEventListener('mousemove'/'mouseup', ...)`.
- Document-level `mousemove`/`mouseup` fire unconditionally regardless of Radix's event delegation, making drag reliable.
- `e.button !== 0` guard prevents right/middle-click drag; `e.preventDefault()` prevents text selection.

---

## 2026-04-15 — GUI: Fix floating panel drag + right-side default positioning

- Replaced `requestAnimationFrame` with `setTimeout(tryInit, 20)` retry loop in all five panel init functions — RAF fires before React commits DOM, so `getElementById` returned null and drag listeners were never installed.
- All panels (file viewer, terminal, object viewer, refactor, unit popup) now position at the right edge of `#left-column` by default, filling available viewport space instead of centring.
- Removed `transform: translate(-50%, -50%)` from refactor panel's React style dict — React re-applied it on every re-render, fighting JS-set `left/top`; replaced with CSS vars `var(--refactor-x/y)`.
- `init_float_refactor` now tracks position in `--refactor-x/y` CSS vars (was missing); `init_popup_drag` has fallback path for floating-panels mode when `#top-right-panel` doesn't exist.

---

## 2026-04-15 — maas-snafu-11: AMT + Smart Plug Power Management Fix

- Added missing `smart_plug_host`/`smart_plug_type` for ms01-02 (`192.168.2.105 tapo`) and ms01-03 (`192.168.2.210 tapo`) — plug fallback was silently skipped, causing enrollment poll to time out.
- Rewrote `maas-machines-precheck` AMT power cycle: try wsman first → if fail + `mgmt_wake_via_plug`, bounce plug + wait for AMT + retry wsman → last resort raw plug cycle.
- Corrects prior behaviour where plug was bounced pre-emptively even when AMT was already reachable.
- Archived snafu-11 plan.

---

## 2026-04-15 — GUI: Floating panels mode + appearance accordion

- New floating panels layout mode: infra tree stays fixed, file viewer/terminal/object viewer become draggable/resizable windows positioned near viewport centre.
- Three new floating panel components (`float_file_viewer_panel`, `float_terminal_panel`, `float_object_viewer_panel`) wrapping existing panel functions; `Panels ▾` menu in toolbar shows/hides each one.
- Panel positions saved to `state/current.yaml` on close; restored via JS on next load.
- Appearance menu rewritten as 10 collapsible accordion sections (was flat/scrollable list); "Floating panels mode" checkbox in Layout section.
- 26 new state vars and ~20 new event handlers; all persisted.

---

## 2026-04-15 — GUI: Node detail popup snaps to cover file viewer panel on open

- Popup now automatically positions and sizes itself over `#top-right-panel` (the file viewer) when first opened.
- Uses `getBoundingClientRect()` inside `requestAnimationFrame`; guarded by `_positionSet` on the DOM element so re-snap only happens on fresh open, not on every node click.
- Removed `max_width` cap (was 750px); raised `max_height` to `95vh` so wide panels aren't clipped.

---

## 2026-04-15 — GUI: Fix unit popup not updating on node click; close unchecks toggle

- `click_node` is a generator that never calls `select_node` — popup update hook was in the wrong method; moved to `click_node` directly.
- Popup content now refreshes every time a tree node is clicked while "Show unit popup on select" checkbox is ON.
- Closing popup with ✕ now unchecks the Appearance menu checkbox and persists the state.

---

## 2026-04-15 — MaaS lifecycle gate: comprehensive pre/post checks for all lifecycle waves

- New shared `maas-lifecycle-gate/playbook.yaml` replaces `maas-lifecycle-sanity` as the pre-check for commissioning→deployed waves and adds POST gates to all six `maas.lifecycle.*` waves (previously 0 had POST gates).
- Gate checks: TF-1 (no placeholder system_id), TF-2 (TF matches MaaS), MAAS-1 (enrolled), MAAS-2 (power_type match), MAAS-3 (hardware inventory), MAAS-4 (allowed status set), MAAS-5 (not failed/broken), MAAS-6 (exact status), BMC-on (PRE only), NET-1 (SSH open, deployed:post only).
- 11 wrapper run scripts (`maas-lifecycle-gate-<wave>-<mode>/run`) set `_MAAS_GATE_WAVE` + `_MAAS_GATE_MODE` and exec the shared runner; `maas-pkg.yaml` wired with `pre_ansible_playbook` + `test_ansible_playbook` for every lifecycle wave.
- Annihilation logic (stuck transitional + BMC off, OR power_type mismatch) preserved in all PRE gates; PRE mode queries ALL AMT/smart_plug machines so `deploying:pre` can verify Allocated machines are powered on.
- Root cause of maas-snafu-10: sanity check exited success after annihilation → commissioning apply ran against placeholder TF state → silent skip → placeholder propagated downstream; POST gate on `new` now catches this immediately.

---

## 2026-04-15 — GUI: Unit detail popup driven by Appearance checkbox (not hover timer)

- Replaced 5-second hover timer with a checkbox "Show unit popup on select" in the Appearance menu under a new "Unit detail popup" section.
- Popup now opens when a node is clicked AND the checkbox is ON; updates content automatically on every subsequent node selection while open.
- Removed `start_hover_timer`, `cancel_hover_timer`, `on_hover_show_trigger`, `hover_pending_path`, `on_mouse_enter/leave` from tree rows, and the `hover-show-trigger` hidden div.
- Added `_load_hover_popup_for_path` helper, `toggle/flip_show_unit_popup` handlers, `init_popup_drag` (replaces `position_hover_popup`).
- `select_node` now calls `_load_hover_popup_for_path` whenever `hover_popup_open` is True so popup content tracks the active selection.
- `show_unit_popup` checkbox state is persisted in config.

---

## 2026-04-14 — GUI: Hover popup for node details

- After resting the cursor on a tree node for 5 seconds, a floating popup appears showing unit-state.yaml data (status, timestamps, exit codes) and the node's full config_params.
- Popup is draggable by its header (pointer-capture drag, no jitter) and resizable via the native CSS resize handle.
- Position is stored in CSS custom properties (`--popup-x/y`) so React re-renders never reset the drag position.
- Hover timer (5s `setTimeout`) is wired via the existing hidden-trigger-div pattern: JS stores cursor coords in `window._hoverPopupData` then clicks `hover-show-trigger` to invoke the Reflex handler.
- Mouse position tracked globally via `document.mousemove` listener installed in `install_resizer` at page load.
- Cancellation guard: if mouse leaves before 5s fires, `hover_pending_path` is cleared and `on_hover_show_trigger` no-ops.

---

## 2026-04-14 — Fix sanity check gaps: power_type mismatch detection + proxmox/manual safety

- **Gap 4 (critical)**: `maas-lifecycle-sanity` now captures `power_type` from MaaS in `_maas_state` and detects mismatches. Any enrolled machine with wrong power driver is annihilated before the wave runs — confirmed fix for all four machines stuck Commissioning with `power_type: manual` when config requires `amt`/`smart_plug`.
- **Gap 1**: `_to_annihilate` block now skips the BMC-state path for `proxmox` and `manual` power types; previously they fell through to `power_state=unknown` and were incorrectly annihilated.
- **Gap 2**: New `Warn about machines in Broken state` debug task emits operator instructions for machines needing `maas machine mark-fixed`.
- **Gap 3**: README execution flow diagram corrected — plug bounce runs before BMC queries, not after.
- Annihilation log messages now show `item.reason` (either `power_type mismatch: MaaS=X config=Y` or `stuck: STATUS but BMC=STATE`).
- `maas-lifecycle-sanity.md` Known Bugs cleared; Annihilation Decision Table updated with power_type mismatch row.

---

## 2026-04-14 — GUI: Auto-select recent unit — button move and selection fixes

- "Auto-select recent unit" moved from Appearance menu to a compact "Auto" toggle button in the infra panel toolbar, next to Merge/Unmerge.
- On enable, immediately selects the most-recently-applied unit from `unit-state.yaml`, expands its ancestors, and switches to tree view.
- Root cause of non-selection: `click_node` is a Reflex generator event (uses `yield`); calling `select_node` as a plain Python method skipped the two-phase flush that highlights the tree row.
- Fix: return `AppState.click_node(best)` as an event spec so Reflex dispatches it after the ancestor-expansion delta is sent to the frontend.
- Added `id="tree-selected-node"` to the selected tree row; `requestAnimationFrame` scrolls it to the centre of the panel with no artificial delay.

---

## 2026-04-14 — MaaS lifecycle sanity check (physical reality verification)

- New `pre_ansible_playbook: maas/maas-lifecycle-sanity` added to all five lifecycle waves (commissioning → ready → allocated → deploying → deployed).
- New playbook checks all `maas.lifecycle.new` physical machines against live BMC power state before each wave runs.
- Detects stuck machines (Commissioning/Testing/Deploying in MaaS but BMC is off/unreachable) and annihilates them: `maas machine delete` + `gsutil rm` all descendant GCS Terraform state.
- New `amt-query.py` helper: fast TCP check on port 16993, then `wsman enumerate CIM_AssociatedPowerManagementService` with 20s timeout; returns JSON power state.
- Smart-plug machines checked via webhook proxy at `http://127.0.0.1:7050/power/status`; Proxmox VMs skipped (deferred).
- `_MAAS_ANNIHILATE_CONFIRM=true` env var enables interactive prompt before annihilation (defaults silent).

---

## 2026-04-14 — GUI: Auto-select recent unit

- New "Folder view behaviour" section in Appearance menu with "Auto-select recent unit" checkbox.
- When enabled, the tree auto-selects and expands to the unit whose apply most recently completed, driven by `local_state_watcher`.
- Three hook points in `local_state_watcher`: Tier 1 (GCS tfstate change), Tier 3 (exit-code files), and auto-refresh (unit-state.yaml mtime change only, not interval).
- `_apply_auto_select` helper expands all ancestor paths for visibility, loads HCL in both separated and merged tree modes.
- Toggle state persisted in `_save_current_config` / restored in `on_load`; defaults to `False`.

---

## 2026-04-14 — /ship archives ai-log files older than 3 days

- `/ship` Step 5 now moves `docs/ai-log/*.md` files whose filename timestamp is >3 days old into `docs/ai-log/archived/` via `git mv`.
- Age determined from the `YYYYMMDDHHMMSS` prefix in the filename, not filesystem mtime.
- `docs/ai-log/archived/.gitkeep` created; 62 existing old logs bulk-archived on first run.

---

## 2026-04-14 — /doit archives completed plans to docs/ai-plans/archived/

- Completed plans are moved to `docs/ai-plans/archived/<timestamp>-<name>.md` after execution.
- Archive step runs before `/ship` and is staged atomically in the same commit as the work.
- `docs/ai-plans/archived/.gitkeep` created so git tracks the directory before first archive.

---

## 2026-04-14 — /doit resume mode via plan name arg

- `/doit <plan-name>` now skips straight to execution if `docs/ai-plans/<plan-name>.md` exists.
- Detection heuristic: no spaces in arg = try as filename stem; falls through to task-description mode if file not found.
- Step 7 now tells user to run `/doit <name>` (not just `/clear`) to resume after context clear.

---

## 2026-04-14 — Rename /plan skill to /doit

- `/plan` command renamed to `/doit` to avoid collision with the built-in Claude Code Plan agent.
- `CLAUDE.md` Planning convention updated to reference `/doit` and describe full workflow.
- `docs/ai-plans/README.md` gained a note that `/ship` is called at the end of execution.

---

## 2026-04-14 — pxe.maas.configure-plain-hosts wave + Proxmox VE 9 + OVS script fix

- New wave `pxe.maas.configure-plain-hosts` (between `maas.lifecycle.deployed` and `pxe.maas.machine-entries`) automates OVS bridge configuration on plain managed hosts post-deploy; `skip_on_clean: true` since OVS state lives on the host and is wiped by MaaS re-deploy.
- New tg-script `infra/maas-pkg/_tg_scripts/maas/configure-plain-hosts/` reads declarative `bridges: technology: ovs` from pwy-home-lab-pkg.yaml, discovers machines dynamically (no hardcoded names), SSHes via `provisioning_ip` + MaaS jump box; distro-aware: netplan for Ubuntu, nmcli for Rocky/RHEL.
- Rocky preseed deploy tasks added to both configure-region and configure-server `import-maas-images.yaml` paths; Curtin userdata template `curtin_userdata_rocky9.j2` deployed automatically when `rocky_images` config is present.
- Updated all Proxmox documentation and playbook comments from VE 8 → VE 9 (Debian 13 trixie upgrade).
- `configure-plain-host-ovs` ai-only script fixed to prefer `provisioning_ip` + MaaS jump box instead of always using `cloud_public_ip` — fixes chicken-and-egg problem where the script ran before OVS was configured.
- Config additions: `amt_port: 16993` (ms01-01, ms01-03), `provisioning_ip: 10.0.12.239` (ms01-02), `deploy_osystem: ubuntu` (ms01-03); `maas-machines.md` table expanded with NIC/switch/port columns.
- Added `Planning (ai-plans)` convention to CLAUDE.md.

---

## 2026-04-14 — GUI log timestamps

- Added `_gui_log(msg)` helper to `homelab_gui.py` that prepends `[HH:MM:SS]` to every log line.
- Replaced all ~34 `print(f"[tag] ...")` calls with `_gui_log(...)` across all component tags (`[homelab_gui]`, `[inventory_refresh]`, `[on_load]`, `[local-state-watcher]`, `[file-watcher]`, etc.).
- `flush=True` preserved in the helper for immediate output even when stdout is buffered.

---

## 2026-04-14 — Rocky Linux 9 MaaS import pipeline + ms01-02 Rocky+OVS + maas-machines.md

- Automated Rocky Linux 9 GenericCloud → MaaS boot resource import: new `import-rocky-image.yaml` (both configure-server/region paths) mirrors the Debian pipeline — downloads qcow2, customizes via chroot (grub2-efi, efibootmgr, netplan from EPEL 9, grub2-install EFI, /curtin marker), imports as ddgz. Hooked into `import-maas-images.yaml` replacing the placeholder debug message. Rocky 9 chosen over 10: EPEL 9 is mature (netplan available); EPEL 10 still in beta.
- Restructured `rocky_images` config in pwy-home-lab-pkg.yaml to `name/title/architecture/url` format (matching `debian_images`). Only `custom/rocky-9` configured.
- ms01-02 now deploys Rocky Linux 9 (`deploy_distro: rocky-9`, `deploy_osystem: custom`, `cloud_init_user: rocky`) with `bridges:` OVS config for sfpplus3 10G NIC at 10.0.10.117/24 — run `configure-plain-host-ovs` post-deploy.
- Created `infra/pwy-home-lab-pkg/_docs/maas-machines.md` — full machine reference with OS version, network stack, IP, power, 10G switch port, build notes, post-deploy OVS steps, and custom boot resource table.

---

## 2026-04-14 — OVS: Debian distro fix, configure-plain-host-ovs script

- Fixed Debian gap in `_configure-ovs-bridge.yaml` — Proxmox VE runs Debian, not Ubuntu; the `ansible_distribution` guard would have hit `fail` on all real Proxmox nodes. Merged Debian+Ubuntu into one `apt` task.
- Created `scripts/ai-only-scripts/configure-plain-host-ovs/` for plain (non-Proxmox) hosts: reads `bridges: technology: ovs` from pwy-home-lab-pkg.yaml, installs OVS per distro (apt on Ubuntu/Debian, EPEL+dnf on Rocky, CRB+EPEL+dnf on RHEL), creates bridge via `ovs-vsctl`, persists IP via netplan (Ubuntu/Debian) or nmcli ovs connections (Rocky/RHEL).
- Confirmed: neither ms01-02 nor ms01-03 uses Rocky — both are `deploy_distro: noble`. Rocky via MaaS requires a separate packer → MaaS import pipeline (not yet automated).

---

## 2026-04-14 — Networking: OVS support, ms01-03, MikroTik browser URL, skip flags

- OVS package install in `_configure-ovs-bridge.yaml` is now fully automated and cross-distro: Ubuntu (`apt`), Rocky Linux (`epel-release` then `dnf`), RHEL (CRB repo + EPEL via direct RPM URL + `dnf`). Uses `ansible_distribution` for explicit branching; fails clearly on unsupported distros.
- Fixed bug: Step 5 of `configure-bridges.yaml` (host IP assignment) was running against OVS bridges. OVS host IPs are set via `OVSIntPort` inside `_configure-ovs-bridge.yaml`; the Linux-bridge pvesh path is now skipped for `technology: ovs`.
- `ms01-02` and `ms01-03` `_skip_on_build` set to `false`. Both are plain managed Ubuntu hosts — not Proxmox nodes; no pve-nodes entries needed. OVS networking for them (if ever desired) requires a separate non-Proxmox playbook using `ovs-vsctl` + netplan, not `pvesh`.
- Added `_browser_url: "http://10.0.11.5"` to MikroTik CRS317 units in both mikrotik-pkg and pwy-home-lab-pkg configs.
- Corrected stale port mapping in MikroTik `_unit_purpose`: pve-1→sfpplus1, ms01-01→sfpplus2, ms01-02→sfpplus3, ms01-03→sfpplus4.
- Added commented OVS bridge examples to pve-1 and ms01-01 showing how to use the 10G NICs once NIC names are discovered.

---

## 2026-04-14 — Fix: Refactor panel ForeachVarError crashing GUI on startup

- GUI failed to start after the Refactor panel was introduced: `rx.foreach` over `dict.get()` on a `dict = {}` state var raises `ForeachVarError` at compile time.
- Added typed `refactor_preview_external_deps: list[dict] = []` state var; `run_refactor_preview` now syncs it from the parsed JSON.
- Replaced `rx.foreach(refactor_preview_result.get("units_found_list", []))` with a plain count display (`units_found_list` key never existed in the JSON report).
- Replaced `rx.foreach(refactor_preview_result.get("external_deps", []))` with `rx.foreach(refactor_preview_external_deps)` — typed var that Reflex can iterate.

---

## 2026-04-14 — manage-unit CLI + GUI Refactor panel

- New `framework/manage-unit/run` CLI moves/copies Terragrunt unit trees, keeping filesystem, config_params YAML, SOPS secrets, and GCS state in sync. Supports `--dry-run`, `--json-report`, `--skip-state`, `--skip-secrets`. Cross-package moves supported.
- GUI: replaced old clipboard copy/paste with a **Refactor** panel (third mode in the Object Viewer dropdown). Right-click any node → Edit → "Refactor (move / copy)…" to open it.
- Removed ~260 lines of copy/paste state vars, event handlers, and dialogs from `homelab_gui.py`.
- `ruamel.yaml` configured with `ignore_aliases=True` and `width=4096` to prevent anchor injection and line-rewrapping on YAML round-trips.

## 2026-04-14 — Proxmox bridge config refactored to pve_bridges list schema

- `generate_ansible_inventory.py` now emits `pve_bridges` (list of bridge dicts) instead of flat `pve_bridge_technology`/`pve_vlan_bridge`/etc. Backward-compat synthesis from legacy flat fields.
- Both configure playbooks now call `configure-bridges.yaml` (dispatcher) instead of four flat task includes.
- New private tasks: `_configure-bridge-host-ip.yaml` (IP/gateway), `_configure-explicit-bridge.yaml` (named NIC), `_configure-ovs-bridge.yaml` (OVS).
- `configure-vlan-aware-bridge.yaml` now purely enables VLAN filtering; gateway config removed to `_configure-bridge-host-ip.yaml`.
- `verify-bridge-config.yaml` updated to iterate `pve_bridges` and verify each bridge by technology.

---

## 2026-04-13 — Document /ship skill in claude-skills.md

- `docs/claude-skills.md` now has a `/ship` section alongside `/run-wave`
- `/ship` was defined in `.claude/commands/ship.md` but missing from the docs index
- Section covers the full 6-step algorithm: diff review, README updates, ai-log, ai-log-summary, commit, push

---

## 2026-04-07 — Repo flatten: eliminate deploy/ wrapper and symlink machinery

Eliminated the `deploy/tasks/phase-0/terragrunt/lab_stack/` wrapper (4-level-deep path
with no value) by moving all contents to the repo root. Replaced gitignored
`k8s-recipes/config` and `k8s-recipes/utilities` symlinks with real tracked `config/`
and `utilities/` directories at repo root.

- **`set_env.sh`** rewritten from 117 → 29 lines: removed `ensure_link()`, symlink
  creation, `_app_task_directories.sh` loading; direct paths to real directories.
- **`scripts/lib/lab_stack_env.sh`** deleted — merged into `set_env.sh`; self-location
  trick was redundant after flatten (`_STACK_ROOT == _GIT_ROOT`).
- **Outer orchestration removed**: `deploy/run`, `deploy/Makefile`,
  `deploy/_app_task_directories.sh`, `deploy/tasks/phase-0/local-dev-setup/` deleted.
- **`_framework-pkg/_setup/run`** enhanced with `_setup_kubectl()`, `_setup_helm()`,
  `_setup_dev_workstation()`, `_setup_ssh_config()` — code from the old
  `APP_TASK_DIRECTORIES` setup package merged here.
- **Human-only scripts** (seed-accounts, gpg, sops, kubeconfig, converters) moved to
  `scripts/human-only-scripts/`.
- **`generate-ansible-inventory`** consolidated under `framework/`.
- **`.gitignore`** promoted terragrunt cache patterns (`.terragrunt-cache/`, `.terraform/`,
  `backend.tf`, `provider.tf`, `terraform.tfstate`) from the old nested `.gitignore`.

---

## 2026-04-07 — Self-contained package refactor: infra/\<pkg\>/ structure

Full architectural transformation moving from the `infra/cat-hmc/` catalog structure
to self-contained `infra/<pkg>/` packages. Each package owns its entire vertical slice:

```
infra/<pkg>/
  _stack/       — terragrunt units (provider/path/leaf-unit)
  _modules/     — Terraform modules
  _providers/   — provider connection templates
  _tg_scripts/  — Terragrunt hook scripts (before_hook/after_hook/local-exec)
  _wave_scripts/ — wave test/precheck playbooks
  _config/      — per-package YAML and secrets
  _setup/       — OS-level tool installation
  docs/         — package documentation
```

`root.hcl` rewritten to derive `p_package` and `p_tf_provider` from the unit path
structure (`infra/<pkg>/_stack/<provider>/...`). No `deploy/` references. All 63 units
pass `terragrunt init`. Seven issues fixed during migration: var substitution,
ancestor params, cross-package dependencies, module resolution, GCP kubeconfig.

---

## 2026-04-07 — Remove dead code: pkg_env.sh, k8s-utils, terraform-utils, unused functions

Series of cleanup commits after flatten:

- **`pkg_env.sh`** (4 files): deleted from all packages. `_PKG_TG_SCRIPTS_DIR` was never
  consumed; `_MAAS_TASKS_DIR` replaced with direct `_INFRA_DIR`-relative paths in 7 playbooks.
  Source lines removed from 12 run scripts.
- **`k8s-utils.sh`**: deleted — k8s not in active use (will be replaced by Ansible).
  `KUBECONFIG` and `_HELM_CHARTS_DIR` removed from `set_env.sh`.
- **`terraform-utils.sh`**: deleted — stack uses Terragrunt exclusively; no run script
  called any `_tf_*` function.
- **`terragrunt-utils.sh`**: deleted — all functions (`tg_build`, `tg_clean_all`,
  `tg_destroy_current_module`, `_tg_graph` and helpers) had no external callers;
  `run` script handles Terragrunt operations directly.
- **`env-yaml-conversion.sh`**: deleted — `converters/env-yaml.sh` has its own inline
  copy; nothing sourced the utilities version.
- Dead functions removed from remaining files: `_framework_run_scripts`, `_update_pip`,
  `_test_env_to_yaml`.
- Fixed 4 stale `deploy/` paths in ai-only-scripts left over from flatten.

---

## 2026-04-07 — Docs, CLAUDE.md, clean-all GKE purge, ms01 prep

- **CLAUDE.md** reduced from ~717 to ~130 lines: extracted Known Pitfalls →
  `docs/known-pitfalls.md`, merged Packer details into `infra/image-maker-pkg/docs/`.
- **`docs/`** restructured from flat `docs/topics/` into package-aligned subdirectories
  (`maas-pkg/`, `proxmox-pkg/`, etc.) + `framework/`. Machine-onboarding and image-maker
  docs merged.
- **`make clean-all` GKE purge**: Added GKE pre-purge stage (clusters were orphaned when
  Terraform destroy failed on non-empty clusters). `gcloud container clusters delete`
  called before Terraform destroy.
- **ms01-02/03 config**: Added missing `role_proxmox_server`, `cloud_init_ssh_keys`,
  `cloud_init_user` fields. Fixed MS-01 onboarding README with correct switch names and
  cabling profile names.

---

## 2026-04-07 — Move hardcoded IPs and ports to package variables

Audited all package YAML files and replaced ~20 hardcoded static IPs and ports
with `vars:` declarations and `${varname}` / `${pkg-name.varname}` references.

- **`maas-pkg`**: added `provisioning_rack_ip: 10.0.12.2` and `maas_api_port: 5240`.
  Replaced in `_provider_api_url`, `_browser_url`, ProxyCommand, configure-server fields.
- **`proxmox-pkg`**: added `pve_1_ip` (10.0.10.115), `pve_2_ip` (10.0.10.200),
  `proxmox_api_port` (8006), `cloud_public_gateway` (10.0.10.1). Cross-package
  `${maas-pkg.maas_server}` and `${maas-pkg.provisioning_rack_ip}` references.
- **`image-maker-pkg`**: added `kairos_version: v3.7.2`.
- Per-machine device IPs (AMT, cloud_public_ip, smart_plug_host) intentionally left as literals.

---

## 2026-04-06 — Proxmox wave separation: install / configure / storage

Split monolithic `hypervisor.proxmox` into three waves with clear package boundaries:
- `hypervisor.proxmox.install` — MaaS deploys OS; Proxmox packages installed; vmbr0 created
- `hypervisor.proxmox.configure` — Proxmox configured (API tokens, storage, networking)
- `hypervisor.proxmox.storage` — ISOs and snippets provisioned

Clarified MaaS/Proxmox boundary: MaaS ends at Deployed state with SSH access; Proxmox
covers PVE install through ISOs/snippets. Added ms01-01 ISO/snippet units to storage wave.

---

## 2026-04-06 — Fix config_base vars deprecation + UniFi tagged VLAN validation

Two bugs introduced with the package variable interpolation feature:

- **`config_base/tasks/main.yaml`**: `vars.keys()`/`vars[k]` triggered Ansible "internal
  vars dictionary deprecated" warning. Hyphenated keys (`terragrunt_lab_stack_azure-pkg`)
  caused Ansible to reject `set_fact` with those names. Fix: replaced `vars.keys()` with
  `q('varnames',...)` + `lookup('vars', k)`; inlined `${}` resolution inside `_tg_providers`
  via JSON round-trip.
- **`validate-unifi-config.py`**: Tagged VLAN checks always reported `actual: '[]'` because
  UniFi 10.x stores tagged VLANs as an exclusion list (`excluded_networkconf_ids`). Fixed to
  compute `tagged = all_excludable − excluded − native` when `tagged_vlan_mgmt == "custom"`.
- Fixed `tg-scripts/_framework-pkg/local/update-ssh-config/` path (`p_package` defaults to
  `"_framework-pkg"`, not `"default"`).

`network-validate-config` wave: All 87 checks PASSED.

---

## 2026-04-06 — UniFi port profile fixes + network README corrections

- **`pxe_host_trunk` profile**: added `management` and `storage` to `tagged_vlans`
  (native=VLAN12, tagged=VLAN10/11/14). Matches README and gives Proxmox all VLANs.
- **`README.network-planning.md`**: corrected Physical Servers section, Intel NUC section,
  Port Profiles table; added `management_only` and `provisioning_only` rows; added AMT
  ports and NUC port 12 to switch tables.

---

## 2026-04-06 — Fix Ansible vars deprecation (29 playbooks)

All playbooks emitted `[DEPRECATION WARNING]: The internal "vars" dictionary is deprecated`.

- **Pattern A** (28 files): `vars: local_roles_dir: ...` + `roles: [{role: "{{ local_roles_dir }}/config_base"}]`.
  Fix: replaced with `ansible.builtin.include_role` using `lookup('env', '_ANSIBLE_ROLES_DIR')` inline.
- **Pattern B** (1 file, `mesh-central/update`): hyphenated key in `vars` check.
  Fix: use `_tg_providers_secrets.maas is defined` instead.

---

## 2026-04-06 — Package variable interpolation (`${varname}` / `${pkg.varname}`)

Implemented `vars:` section in package YAMLs supporting local and cross-package string interpolation.

- **`merge-stack-config.py`**: two-pass `merge_packages()` — Pass 1 collects `vars:` sections;
  Pass 2 calls `resolve_vars()` before deep-merge. Unrecognised `${...}` tokens passed through.
- **`config_base/tasks/main.yaml`**: added `_pkg_vars` collection task and inline `${}`
  resolution via JSON round-trip.
- **`maas-pkg`**: first real use — `${maas_server}` in `_provider_api_url`, `maas_host`, `maas_server_ip`.

---

## 2026-04-06 — network.unifi.validate-config wave

Added pure-test wave `network.unifi.validate-config` after `network.unifi`. Python script
authenticates to UniFi controller and checks VLANs (name, purpose, subnet, DHCP), port
profiles (native/tagged VLANs resolved via `vlan_id → _id`), and device ports (name,
profile, connected MAC). 87 checks across 3 categories.

---

## 2026-04-06 — local.updates wave: dynamic SSH config

Added `local.updates` as the final pipeline wave. Null unit invokes
`tg-scripts/_framework-pkg/local/update-ssh-config/run --build`, which regenerates the
Ansible inventory then writes SSH Host stanzas to `~/.ssh/conf.d/dynamic_ssh_config`.
Trigger is a hash of config YAMLs + run script.

---

## 2026-04-06 — SSH tests for VM waves

All four Proxmox VM waves (`vms.proxmox.from-web.ubuntu`, `vms.proxmox.from-web.rocky`, `vms.proxmox.from-packer`,
`vms.proxmox.from-kairos`) switched from `test_action: reapply` to `test_ansible_playbook`.
Test playbooks use `wait_for_connection` (180s / 300s Kairos) and report distro/IP.
Kairos is a soft warning (OS enrollment from ISO may still be running).

---

## 2026-04-06 — README and wave description refresh

All 18 wave `description:` fields rewritten with detailed multi-line content. Six README
files updated: root README, `README.waves.md`, proxmox-pkg wave-scripts, proxmox
tg-scripts READMEs (Debian 12 → 13), configure-server README (task table expanded from
4 to 9 entries), `README.maas-provisioned-proxmox-host-setup.md`.

---

## 2026-04-04 — Package system: core architecture refactor

Large multi-session refactor introducing per-package YAML files, capability constraints,
provider aggregation, and module/template consolidation.

**Config and secrets split** (20260404132550, 20260404140000):
- Monolithic config split into 8 per-package YAMLs with `_version`,
  `_provides_capability`/`_requires_capability` (semver lists), `_kind`, `_provisioner`.
- Monolithic `terragrunt_lab_stack_secrets.sops.yaml` split into per-package secrets files.
  Auto-discovered by `merge-stack-config.py`.

**Provider/module/template consolidation** (20260404150059, 20260404170000, 20260404174000):
- Terraform modules moved to canonical provider packages (aws-pkg, azure-pkg, gcp-pkg,
  proxmox-pkg, unifi-pkg). `demo-buckets-example-pkg` becomes a pure config-coordinator.
- Provider templates moved from `_providers/_framework-pkg/` to per-provider package dirs
  with 3-tier lookup: package-specific → provider-pkg → _framework-pkg fallback.
- `gke-pkg` dissolved — modules merged into gcp-pkg.

**Routing simplification** (20260404172930):
- Eliminated `_scripts_package` field. Each package owns null module symlink directories.
  Single `_package` field controls modules, templates, and scripts routing.

**Dynamic provider aggregation** (20260404233500):
- `config_base` role: added `_tg_providers` and `_tg_providers_secrets` aggregation.
  All 17 Ansible files now use dynamic discovery — hardcoded package variable names removed.
  New packages auto-discovered.

**Wave/naming cleanup** (20260404180000, 20260404203036):
- Dropped `.pwy-homelab` site suffix from 10+ wave names.
- Removed empty `util.noop` wave.
- `cloud.k8s.gcp.us-central1` → `cloud.k8s` (provider/region are config, not wave name).
- `cloud.storage.multi` → `cloud.storage`.

**`_extra_providers`** (20260404112034):
- Units can declare secondary provider plugins: `_extra_providers: ["null"]`.
- `root.hcl` injects entry templates into `required_providers {}`. YAML reserved words quoted.
- GKE kubeconfig unit uses this to move alongside cluster unit.

---

## 2026-04-01 — SSH ProxyCommand fix for VLAN 12 jump hosts + secrets update

- **`-J` → explicit `ProxyCommand`**: `-J ubuntu@host` does not propagate
  `StrictHostKeyChecking=no`/`UserKnownHostsFile=/dev/null` to the final hop,
  causing `kex_exchange_identification: Connection closed`. Fixed for ms01-01 and pxe-test-vm-1.
- **Secrets updated**: MaaS API key re-synced; ms01-01 Proxmox token secret updated.

---

## 2026-04-01 — Fix Proxmox apt-installed vmbr0 DHCP → static conversion

- **Root cause**: `configure-linux-bridge.yaml` detected vmbr0 exists (pvesh rc=0) and
  SKIPPED creation — leaving vmbr0 as DHCP. MaaS DHCP leases expire in 600s → ms01-01
  lost IP, became unreachable.
- **Fix 1**: Added DHCP bridge detection: if vmbr0 exists but has no `cidr`, convert to
  static using `ansible_host`/24 and current gateway.
- **Fix 2**: Skip DHCP NIC fallback when `vmbr0 inet static` already present in
  `/etc/network/interfaces`.
- **Recovery**: ms01-01 recovered via MaaS rescue mode (disk mount, rewrote interfaces).

---

## 2026-04-01 — MaaS release automation, pxe-test-vm-1 lifecycle fix, docs refresh

- **MaaS release on VM destroy**: `null_resource.maas_release_on_destroy` with destroy
  provisioner SSHes to MaaS server, releases machine to Ready for next deploy.
- **Auto-import redeploy detection**: detects when `maas_machine.this` has valid system_id
  but is in non-Deployed state — removes `maas_instance.this` from state, triggering
  fresh OS deploy without manual taint.
- **pxe-test-vm-1**: blank disk + stale "Deployed" MaaS state caused kernel panic → guest
  agent timeout → apply failure. Released machine, cleared GCS lock.
- **Docs refresh**: rewrote `README.unit_params.md`, `README.waves.md`, `README.package-system.md`.

---

## 2026-03-30 — Cloud public IPs + provisioning_ip rename + pxe_host_trunk

- `static_ip` → `provisioning_ip` rename to clarify VLAN 12 MaaS commissioning IP.
- `cloud_public_ip` added for all 4 machines (ms01-01=.116, .117, .118, nuc-1=.119).
- `pxe_host_trunk` port profile: native=VLAN12, tagged=[VLAN10]. Changed all 4 PXE ports.
- `configure-cloud-public-vlan.yaml`: creates `vmbr0.10` on Proxmox hosts idempotently.
- `generate_ansible_inventory.py`: added `pve_cloud_public_ip` host var.
- `power_address` → type-specific fields (`amt_address`, `ipmi_address`, `redfish_address`).

---

## 2026-03-30 — Wave 8: Proxmox vmbr0 bridge fix for apt-installed hosts

1. **Reboot timeout**: `configure-linux-bridge.yaml` reboot_timeout 300s → 600s (Proxmox
   first boot after `apt install proxmox-ve` takes 6+ min).
2. **DHCP fallback**: `install-proxmox-packages.yaml` used `blockinfile` → appended second
   `iface enp87s0 inet dhcp`; first definition won. Fixed with `sed -i` that replaces in-place.

---

## 2026-03-30 — Wave 7: ms01-01 deploy fixes

- **`maas` snap not found with `become: true`**: switched to `shell` module for MaaS CLI
  tasks (sudo doesn't inherit `/snap/bin`).
- **maas-machines-test parser error**: moved Jinja2 vars to shell assignments at top of
  block; removed backslash-newline continuations.
- **Stale reserved IP**: blocking deploy; `configure-server.yaml` now idempotently removes
  existing link before recreating.
- **Proxmox split deploy-retry**: detects Proxmox installed but no interfaces → force-releases
  and re-deploys.

---

## 2026-03-30 — Debian trixie preseed and inventory path fixes

- Empty `cloud_init_password` locked the debian user. Fixed with conditional `chpasswd`.
- Disabled cloud-init network management to prevent overwriting MaaS static IP on reboot.
- Fixed stale inventory path in update-ssh-config.

---

## 2026-03-29 — Wave 7 test idempotency + ms01-01 config fixes

- `ssh_pwauth` check skips if no `cloud_init_password` set.
- ms01-01 YAML keys corrected to `machines/ms01-01` (were nested under region config).
- Force-release task calls `terragrunt state rm` before re-running.

---

## 2026-03-28 — install-proxmox: networkd stop bug + network fallback

- **Critical**: `state: stopped` on `systemd-networkd` released DHCP lease, dropped SSH.
  Fix: `masked: true` only. Rule added to CLAUDE.md: NEVER `state: stopped` on network
  services over SSH.
- Static IP enforcement after Proxmox install (`ansible_host` set to YAML static IP).
- `cloud_init_password` support for the debian user.

---

## 2026-03-28 — Post-reorganization path fixes (wave 6)

Fixed 6 path-staleness bugs from the March 26 VM directory reorganization: inventory
generator paths, Proxmox provider template paths, hook script paths.

---

## 2026-03-28 — GUI: config file watcher + skip_on_clean_all toggle

- `@rx.background` `_config_file_watcher` (mtime polling, 2s) auto-reloads state when
  stack YAML/SOPS changes externally.
- Per-wave `skip_on_clean_all: true` boolean with `⊘` toggle button in GUI waves panel.
- Fixed `toggle_wave_skip_on_clean_all` not repainting (needed `dict(self.wave_filters)`).

---

## 2026-03-28 — clean-all and run improvements

1. `clean-all` Stage 5: moves wave logs instead of deleting.
2. Stage 3: preserves GCS state for skipped waves. Fixed `grep -v` bug silently skipping
   all deletions.
3. `run.py`: deletes stale `.tflock` files from GCS before each wave apply (`pre_apply_unlock: true`).

---

## 2026-03-26 — VM directory reorganization + clean-all gsutil fix

- VMs reorganized into `vms/utils/` and `vms/test/` under each pve-node.
- `make clean-all`: changed `gsutil -m rm -r gs://bucket/` → `gsutil -m rm "gs://bucket/**"`
  (objects only, avoids IAM-restricted bucket deletion). Removed `gsutil rb` call.

---

## 2026-03-23 — ms01-01: GRUB fix + release_erase stale OS wipe

Fixed ms01-01 boot failure (GRUB targeting wrong disk). Added `release_erase: true` to
machine configs — MaaS wipes disk before re-deploying.

---

## 2026-03-22 — SOPS secrets file corruption: postmortem + CLAUDE.md rules

SOPS file destroyed by `sops -e /tmp/... > $SOPS_FILE` when sops failed — redirect truncated
before command ran. All credentials reconstructed from secure notes.
Rules added to CLAUDE.md: use `sops --set` for programmatic updates; never use shell
redirects or Write/Edit tools on `.sops.yaml` files.

---

## 2026-03-21 — Wave system introduction

Introduced wave system: `_wave` reserved param, `TG_WAVE`/`TG_WAVE_MAX` env vars for
selective unit execution. Wave category ordering enforced. `ignore_unreachable` added to
configure-proxmox to handle partially-deployed hosts.

---

## 2026-03-02 to 2026-03-15 — Early foundational setup

- **Bootstrap fix**: Terragrunt bootstrapped from first dependency-free unit.
- **Nuke script**: comprehensive 4-stage nuclear cleanup (unlock → destroy → wipe GCS → clean cache).
- **MaaS secrets consolidation**: fragmented secrets merged into single `providers.maas` section.
- **Proxmox ISO fix**: `content_type: iso` (not `import`) for qcow2 files.
- **configure-proxmox**: comprehensive Ansible automation for storage, API tokens, networking.
- **MaaS commission automation**: handles Commissioning/Testing states, stale API keys,
  `tofu import` variable requirements.
- **MaaS architecture**: PXE → Commission → Deploy pipeline; rack controller at 10.0.12.2;
  smart-plug power via MaaS rack proxy at localhost:7050.
- **Image-maker after_hook**: Packer images built idempotently after VM creation.
- **MaaS Proxmox host configure**: `configure-proxmox` runs twice (Stage 3b for early nodes,
  Stage 10 after Proxmox install for new nodes) with ProxyJump SSH support.
