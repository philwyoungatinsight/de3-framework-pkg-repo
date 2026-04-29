#!/bin/bash

# Collection of re-usable functions related to the framework

################################################################################
# Boiler plate
################################################################################

# uncomment this to for debugging
#set -x

# Aggressively catch and report errors
set -euo pipefail
function handle_error {
    local exit_status=$?
    echo "An error occurred on line $LINENO: $BASH_COMMAND"
    exit $exit_status
}
trap handle_error ERR

# Set Config variables
. $(git rev-parse --show-toplevel)/set_env.sh

################################################################################
# Functions
################################################################################

# Require explicit confirmation before destructive operations.
#
# Usage:
#   confirm_destructive "message describing what will be destroyed" [KEYWORD]
#
# KEYWORD defaults to "DELETE". The user must type it exactly to proceed.
# If _FORCE_DELETE=YES is set in the environment, the prompt is skipped and
# _FORCE_DELETE=YES is exported for child processes to inherit.
#
# Reads from /dev/tty so the prompt works even when stdin is a pipe or Make
# redirects stdin. On headless systems with no controlling terminal, the read
# safely fails and the operation is aborted.
#
# On confirmation, exports _FORCE_DELETE=YES so that child scripts that also
# call confirm_destructive() skip their prompts (single top-level confirmation).
#
# Example:
#   confirm_destructive "This will destroy all VMs."
#   confirm_destructive "This will wipe everything. There is NO undo." "NUKE"
function confirm_destructive() {
    local msg="${1:-Destructive operation requested.}"
    local keyword="${2:-DELETE}"
    if [[ "${_FORCE_DELETE:-}" == "YES" ]]; then
        echo "(_FORCE_DELETE=YES – skipping confirmation)"
        return 0
    fi
    echo ""
    echo "WARNING: $msg"
    printf "Type '%s' to confirm, anything else to abort: " "$keyword"
    local answer=""
    if { true </dev/tty; } 2>/dev/null; then
        read -r answer </dev/tty || true
    fi
    if [[ "$answer" != "$keyword" ]]; then
        echo "Aborted."
        exit 1
    fi
    export _FORCE_DELETE=YES
}

# Find a config file by its top-level key name.
# Searches for <key_name>.yaml in:
#   1. $GIT_ROOT/config/  (framework-level config, e.g. framework.yaml)
#   2. $_INFRA_DIR/*/_config/  (per-package config, e.g. gcp-pkg.yaml)
# Convention: every config file is named after the top-level key it contains.
function _find_component_config() {
    local key_name
    key_name="${1:-}"
    if [[ -z "$key_name" ]]; then
        echo "ERROR: _find_component_config requires a key name (e.g., gcp-pkg, framework)" >&2
        return 1
    fi
    local git_root candidate
    git_root="$(git rev-parse --show-toplevel)"
    # Check framework config/ first
    for f in "${git_root}/config/${key_name}.yaml" "${git_root}/config/${key_name}.sops.yaml"; do
        if [[ -f "$f" ]]; then
            echo "$f"
            return 0
        fi
    done
    # Fall back to per-package _config/ directories
    candidate=$(find "$_INFRA_DIR" -maxdepth 4 \( -name "${key_name}.yaml" -o -name "${key_name}.sops.yaml" \) -path "*/_config/*" 2>/dev/null | head -1)
    if [[ -z "$candidate" ]]; then
        echo "ERROR: neither ${key_name}.yaml nor ${key_name}.sops.yaml found." >&2
        echo "  Searched: $git_root/config/${key_name}.yaml" >&2
        echo "            $git_root/config/${key_name}.sops.yaml" >&2
        echo "            $_INFRA_DIR/*/_config/${key_name}.yaml" >&2
        echo "            $_INFRA_DIR/*/_config/${key_name}.sops.yaml" >&2
        echo "            $_INFRA_DIR/*/_config/_framework_settings/${key_name}.yaml" >&2
        echo "            $_INFRA_DIR/*/_config/_framework_settings/${key_name}.sops.yaml" >&2
        return 1
    fi
    echo "$candidate"
}

# wait_for_condition: Interactive polling loop with configurable timeout.
#
# Polls <check_cmd> until it returns 0, the timeout elapses, or the user
# requests early continuation.
#
# Timeout semantics (controlled by the named env var):
#   0   skip immediately — do not poll, return success
#   -1  block until the user presses Enter (no time limit)
#   N   poll every <interval> seconds for up to N seconds, then return 1
#
# Interactive controls (when /dev/tty is available):
#   Enter   continue immediately (return success now)
#   p / P   pause the countdown; press Enter to resume
#
# Parameters:
#   $1  description   Human-readable label for what is being waited for
#   $2  check_cmd     Shell command returning 0 when ready, non-0 otherwise
#   $3  timeout_var   Name of the env var that holds the timeout value
#   $4  default       Default timeout (seconds) if timeout_var is unset
#   $5  interval      (optional) Seconds between polls; default 15
#
# Returns 0 on success (condition met or user continued), 1 on timeout.
#
# Example:
#   wait_for_condition \
#     "Proxmox API endpoints reachable" \
#     "_proxmox_all_up" \
#     _PROXMOX_WAIT_TIMEOUT 300 15
# Returns 0 if the configured backend already exists; 1 if bootstrap is needed.
function _backend_exists() {
    local stack_config
    stack_config="$(_find_component_config framework_backend)"
    local info backend_type bucket endpoint
    info=$(python3 -c "
import yaml, sys
with open('$stack_config') as f:
    cfg = yaml.safe_load(f)
b = list(cfg.values())[0]
btype = b.get('type', 'local')
cfg = b.get('config', {})
bucket = cfg.get('bucket', '')
endpoint = cfg.get('endpoint', '') or cfg.get('s3_endpoint', '') or cfg.get('minio_endpoint', '')
print(btype, bucket, endpoint)
" 2>/dev/null) || return 1
    backend_type="${info%% *}"; info="${info#* }"
    bucket="${info%% *}";       endpoint="${info#* }"
    case "$backend_type" in
        local) return 0 ;;
        gcs)   gsutil ls "gs://$bucket" &>/dev/null ;;
        s3)
            if [[ -n "${endpoint:-}" && "$endpoint" != "None" ]]; then
                aws s3api head-bucket --bucket "$bucket" --endpoint-url "$endpoint" &>/dev/null
            else
                aws s3api head-bucket --bucket "$bucket" &>/dev/null
            fi ;;
        *) return 1 ;;
    esac
}

# Bootstrap the backend if it does not already exist.  Safe to call repeatedly.
function ensure_backend() {
    echo "=== Checking backend ==="
    if _backend_exists; then
        echo "Backend already exists – no bootstrap needed."
        return 0
    fi
    echo "Backend not found – running bootstrap..."
    # Bootstrap must run from a single unit directory (with no dependencies).
    # "run --all" would try to init every unit at once, which fails when the backend doesn't exist yet.
    # Pick the first unit with no dependency blocks.
    local first_unit
    first_unit=$(find "$_INFRA_DIR" -name "terragrunt.hcl" -not -path "*/.terragrunt-cache/*" \
        | xargs grep -rLE "^dependency\b" | xargs -n1 dirname | head -1)
    cd "$first_unit"
    terragrunt backend bootstrap --non-interactive
    echo "=== Backend ready ==="
}

function wait_for_condition() {
    local description="$1"
    local check_cmd="$2"
    local timeout_var="$3"
    local default_timeout="${4:-300}"
    local interval="${5:-15}"

    local timeout="${!timeout_var:-$default_timeout}"

    # timeout=0: skip entirely
    if [[ "$timeout" == "0" ]]; then
        echo "  (${timeout_var}=0 — skipping wait: ${description})"
        return 0
    fi

    local interactive=false
    if { true </dev/tty; } 2>/dev/null; then
        interactive=true
    fi

    echo ""
    echo "=== Waiting for: ${description} ==="

    # timeout=-1: block until user presses Enter
    if [[ "$timeout" == "-1" ]]; then
        echo "  (${timeout_var}=-1 — no timeout; press Enter to continue)"
        echo "  Press Enter when ready..."
        if $interactive; then
            read -r </dev/tty 2>/dev/null || true
        fi
        echo "  Continuing."
        return 0
    fi

    echo "  Timeout: ${timeout}s   Poll interval: ${interval}s"
    echo "  To skip:            export ${timeout_var}=0"
    echo "  To wait for Enter:  export ${timeout_var}=-1"
    if $interactive; then
        echo "  [Enter] continue now   [p] pause countdown"
    fi
    echo ""

    # Run check immediately before first sleep
    if eval "$check_cmd" 2>/dev/null; then
        echo "  [$(date '+%H:%M:%S')] Ready."
        return 0
    fi

    local elapsed=0
    while [[ $elapsed -lt $timeout ]]; do
        local key=""
        if $interactive; then
            # read -t: wait up to $interval seconds for one silent keypress
            if read -r -t "$interval" -s -n1 key </dev/tty 2>/dev/null; then
                # Drain any trailing newline so the terminal stays clean
                read -r -t 0.2 -n100 </dev/tty 2>/dev/null || true
                case "${key,,}" in
                    p)
                        echo ""
                        echo "  [PAUSED] Press Enter to resume..."
                        read -r </dev/tty 2>/dev/null || true
                        echo "  [RESUMED]"
                        continue  # re-poll without advancing elapsed
                        ;;
                    *)
                        # Enter (empty string) or any other key = continue now
                        echo ""
                        echo "  [$(date '+%H:%M:%S')] Continuing at user request."
                        return 0
                        ;;
                esac
            else
                # read timed out — interval has elapsed
                elapsed=$((elapsed + interval))
            fi
        else
            sleep "$interval"
            elapsed=$((elapsed + interval))
        fi

        if eval "$check_cmd" 2>/dev/null; then
            echo "  [$(date '+%H:%M:%S')] Ready (elapsed: ${elapsed}s)"
            return 0
        fi
        echo "  [$(date '+%H:%M:%S')] Not yet ready (elapsed: ${elapsed}s / ${timeout}s)"
    done

    echo ""
    echo "ERROR: Timed out waiting for: ${description} (after ${timeout}s)"
    echo "  To skip:           export ${timeout_var}=0"
    echo "  To wait for Enter: export ${timeout_var}=-1"
    return 1
}
