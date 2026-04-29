# _framework-pkg version history

## 1.21.0  (2026-04-26, git: 3e530f0)
- fw-repo-mgr: rename script to `run`, add Makefile with build/validate/status targets
- fw-repo-mgr: fix TypeError ('NoneType' is not iterable) — tier-3 framework_repo_manager.yaml had `framework_repos: null`; add `or []` guards throughout
- fw-repo-mgr: replace positional subcommands with GNU-style flags (`--build`/`-b`, `--validate`/`-v`, `--status`/`-s`, `--force-push`/`-f`)
- fw-repo-mgr: fix `$_EPHEMERAL` → `$_RAMDISK_DIR`
- set_env.sh: update `_FW_REPO_MGR` to point to new `run` script; remove `_fw-repo-mgr` from PATH list

## 1.20.0  (2026-04-26, git: cdcf909)
- Rename _FRAMEWORK_CONFIG_PKG → _FRAMEWORK_MAIN_PACKAGE; _FRAMEWORK_CONFIG_PKG_DIR → _FRAMEWORK_MAIN_PACKAGE_DIR (realpath-resolved)
- Old names re-exported as aliases in set_env.sh for backward compatibility
- Python tools fall back to old env var name if new one is unset
- Update all live code: root.hcl, fw-repo-mgr, pkg-mgr, packages.py, framework_config.py, config.py (diagram exporter)
- Docs: config-overview.md, config-files.md updated

## 1.19.0  (2026-04-26, git: a417287)
- fw-repos-diagram-exporter scanner: fix crash when framework_repos_manager.yaml has explicit null lists (`framework_repos:`, `source_repos:`, `framework_packages:`, `notes:`, `labels:` with no values); replace `.get(key, [])` with `.get(key) or []` throughout `_load_repo_manager` and `_scan_dir`

## 1.18.0  (2026-04-26, git: 1236545)
- sops-mgr: add `-d|--infra-dir PATH` to scope file discovery to a specific directory
- fw-repo-mgr: call `sops-mgr --re-encrypt --infra-dir "$repo_dir/infra"` after `_write_sops_yaml` so copied `*.sops.yaml` files are re-keyed before commit
- CLAUDE.md: add "Why Use Framework Tools" rule documenting traceability benefit

## 1.17.0  (2026-04-26, git: df2cc11)
- de3-gui: add spinner to fw-repos Refresh button; convert `refresh_fw_repos_data` to `@rx.event(background=True)` so the button disables and shows "Refreshing…" during the scan

## 1.16.0  (2026-04-26, git: 6379bf6)
- Rename framework tool `_fw-repos-visualizer` → `_fw_repos_diagram_exporter`: directory, Python package (`fw_repos_visualizer` → `fw_repos_diagram_exporter`), bash entry-point (`fw-repos-visualizer` → `fw-repos-diagram-exporter`), config YAML (`framework_repos_visualizer.yaml` → `framework_repos_diagram_exporter.yaml`), state dir (`config/tmp/fw-repos-visualizer` → `config/tmp/fw_repos_diagram_exporter`), cache dir, env var (`_FW_REPOS_VISUALIZER` → `_FW_REPOS_DIAGRAM_EXPORTER`)
- Update GUI hardcoded paths in `homelab_gui.py` and error message in `fw_repos_mermaid_viewer.html`

## 1.15.0  (2026-04-26, git: d69b6bd)
- fw-repos-visualizer scanner: URL read from `new_repo_config.git-remotes[0].git-source`; `upstream_url` removed; `local_only: true` repos skipped from BFS enqueue
- fw-repo-mgr: skip remote push for `local_only: true` repos; status shows `(local-only)` flag
- framework-repo-manager.md: new doc covering `fw-repo-mgr` CLI, per-repo fields, and `local_only` workflow
- de3-runner template config: removed stale `pwy-home-lab-pkg` active entry; replaced with generic commented example

## 1.14.0  (2026-04-26, git: 5727808)
- fw-repos-visualizer: add clickable hyperlinks to DOT output — package nodes link to
  the repo browse URL; cluster labels link to framework_repo_manager.yaml in the
  repo's config package; scanner backfills main_package from declared stubs

## 1.13.0  (2026-04-26, git: 9146632)
- rename _framework.config_package to _framework.main_package in fw-repo-mgr, read-set-env.py, and scanner.py

## 1.12.0  (2026-04-25, git: a8fb7cd)
- fw-repos-visualizer: add label system (name + optional qualifiers); initialize _purpose and _docs
  for all pwy-home-lab-pkg repos; render labels in text output and _purpose in dot cluster subtitle

## 1.11.0  (2026-04-25, git: fcb6480)
- fw-repos scanner: scan framework_backend.yaml from config pkg settings dir; store notes
  from framework_repo_manager.yaml `notes:` list per repo entry; back-fill both into
  scan result entries

## 1.10.0  (2026-04-25, git: 0bcd51b)
- fw-repos-visualizer scanner: scan `config/_framework.yaml` in each repo to extract
  `config_package`; derive it from `is_config_package` in declared repos; back-fill for
  local repo from the declared stub

## 1.9.1  (2026-04-23, git: b73a4b3)
- fw-repos-visualizer scanner: replace `rglob` with `os.walk(followlinks=True)` so
  symlinked dirs (e.g. `infra/_framework-pkg`) are scanned in the current repo
- framework_repos_visualizer.yaml: enable all 4 output formats and capability visualization

## 1.9.0  (2026-04-23, git: 20d985d)
- Add `fw-repos-visualizer` framework tool: BFS-discovers all reachable framework repos,
  scans `_framework_settings` dirs, renders as yaml/json/text/dot simultaneously
- State files (known-fw-repos.yaml, output.*) in `config/tmp/fw-repos-visualizer/`; config
  in `_framework_settings/framework_repos_visualizer.yaml`
- Configurable auto-refresh: modes never/fixed_time/file_age; default file_age, 10s gate
- Optional capability visualization: show_capability_deps, show_capabilities_in_diagram
- Repo lineage from framework_repo_manager.yaml: source_repos seeded into BFS; generated
  repos annotated with created_by and rendered as bold green "creates" edges in DOT

## 1.8.0  (2026-04-23, git: eb48c7a)
- config-mgr: add `fw-setting <name>` subcommand — canonical 3-tier lookup for framework settings files
- ramdisk-mgr: replace both inline 3-tier bash blocks with `config-mgr fw-setting` call
- framework_config.py: add public `fw_cfg_path()` for 3-tier lookup reuse in any Python tool
- unit-mgr: fix `_read_framework_backend()` — wrong path and missing 3-tier resolution

## 1.7.1  (2026-04-23, git: 5226b56)
- Remove defunct `_human-only-scripts/` directory and all references (CLAUDE.md, README, code-architecture.md, GUI tooltip)

## 1.7.0  (2026-04-23, git: d5a25bf)
- Add `gpg-mgr` framework tool: auto-updates gpg-agent TTY and unlocks signing keys on `source set_env.sh`; restarts agent only on failure; warns in non-interactive contexts
- Remove human-only `unlock-all-private-gpg-keys.sh` (superseded)
- set_env.sh: export `_GPG_MGR`, `GPG_TTY`; call `gpg-mgr` in `_set_env_run_startup_checks` before `config-mgr generate`

## 1.6.0  (2026-04-23, git: 8c8cdcd)
- pkg-mgr: remove `import_path` field support — symlink path always derived from package `name`
- pkg-mgr: error if `import_path` is set in any package entry
- framework_packages.yaml, framework_repo_manager.yaml: remove all `import_path:` fields
- de3-gui homelab_gui.py: update docstring to remove `import_path` from return shape

## 1.5.4  (2026-04-23, git: 4e47783)
- pkg-mgr: add `_assert_pkg_name()` guard called in --import, --rename, --copy
- pkg-mgr: add name validation in --sync's Python heredoc (reuses existing invalid/sys.exit pattern)
- fw-repo-mgr: add name validation in `_write_framework_packages_yaml()` before writing
- framework_repo_manager.yaml: update example package name (my-homelab → my-homelab-pkg)

## 1.5.3  (2026-04-23, git: 9fc2b58)
- set_env.sh: add section headers and inline comments for all variable groups
- set_env.sh: document 3-tier GCS bucket lookup, config-package resolution, startup check
- set_env.sh: update _CONFIG_MGR comment to reflect full CLI (generate/get/set/set-raw/move)
- config-overview.md: rewrite as developer landing page; fix all broken links; add set_env.sh, 3-tier lookup, $_CONFIG_MGR subcommands reference

## 1.5.2  (2026-04-23, git: ece766c)
- replace all direct `sops --set` calls in aws-pkg, azure-pkg, gcp-pkg seed scripts with `"$_CONFIG_MGR" set-raw --sops`
- fix 5 stale `_config-mgr/run` references in Ansible tg-scripts (proxmox, maas) to use `{{ lookup('env', '_CONFIG_MGR') }}`

## 1.5.1  (2026-04-23, git: d78be49)
- remove all stale `default-pkg` references: update 6 _setup/run scripts, 2 maas playbooks, archived query-unifi-switch script, de3-gui defaults.yaml, .gitignore, and .claude/settings.local.json

## 1.5.0  (2026-04-22, git: 829ead3)
- set_env.sh: replace inline Python heredocs with read-set-env.py helper
- set_env.sh: export tool path env vars (_PKG_MGR, _UNIT_MGR, _CLEAN_ALL, _EPHEMERAL, _CONFIG_MGR, _FW_REPO_MGR)
- rename framework tool scripts from `run` to descriptive names (config-mgr, pkg-mgr, unit-mgr, ephemeral, clean-all, fw-repo-mgr, write-exit-status, setup-ephemeral-dirs, purge-gcs-status, fix-git-index-bits, upgrade-routeros)
- _git_root/run: use ENV[_CLEAN_ALL/PKG_MGR/EPHEMERAL] instead of hardcoded paths
- fw-repo-mgr: use $_PKG_MGR/$_EPHEMERAL env vars instead of hardcoded paths
- _WRITE_EXIT_STATUS: updated to write-exit-status/write-exit-status

## 1.4.11  (2026-04-22, git: d3d92ad)
- ephemeral: skip dir creation when size_mb=0 in framework_ephemeral_dirs.yaml

## 1.4.10  (2026-04-22, git: 98f7ca4)
- framework_settings: add placeholder comments + examples for framework_backend, gcp_seed, framework_clean_all
- framework_repo_manager.yaml: add commented-out framework_package_template, framework_settings_template, framework_settings_sops_template blocks; fix Example A/B to use is_config_package

## 1.4.9  (2026-04-22, git: 69dbdb8)
- fw-repo-mgr: copy full set of framework settings files into generated repos (_copy_framework_settings)
- fw-repo-mgr: apply framework_settings_template overrides from config (_write_settings_template)
- framework-utils.sh: _find_component_config maxdepth 3→4 so _framework_settings/ files are found

## 1.4.8  (2026-04-22, git: 90d05e0)
- fw-repo-mgr: _write_framework_packages_yaml() now reads framework_package_template and prepends it to the package list so _framework-pkg is auto-injected into every generated repo

## 1.4.7  (2026-04-21, git: 95b5bda)
- rename framework_manager.yaml → framework_repo_manager.yaml in _framework_settings/
- fw-repo-mgr/run: update FW_MGR_CFG filename and all d.get('framework_manager') key reads
- version history moved from YAML comments to version_history.md peer file

## 1.4.6  (2026-04-21, git: 28bc7b2)
- config/_framework.yaml: new anchor declaring which package holds framework config
- set_env.sh: reads _framework.yaml → exports _FRAMEWORK_CONFIG_PKG / _FRAMEWORK_CONFIG_PKG_DIR
- framework_config.py: find_framework_config_dirs() — three-tier lookup (framework → config-pkg → config/)
- packages.py: _fw_cfg_path() — three-path lookup (config/ → config-pkg → framework)
- pkg-mgr/run: _fw_cfg() — three-path lookup matching packages.py
- root.hcl: _fw_backend_path — three-tier fileexists() chain
- docs: config-files.md updated for three-tier lookup and _framework.yaml anchor

## 1.4.5  (2026-04-21, git: 924b818)
- move framework_packages.yaml from _framework-pkg/_config/ to config/
- packages.py: load_framework_packages() uses _fw_cfg_path() (two-path lookup)
- pkg-mgr/run: FRAMEWORK_PKGS_CFG uses _fw_cfg() helper
- _framework-pkg/_config/ now contains only _framework-pkg.yaml
- move framework_config_mgr.yaml, framework_package_management.yaml, framework_package_repositories.yaml from _framework-pkg/_config/ to config/
- packages.py: _fw_cfg_path() two-path helper for framework_config_mgr.yaml
- pkg-mgr/run: _fw_cfg() shell helper for framework_package_*.yaml
- docs: config-files.md documents all hardcoded framework config paths
- framework_config.py: find_framework_config_dirs() — framework dir + config/ at git root
- load_framework_config(): accepts list of dirs; deployment overrides framework defaults
- root.hcl: framework_backend.yaml checked in config/ first, _framework-pkg/_config/ fallback
- deployment-specific framework_*.yaml files moved from _framework-pkg/_config/ to config/

## 1.4.4  (2026-04-21, git: 1355491)

## 1.4.3  (2026-04-21, git: 4a493c7)

## 1.4.2  (2026-04-21, git: 6e04809)
- framework_packages.yaml: add package_type (embedded|external) field; rename public → exportable
- pkg-mgr: validate package_type consistency; use package_type in sync/clean/status/list-remote
- fw-repo-mgr: comment update only (prune logic unchanged)

## 1.4.1  (2026-04-21, git: 10db5db)
- add fw-repo-mgr: clone+prune+sync tool for splitting and combining framework repos

## 1.4.0  (2026-04-21, git: c0deffb)
- renamed default-pkg → _framework-pkg; underscore prefix signals reserved/framework status
- _DEFAULT_PKG_DIR env var renamed to _FRAMEWORK_PKG_DIR
- root symlinks (CLAUDE.md, set_env.sh, run, root.hcl, Makefile, etc.) updated
- all path strings and YAML keys updated across 82 files

## 1.3.1  (2026-04-21, git: e39b679)
- config-mgr writer: set_config_param supports dot-separated nested keys (e.g. token.id)
- de3-runner maas-pkg sync-api-key, configure-region, configure-server: replaced sops --set with config-mgr set --sops; config_source routing now determines target secrets file
- de3-runner proxmox-pkg configure-api-token: replaced sops --set (old nested providers.proxmox format) with config-mgr set --sops (flat config_params format, nested key support)
- de3-runner maas-pkg fetch-maas-state: reads _MAAS_CONFIG from $_CONFIG_DIR
- de3-runner de3-gui-pkg de3-gui: reads PKG_CONFIG_FILE from $_CONFIG_DIR
- pwy-home-lab-pkg update-ssh-config: reads PKG_CONFIG from $_CONFIG_DIR

## 1.3.0  (2026-04-21, git: 01cc7e1)
- config-mgr: new framework tool (_config-mgr/) that pre-merges and pre-decrypts all package config into $_CONFIG_DIR before terragrunt/ansible run
- framework_packages.yaml: added config_source field to all external packages
- framework_config_mgr.yaml: new config file controlling merge_method and output_mode
- set_env.sh: exports $_CONFIG_DIR; calls config-mgr generate on every source
- root.hcl: reads from $_CONFIG_DIR (plain YAML, no sops_decrypt_file)
- unit-mgr: resolves config_source chain for correct config file routing
- generate_ansible_inventory.py: reads from $_CONFIG_DIR instead of infra/*/_config/
- config_base role: reads from $_CONFIG_DIR; removes community.sops.load_vars
- validate-config.py: RULE 6 — config_source chain existence and cycle checks

## 1.2.2  (2026-04-21, git: 7caaa49)
- pkg-mgr: removed local_overrides (per-developer git_ref override); git_ref from framework_packages.yaml is now the single source of truth

## 1.2.1  (2026-04-21, git: f2530cf)
- pkg-mgr: git_ref is now required on all imported packages; sync and import both error if git_ref is missing, preventing directory conflicts under _ext_packages/<slug>/

## 1.2.0  (2026-04-21, git: bddc840)
- pkg-mgr: local_overrides in framework_package_management.yaml — per-developer git_ref override; shown as (local) in status output
- pkg-mgr: removed local_copy inclusion method; only linked_copy remains; external_package_dir now required

## 1.1.0  (2026-04-21, git: 46b610d)
- pkg-mgr: two-level clone layout _ext_packages/<slug>/<ref>/ — each (repo, ref) pair gets its own clone; / in branch names replaced with __ in dir name; HEAD for no git_ref
- Migration: pkg-mgr clean --all && pkg-mgr sync required after upgrade

## 1.0.6  (2026-04-21, git: 9f84b58)
- pkg-mgr: optional git_ref field on package entries — pins clone to branch, tag, or SHA
- pkg-mgr status: Ref column shows checked-out branch/short-SHA per repo
- pkg-mgr import: --git-ref <ref> flag writes git_ref to framework_packages.yaml

## 1.0.4  (2026-04-21, git: 4c07679)
- pkg-mgr --sync auto-migrates repos when inclusion_method changes in config

## 1.0.3  (2026-04-20, git: 4b76508)
- pkg-mgr: switched to --flag style CLI; added --status-verbose with Path column

## 1.0.2  (2026-04-20, git: ff33fc5)
- pkg-mgr status: rich ANSI/unicode table with config header, repos, and packages sections

## 1.0.1
- Fixed some bugs and fetches packages from de3-runner

## 1.0.0
- is the original code from de3-runner
