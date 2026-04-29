# Plan: Move GPG Key Unlock to Framework Tool (`gpg-mgr`)

## Objective

Create a framework tool `gpg-mgr` that replaces the existing human-only script
`infra/_framework-pkg/_framework/_human-only-scripts/gpg/unlock-all-private-gpg-keys.sh`.
The tool will be called automatically from `set_env.sh` before any SOPS file access, so
the GPG agent is always updated and keys are always unlocked before `terragrunt` evaluates
`sops_decrypt_file()` in `root.hcl`. If any key is not yet cached, the tool prompts the
user interactively for a passphrase.

## Context

### Current state
- Human-only script: `infra/_framework-pkg/_framework/_human-only-scripts/gpg/unlock-all-private-gpg-keys.sh`
  - Bounces the gpg-agent via `systemctl --user restart gpg-agent` (kills all cached passphrases)
  - Sets `GPG_TTY=$(tty)` and calls `gpg-connect-agent updatestartuptty /bye`
  - Iterates secret keys and signs a test file to trigger passphrase caching
  - **Bugs**: writes to `~/.gpg.tmp` (hardcoded, not cleaned up); uses `exit 0` inside a
    function (should be `return 0`); doesn't pass `--local-user` per key so all iterations
    sign with the default key

- `set_env.sh` flow (in order): `_set_env_export_vars` → `_set_env_update_path` →
  `_set_env_create_dirs` → `_set_env_run_startup_checks` (calls `config-mgr generate`)
  - Does NOT set `GPG_TTY` today
  - Does NOT call the GPG unlock script

- First SOPS access is in `root.hcl` via `sops_decrypt_file()` during `terragrunt` evaluation.
  `config-mgr generate` does NOT decrypt SOPS files — it only copies encrypted files to
  `$_CONFIG_DIR`. So GPG unlock only needs to happen before any `terragrunt` run, but
  sourcing `set_env.sh` is the natural and earliest integration point.

### Why `GPG_TTY` must be set in `set_env.sh`, not just in `gpg-mgr`
`gpg-mgr` runs as a subprocess. `export GPG_TTY=...` inside it does not propagate to the
parent shell. Subsequent `gpg` calls in the user's interactive shell would be missing
`GPG_TTY`. Therefore `set_env.sh` must set `export GPG_TTY=$(tty ...)` directly, and
`gpg-mgr` inherits it from the environment.

### Agent restart vs TTY update
The existing script does a full `systemctl --user restart gpg-agent`, which evicts all
cached passphrases. The gentler alternative — `gpg-connect-agent updatestartuptty /bye` —
tells the running agent about the current TTY without clearing the cache. The TTY update
is sufficient for the typical case (new terminal session with existing passphrase cache).
A full restart should only happen when the agent itself is broken, not on every `source
set_env.sh`.

### Framework tool naming convention
Per CLAUDE.md: use `run` only when a sibling Makefile exists. Other framework tools use
descriptive names (`config-mgr`, `pkg-mgr`, `wave-mgr`, etc.). New tool: `gpg-mgr`.

## Decisions (confirmed)

1. **Agent restart**: Only restart gpg-agent if the unlock attempt itself fails (agent is
   broken). Default path uses `updatestartuptty` only — preserves passphrase cache across
   terminal sessions. No `--restart` flag needed; the restart is an automatic fallback.

2. **Delete the human-only script**: Yes — delete `unlock-all-private-gpg-keys.sh` as part
   of this change. It is superseded and has known bugs.

3. **Non-interactive (no TTY) behaviour**: Warn to stderr and exit 0. Do not fail the
   `source set_env.sh`.

## Files to Create / Modify

### `infra/_framework-pkg/_framework/_gpg-mgr/gpg-mgr` — create

New framework tool. Subcommands:
- `gpg-mgr` (no args): update agent TTY, check if all keys cached; if not, unlock interactively
- `gpg-mgr check`: update agent TTY, exit 0 if all keys cached, exit 1 if any are not
- `gpg-mgr unlock`: update agent TTY unconditionally, then run interactive unlock for all keys

```bash
#!/usr/bin/env bash
# gpg-mgr — ensure gpg-agent TTY is current and all signing keys are unlocked.
#
# Called automatically from set_env.sh on every `source set_env.sh`. Fast-exits if
# all keys are already cached in the agent. If any key needs a passphrase, prompts
# interactively. Requires GPG_TTY to be set in the environment (set_env.sh does this).

set -euo pipefail

_gpg_update_tty() {
    gpg-connect-agent updatestartuptty /bye >/dev/null 2>&1 || true
}

_gpg_restart_agent() {
    echo "gpg-mgr: restarting gpg-agent (unlock failed)" >&2
    gpgconf --kill gpg-agent 2>/dev/null || true
    gpg-connect-agent /bye >/dev/null 2>&1 || true  # starts a fresh agent
    _gpg_update_tty
}

_gpg_list_key_ids() {
    gpg --list-secret-keys --with-colons 2>/dev/null | grep "^sec" | cut -d: -f5
}

_gpg_all_cached() {
    # Returns 0 if every secret key is already cached in the agent (no passphrase needed),
    # 1 if any key is not cached. Uses --batch --no-tty so gpg fails rather than prompts.
    local tmpfile
    tmpfile="$(mktemp)"
    trap 'rm -f "$tmpfile"' RETURN
    printf 'gpg-mgr-check\n' > "$tmpfile"

    local all_ok=0
    while IFS= read -r key_id; do
        [[ -z "$key_id" ]] && continue
        if ! gpg --batch --no-tty --armor --detach-sign --local-user "$key_id" --yes \
                 "$tmpfile" >/dev/null 2>&1; then
            all_ok=1
            break
        fi
    done < <(_gpg_list_key_ids)
    return $all_ok
}

_gpg_unlock_all() {
    # Attempt interactive unlock for all secret keys. If any sign attempt fails after the
    # agent restart fallback, report the failure but continue (don't abort the shell source).
    local tmpfile
    tmpfile="$(mktemp)"
    trap 'rm -f "$tmpfile"' RETURN
    printf 'gpg-mgr-unlock\n' > "$tmpfile"

    local found=0
    local restarted=0
    while IFS= read -r key_id; do
        [[ -z "$key_id" ]] && continue
        found=1
        local user_id
        user_id="$(gpg --list-secret-keys --with-colons "$key_id" 2>/dev/null \
                   | grep "^uid" | head -n1 | cut -d: -f10)"
        echo "gpg-mgr: unlocking key $key_id ($user_id)" >&2
        if gpg --armor --detach-sign --local-user "$key_id" --yes "$tmpfile" >/dev/null 2>&1; then
            echo "gpg-mgr:   ✓ cached" >&2
        else
            # First failure: restart the agent once and retry
            if [[ $restarted -eq 0 ]]; then
                restarted=1
                _gpg_restart_agent
                if gpg --armor --detach-sign --local-user "$key_id" --yes "$tmpfile" >/dev/null 2>&1; then
                    echo "gpg-mgr:   ✓ cached (after agent restart)" >&2
                    continue
                fi
            fi
            echo "gpg-mgr:   ✗ failed or cancelled" >&2
        fi
    done < <(_gpg_list_key_ids)

    if [[ $found -eq 0 ]]; then
        echo "gpg-mgr: no secret keys found" >&2
    fi
}

_gpg_has_tty() {
    [[ -n "${GPG_TTY:-}" ]] && [[ "$GPG_TTY" != "not a tty" ]]
}

cmd="${1:-}"

case "$cmd" in
    check)
        _gpg_update_tty
        _gpg_all_cached
        ;;
    unlock)
        _gpg_update_tty
        _gpg_unlock_all
        ;;
    "")
        _gpg_update_tty
        if _gpg_all_cached; then
            exit 0  # all keys cached — nothing to do
        fi
        if ! _gpg_has_tty; then
            echo "gpg-mgr: warning: no TTY available and keys are not cached" \
                 "— SOPS decryption may fail" >&2
            exit 0
        fi
        _gpg_unlock_all
        ;;
    *)
        echo "Usage: gpg-mgr [check|unlock]" >&2
        exit 1
        ;;
esac
```

Make executable: `chmod +x infra/_framework-pkg/_framework/_gpg-mgr/gpg-mgr`

### `set_env.sh` — modify

Three changes:

**1. `_set_env_export_vars`** — add GPG_TTY export and `_GPG_MGR` path variable (after
the existing tool path exports, e.g. after `_WAVE_MGR`):

```bash
export _GPG_MGR="$_FRAMEWORK_DIR/_gpg-mgr/gpg-mgr"

# GPG_TTY must be set in the calling shell (subprocess exports don't propagate).
# tty(1) returns "not a tty" / non-zero in non-interactive contexts — handle gracefully.
export GPG_TTY
GPG_TTY="$(tty 2>/dev/null || true)"
```

**2. `_set_env_update_path`** — add `_gpg-mgr` directory to the PATH loop:

```bash
"$_FRAMEWORK_DIR/_gpg-mgr" \
```
(add alongside the existing `_config-mgr`, `_pkg-mgr`, etc. entries)

**3. `_set_env_run_startup_checks`** — call `gpg-mgr` before `config-mgr generate`:

```bash
_set_env_run_startup_checks() {
    "$_GPG_MGR" >&2
    "$_FRAMEWORK_DIR/_config-mgr/generate" >&2
}
```

### `infra/_framework-pkg/_framework/_human-only-scripts/gpg/unlock-all-private-gpg-keys.sh` — delete

Superseded by `gpg-mgr`. Bugs: hardcoded `~/.gpg.tmp`, `exit 0` in function, no
`--local-user` per key. Delete once `gpg-mgr` is confirmed working.

### `infra/_framework-pkg/_framework/_human-only-scripts/gpg/README.gpg-setup.md` — keep or delete

Contains reference notes on GPG setup options. Unrelated to the unlock script itself.
Keep unless user says otherwise.

## Execution Order

1. Create `infra/_framework-pkg/_framework/_gpg-mgr/` directory and write `gpg-mgr` script
2. `chmod +x infra/_framework-pkg/_framework/_gpg-mgr/gpg-mgr`
3. Modify `set_env.sh`: export `_GPG_MGR` + `GPG_TTY` in `_set_env_export_vars`
4. Modify `set_env.sh`: add `_gpg-mgr` to `_set_env_update_path`
5. Modify `set_env.sh`: call `"$_GPG_MGR"` in `_set_env_run_startup_checks`
6. Delete `unlock-all-private-gpg-keys.sh` (pending confirmation of open question 2)
7. Write ai-log entry, bump `_framework-pkg` `_provides_capability` + `version_history.md`
8. Commit

## Verification

```bash
# Re-source in interactive shell — should prompt for passphrase if keys not cached,
# then exit silently on re-source:
source set_env.sh

# Check tool is on PATH and runs:
gpg-mgr check   # exit 0 if cached, 1 if not

# Verify GPG_TTY is exported:
echo $GPG_TTY   # e.g. /dev/pts/0

# Verify SOPS still decrypts correctly (no regressions):
source set_env.sh && terragrunt plan   # from any unit with secrets
```
