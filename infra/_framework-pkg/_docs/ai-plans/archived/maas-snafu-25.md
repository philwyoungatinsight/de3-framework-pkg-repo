# Plan: maas-snafu-25 — Rocky 9 Deployment Fails: grub2-install Refuses EFI Without --force

## Objective

Fix deployment failures for Rocky Linux 9 caused by `grub2-install` refusing to install
on EFI platforms without `--force`. Curtin's RHEL-specific curthooks run
`chroot /target grub2-install --target=x86_64-efi` during deployment, but Rocky 9's
`grub2-install` includes a Secure Boot check that refuses EFI installs without `--force`.

## Root Cause

During ms01-02 deployment (Run 170), curtin's `builtin_curthooks` → `setup_grub` →
`install_grub` ran:

```
chroot /target grub2-install --target=x86_64-efi --efi-directory=/boot/efi \
  --bootloader-id=rocky --recheck
```

Rocky 9's `grub2-install` (in the deployed target chroot) outputs:
```
grub2-install: error: This utility should not be used for EFI platforms because
it does not support UEFI Secure Boot. If you really wish to proceed, invoke the
--force option.
```

**Why `grub: install_devices: []` in the curtin preseed didn't help**: The curtin
preseed for Rocky 9 already has `grub: install_devices: []`, which was intended to
prevent curtin's built-in grub installation. However, for RHEL-family images
(`osfamily=redhat`) with `base_image=rhel/9`, curtin's RHEL-specific curthooks code
path does NOT respect `install_devices: []` and calls `setup_grub` regardless.

**Why `reinstall_grub_removable` in `late_commands` didn't run**: It includes `--force`
and would succeed, but `late_commands` only run after `curthooks` completes. Since
curthooks fails at grub2-install, late_commands never execute.

## Fix

Add a `grub2-install` wrapper at `/usr/local/sbin/grub2-install` in the Rocky 9 tgz
image. The wrapper calls `/usr/sbin/grub2-install --force "$@"`. Since `/usr/local/sbin`
appears before `/usr/sbin` in the default chroot PATH, curtin's
`chroot /target grub2-install` call finds the wrapper first and passes `--force`
transparently.

## Files Modified

### `infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/import-rocky-image.yaml` — modified
### `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/import-rocky-image.yaml` — modified

Add a task after "Install base packages via dnf in chroot" to create the wrapper:

```yaml
- name: "Create grub2-install wrapper in {{ item.name }} (adds --force for EFI chroot installs)"
  ansible.builtin.copy:
    dest: "{{ _mnt }}/usr/local/sbin/grub2-install"
    mode: "0755"
    content: |
      #!/bin/bash
      # Wrapper: Rocky 9's grub2-install refuses EFI install without --force.
      # Curtin runs `chroot /target grub2-install --target=x86_64-efi ...` during
      # RHEL curthooks — this wrapper in /usr/local/sbin (before /usr/sbin in PATH)
      # adds --force transparently.
      exec /usr/sbin/grub2-install --force "$@"
  become: true
```

### `scripts/ai-only-scripts/patch-rocky-image/` — created

One-time Ansible playbook that patches the EXISTING rocky-9 tgz already in MaaS
(avoids re-downloading the 700MB qcow2). Steps:
1. Extract existing tgz to `/var/snap/maas/common/rocky-patch/`
2. Create the grub2-install wrapper
3. Repack to a new tgz
4. Delete boot resource id=14 (rocky-9)
5. Re-import the patched tgz
6. Trigger boot-resources import
7. Wait for import to complete

## Applied Fix

1. Update both import-rocky-image.yaml files
2. Run the patch-rocky-image ai-only script
3. Annihilate ms01-02 (delete from MaaS + wipe TF state)
4. Restart the build from `maas.lifecycle.new` or `maas.lifecycle.deploying` wave

## Verification

- After re-import: `maas maas-admin boot-resources read` should show rocky-9 as Uploaded
- During ms01-02 deployment: install.log should NOT show grub2-install error
- ms01-02 should reach Deployed state

## Open Questions

None — root cause confirmed, fix is clear.
