# Fix: ansible.builtin.copy + become:true chmod temp-file error in install-maas.yaml

**Date**: 2026-04-11  
**Waves affected**: pxe.maas.seed-server (wave 9)

## Summary

The `Configure systemd-resolved FallbackDNS` task in `install-maas.yaml` failed with:

```
Failed to set permissions on remote files (rc: 1, err:
  chmod: cannot access '/tmp/.ansible/ansible-tmp-.../': No such file or directory
  chmod: cannot access '/tmp/.ansible/ansible-tmp-.../.source.conf': No such file or directory
```

## Root Cause

`ansible.builtin.copy` with `become: true` intermittently fails on Ubuntu when
SSH pipelining is enabled. Even with `pipelining = true`, the `copy` module writes
source content to a temp file at `/tmp/.ansible/ansible-tmp-xxx/.source.conf`, then
uses sudo to chmod it. If the temp dir is cleaned between those steps (or if the
sudo boundary prevents access), the chmod fails with "No such file or directory".

This is the same known issue documented in the comments of `fix-maas-amt-ssl.yaml`
and `install-smart-plug-proxy.yaml`.

## Fix

Replaced `ansible.builtin.copy` with `ansible.builtin.shell` + heredoc, same pattern
as other root-owned file writes. The `[Resolve]` section header in the heredoc content
is kept at 4-space YAML indentation to avoid the YAML block-scalar parse error that
would occur if it appeared at column 0 (YAML would interpret `[Resolve]` as a flow
sequence start).

## General Rule

Any Ansible task that writes a file to a root-owned path with `become: true` should
use `ansible.builtin.shell` with a heredoc, NOT `ansible.builtin.copy`. This applies
to ALL configure-server task files. The pattern:

```yaml
ansible.builtin.shell: |
  DEST=/path/to/file
  NEW_CONTENT="$(cat << 'MARKER'
  line1
  line2
  MARKER
  )"
  if [ ! -f "$DEST" ] || [ "$(cat "$DEST")" != "$NEW_CONTENT" ]; then
    printf '%s\n' "$NEW_CONTENT" > "$DEST"
    chmod 0644 "$DEST"
    chown root:root "$DEST"
    echo "CHANGED"
  else
    echo "OK"
  fi
register: _result
changed_when: "'CHANGED' in _result.stdout"
```

Note: Use a named heredoc marker (not EOF) to avoid collisions with any outer
heredocs. Keep all heredoc content lines at 4-space YAML indentation.

## Files Changed

- `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/install-maas.yaml`
  (replaced `ansible.builtin.copy` with `ansible.builtin.shell` + heredoc for
   `Configure systemd-resolved FallbackDNS` task)
