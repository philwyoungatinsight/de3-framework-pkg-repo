#!/bin/bash
# Bootstrap script — export all framework environment variables and run startup checks.
#
# Source this before running any terragrunt, ansible, or utility command.
# Consumer standalone scripts (Category C): source "$(git rev-parse --show-toplevel)/set_env.sh"
# Framework scripts must NOT use git rev-parse — see infra/_framework-pkg/_docs/set-env-bootstrap-standard.md
#
# On every source it:
#   1. Exports path variables (_FRAMEWORK_PKG_DIR, _MAIN_PKG_DIR, tool paths, dynamic dirs, GCS bucket)
#   2. Creates the dynamic runtime directories under config/tmp/dynamic/
#   3. Runs `config-mgr generate` to pre-merge all package YAML and copy encrypted
#      SOPS files into $_CONFIG_DIR (Terragrunt decrypts secrets at runtime via
#      sops_decrypt_file — no secret is written to disk in plaintext)

# Idempotent: already sourced if _FRAMEWORK_PKG_DIR and _UTILITIES_DIR are both set.
[[ -n "${_FRAMEWORK_PKG_DIR:-}" && -n "${_UTILITIES_DIR:-}" ]] && return 0

_set_env_export_vars() {
    # ── Primary anchors ─────────────────────────────────────────────────────────
    # _FRAMEWORK_PKG_DIR is derived from BASH_SOURCE[0] (the path of set_env.sh
    # itself, which is always a symlink at the consumer repo root). This avoids
    # git rev-parse and works correctly from any subdirectory or symlinked context.
    # If already set (e.g. by a bash tool wrapper that cd's before running Python),
    # the existing value is kept and trusted.
    if [[ -z "${_FRAMEWORK_PKG_DIR:-}" ]]; then
        local _boot_root
        _boot_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        if [[ -z "$_boot_root" ]]; then
            echo "FATAL: could not determine repo root from BASH_SOURCE." >&2; return 1
        fi
        export _FRAMEWORK_PKG_DIR="$_boot_root/infra/_framework-pkg"
    fi

    # Internal repo root — derived from _FRAMEWORK_PKG_DIR, NOT exported.
    # All new code should reference _FRAMEWORK_PKG_DIR (or _MAIN_PKG_DIR) directly.
    local _repo_root
    _repo_root="$(dirname "$(dirname "$_FRAMEWORK_PKG_DIR")")"

    export _INFRA_DIR="$(dirname "$_FRAMEWORK_PKG_DIR")"
    export _FRAMEWORK_DIR="$_FRAMEWORK_PKG_DIR/_framework"    # framework tool source

    # --- Framework tool paths ---
    # These point to executable scripts that other tools, Makefiles, and Terragrunt hooks invoke.
    export _UTILITIES_DIR="$_FRAMEWORK_DIR/_utilities"                # shared bash/python/ansible lib
    export _ANSIBLE_ROLES_DIR="$_UTILITIES_DIR/ansible/roles"         # roles used by all playbooks
    export _GENERATE_INVENTORY="$_FRAMEWORK_DIR/_generate-inventory/run"   # entry-point is `run` (has Makefile); not added to PATH
    export _WRITE_EXIT_STATUS="$_UTILITIES_DIR/tg-scripts/write-exit-status/write-exit-status"  # tg hook helper
    export _CONFIG_MGR="$_FRAMEWORK_DIR/_config-mgr/config-mgr"       # pre-process, read, and write framework config (generate/get/set/set-raw/move)
    export _PKG_MGR="$_FRAMEWORK_DIR/_pkg-mgr/pkg-mgr"                # external package clone/sync
    export _UNIT_MGR="$_FRAMEWORK_DIR/_unit-mgr/unit-mgr"             # move/copy units with state
    export _RAMDISK_MGR="$_FRAMEWORK_DIR/_ramdisk-mgr/ramdisk-mgr"    # RAM-backed dir manager (tmpfs)
    export _CLEAN_ALL="$_FRAMEWORK_DIR/_clean_all/clean-all"           # nuclear destroy + state wipe
    export _WAVE_MGR="$_FRAMEWORK_DIR/_wave-mgr/wave-mgr"             # wave runner (apply/test/clean/list)
    export _FW_REPO_MGR="$_FRAMEWORK_DIR/_fw-repo-mgr/fw-repo-mgr"
    export _GPG_MGR="$_FRAMEWORK_DIR/_gpg-mgr/gpg-mgr"               # gpg-agent TTY update + key unlock
    export _SOPS_MGR="$_FRAMEWORK_DIR/_sops-mgr/sops-mgr"            # SOPS secrets re-encrypt + verify
    export _FW_REPOS_DIAGRAM_EXPORTER="$_FRAMEWORK_DIR/_fw_repos_diagram_exporter/fw-repos-diagram-exporter"  # repo/package discovery and diagram export

    # GPG_TTY must be exported from the calling shell — subprocess exports don't propagate.
    # tty(1) prints "not a tty" (non-zero) in non-interactive contexts; handle gracefully.
    export GPG_TTY
    GPG_TTY="$(tty 2>/dev/null || true)"

    # --- Runtime dynamic directories ---
    # All generated/runtime files go under config/tmp/dynamic/ so they are gitignored
    # and survive across shell sessions. Subdirs are created by _set_env_create_dirs.
    export _CONFIG_TMP_DIR="$_repo_root/config/tmp"
    export _DYNAMIC_DIR="$_CONFIG_TMP_DIR/dynamic"
    export _RAMDISK_DIR="$_DYNAMIC_DIR/ramdisk"               # RAM-backed scratch space (managed by _RAMDISK_MGR)
    export _WAVE_LOGS_DIR="$_DYNAMIC_DIR/run-wave-logs"      # per-wave apply/test log files
    export _GUI_DIR="$_DYNAMIC_DIR/gui"                      # GUI launcher status/control files
    export _CONFIG_DIR="$_DYNAMIC_DIR/config"                # pre-merged public YAML + encrypted SOPS copies (read by root.hcl)

    # --- Main package resolution ---
    # config/_framework.yaml declares which package is the "main package" — the deployment-
    # specific package that overrides framework defaults (e.g. pwy-home-lab-pkg).
    # A pre-existing _FRAMEWORK_MAIN_PACKAGE env var wins (for CI or per-dev overrides).
    if [[ -z "${_FRAMEWORK_MAIN_PACKAGE:-}" ]]; then
        export _FRAMEWORK_MAIN_PACKAGE
        _FRAMEWORK_MAIN_PACKAGE="$(python3 "$_FRAMEWORK_DIR/_utilities/python/read-set-env.py" config-pkg "$_repo_root")"
    fi
    export _MAIN_PKG_DIR=""
    if [[ -n "${_FRAMEWORK_MAIN_PACKAGE:-}" ]]; then
        export _MAIN_PKG_DIR
        _MAIN_PKG_DIR="$(realpath "$_INFRA_DIR/$_FRAMEWORK_MAIN_PACKAGE" 2>/dev/null || echo "$_INFRA_DIR/$_FRAMEWORK_MAIN_PACKAGE")"
    fi

    # --- GCS state backend (3-tier lookup) ---
    # Priority (highest → lowest):
    #   1. config/framework_backend.yaml            — ad-hoc per-developer override
    #   2. $_MAIN_PKG_DIR/_config/_framework_settings/framework_backend.yaml
    #                                               — deployment main package (e.g. pwy-home-lab-pkg)
    #   3. $_FRAMEWORK_PKG_DIR/_config/_framework_settings/framework_backend.yaml
    #                                               — framework default (always present)
    local _fw_backend
    if [[ -f "$_repo_root/config/framework_backend.yaml" ]]; then
        _fw_backend="$_repo_root/config/framework_backend.yaml"
    elif [[ -n "${_MAIN_PKG_DIR:-}" && \
            -f "$_MAIN_PKG_DIR/_config/_framework_settings/framework_backend.yaml" ]]; then
        _fw_backend="$_MAIN_PKG_DIR/_config/_framework_settings/framework_backend.yaml"
    else
        _fw_backend="$_FRAMEWORK_PKG_DIR/_config/_framework_settings/framework_backend.yaml"
    fi
    export _GCS_BUCKET
    _GCS_BUCKET="$(python3 "$_FRAMEWORK_DIR/_utilities/python/read-set-env.py" gcs-bucket "$_fw_backend")"
}

# Add framework tool directories to $PATH so bare command names work.
# Idempotent: each directory is only prepended once even if sourced multiple times.
# _generate-inventory is excluded because its entry-point is named `run`.
_set_env_update_path() {
    local _dir
    for _dir in \
        "$_FRAMEWORK_DIR/_config-mgr" \
        "$_FRAMEWORK_DIR/_pkg-mgr" \
        "$_FRAMEWORK_DIR/_unit-mgr" \
        "$_FRAMEWORK_DIR/_ramdisk-mgr" \
        "$_FRAMEWORK_DIR/_clean_all" \
        "$_FRAMEWORK_DIR/_wave-mgr" \
        "$_FRAMEWORK_DIR/_gpg-mgr" \
        "$_FRAMEWORK_DIR/_fw-repo-mgr" \
        "$_FRAMEWORK_DIR/_fw_repos_diagram_exporter"; do
        case ":${PATH}:" in
            *":${_dir}:"*) ;;
            *) PATH="${_dir}:${PATH}" ;;
        esac
    done
    export PATH
}

# Create all dynamic directories so tools can write to them without checking existence.
_set_env_create_dirs() {
    mkdir -p "$_CONFIG_TMP_DIR" "$_DYNAMIC_DIR" "$_WAVE_LOGS_DIR" "$_GUI_DIR" "$_RAMDISK_DIR" "$_CONFIG_DIR"
}

# Ensure gpg-agent TTY is current and all signing keys are unlocked before any
# terragrunt run calls sops_decrypt_file(). Prompts interactively if keys are not
# cached; fast-exits silently when they are.
# Then pre-merge all package YAML and copy encrypted SOPS files into $_CONFIG_DIR.
_set_env_run_startup_checks() {
    "$_GPG_MGR" --ensure >&2
    "$_FRAMEWORK_DIR/_config-mgr/generate" >&2
}

_set_env_export_vars || return 1
_set_env_update_path
_set_env_create_dirs
_set_env_run_startup_checks

# Clean up helper functions — they are not part of the public API.
unset -f _set_env_export_vars _set_env_update_path _set_env_create_dirs _set_env_run_startup_checks
