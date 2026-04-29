# Fix: AMT SSL drop-in YAML parse error from zero-indent shell string

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.seed-server (wave 9)

## Summary

`fix-maas-amt-ssl.yaml` had a YAML parse error at line 73 that prevented the entire
task file from loading. Root cause: the `NEW_CONTENT` variable was set with a
single-quoted multi-line shell string, and the continuation lines (`[Service]`,
`Environment=...`, etc.) were at column 0. YAML's block scalar parser terminates the
block scalar when it encounters a line with less indentation than the established
content indent (4 spaces). At column 0, YAML tried to parse `[Service]` as a new
top-level element — which looks like a YAML flow sequence start — and then
`Environment=OPENSSL_CONF=...` as a mapping key without a `:`, producing:

```
While scanning a simple key could not find expected ':'
Origin: fix-maas-amt-ssl.yaml:73:1
```

## Root Cause

The prior fix (commit 1eb168d) replaced `ansible.builtin.copy` with
`ansible.builtin.shell` + single-quoted multi-line string for the systemd drop-in
content. In a `|` block scalar, YAML determines the content indentation from the
FIRST content line (4 spaces). Any subsequent line with FEWER than 4 spaces is
outside the block scalar. Lines 70-73 of the shell string continued at column 0:

```yaml
  ansible.builtin.shell: |
    DEST=...
    NEW_CONTENT='# Set OPENSSL_CONF ...    ← 4-space indent: inside block scalar
# (port 16993) ...                         ← 0-space indent: OUTSIDE block scalar!
...
[Service]                                  ← YAML sees a flow sequence start
Environment=OPENSSL_CONF=...'              ← YAML expects ':' for mapping key
```

## Fix

Replace the single-quoted multi-line string with a command substitution + named
heredoc. All lines remain at 4-space indentation inside the YAML block scalar.
After YAML strips the block scalar indent, the shell sees the heredoc without leading
spaces — producing the correct systemd unit file content:

```yaml
  ansible.builtin.shell: |
    DEST=/etc/systemd/system/snap.maas.pebble.service.d/openssl-legacy.conf
    NEW_CONTENT="$(cat << 'DROPIN_EOF'
    # Set OPENSSL_CONF so wsman subprocesses can connect to Intel AMT
    # ...
    [Service]
    Environment=OPENSSL_CONF=/var/snap/maas/common/openssl-legacy.cnf
    DROPIN_EOF
    )"
```

The `DROPIN_EOF` marker, after YAML strips 4 spaces, appears at column 0 in the
actual shell script — correctly terminating the heredoc.

## General Rule

In Ansible `|` block scalars, multi-line shell strings with content at column 0
break YAML parsing. Use a heredoc inside `$()` command substitution — all heredoc
content lines are indented to the block scalar level in YAML but appear at column 0
in the executed shell.

## Files Changed

- `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/fix-maas-amt-ssl.yaml`
  (replaced single-quoted multi-line NEW_CONTENT with heredoc+command substitution)
