# Move GPG Key Unlock to Framework Tool (`gpg-mgr`)

**Date**: 2026-04-23
**Plan**: `infra/_framework-pkg/_docs/ai-plans/move-gpg-key-unlock-to-fw.md`

## What was done

Created `infra/_framework-pkg/_framework/_gpg-mgr/gpg-mgr` — a new framework tool that
replaces the buggy human-only script `unlock-all-private-gpg-keys.sh`.

Integrated into `set_env.sh` so it runs automatically on every `source set_env.sh`,
before `config-mgr generate`, ensuring the gpg-agent TTY is current and all signing keys
are unlocked before any `terragrunt` run calls `sops_decrypt_file()`.

**Key design decisions:**
- `updatestartuptty` only by default — preserves cached passphrases across terminal sessions
- gpg-agent restart only if an unlock attempt fails (broken agent), not unconditionally
- Non-interactive (no-TTY) contexts: warn to stderr, exit 0 — does not break `source set_env.sh`
- `mktemp` for temp files (not `~/.gpg.tmp`), cleaned up via `trap RETURN`
- `--local-user <key_id>` per key so each key is individually unlocked

**Bugs fixed in old script:**
- Hardcoded `~/.gpg.tmp` never cleaned up
- `exit 0` inside a function (terminates the shell)
- No `--local-user` — all iterations signed with the default key only
- Always restarted gpg-agent (evicting all cached passphrases)

## Files changed

- **created**: `infra/_framework-pkg/_framework/_gpg-mgr/gpg-mgr`
- **modified**: `infra/_framework-pkg/_framework/_git_root/set_env.sh` — export `_GPG_MGR`, `GPG_TTY`; add `_gpg-mgr` to PATH; call `gpg-mgr` in startup checks
- **deleted**: `infra/_framework-pkg/_framework/_human-only-scripts/gpg/unlock-all-private-gpg-keys.sh`
- **modified**: `infra/_framework-pkg/_config/_framework-pkg.yaml` — bumped to 1.7.0
- **modified**: `infra/_framework-pkg/_config/version_history.md`
