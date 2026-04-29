# Plan: maas-snafu-20 — Rocky 9 grub2-mkconfig Path Rejection

## Objective

ms01-02 Rocky 9 deployment was failing at the curthooks grub installation stage.
curtin runs `grub2-mkconfig -o /boot/efi/EFI/rocky/grub.cfg` inside the Rocky 9 chroot,
but Rocky 9's grub2-mkconfig rejects that path with:

```
Running `grub2-mkconfig -o /boot/efi/EFI/rocky/grub.cfg' will overwrite the GRUB wrapper.
Please run `grub2-mkconfig -o /boot/grub2/grub.cfg' instead to update grub.cfg.
```

This causes `curtin command curthooks` to fail → `curtin command install` fails →
machine marked "Failed deployment" after only ~2 minutes.

## Context

**Root cause chain:**
1. Rocky 9 uses BLS (Boot Loader Specification). `/boot/efi/EFI/rocky/grub.cfg` is
   a small "wrapper" file that sources `/boot/grub2/grub.cfg` via BLS chain-load.
2. Rocky 9's grub2-mkconfig has a built-in guard: it refuses to overwrite
   `/boot/efi/EFI/rocky/grub.cfg` with a full grub.cfg because that would break BLS.
3. curtin's `install_grub.py` does not know about this Rocky 9 restriction and runs
   `grub2-mkconfig -o /boot/efi/EFI/rocky/grub.cfg` — the wrong path.
4. curtin fails, late_commands never run, machine never signals MaaS.
5. Machine cloud-init power_state_change reboots the machine, it PXE boots in
   still-Deploying state → MaaS looks for `custom/amd64/ga-24.04/rocky-9` boot image
   (not found) → "Failed deployment".

**Partition layout of Rocky 9 GenericCloud image (DD'd to nvme1n1):**
- nvme1n1p1: BIOS boot (PARTLABEL=p.legacy, no filesystem)
- nvme1n1p2: EFI (vfat, PARTLABEL=p.UEFI)
- nvme1n1p3: /boot (XFS, LABEL=BOOT)
- nvme1n1p4: / root (XFS, LABEL=rocky)

**Commissioning storage config quirk:**
- curtin found `install_devices: ['/dev/nvme1n1p1']` (p1 = BIOS boot, not EFI)
- This is because the commissioning storage config has `nvme0n1-part1` as the
  boot-flagged partition, and that maps to nvme1n1p1 in the deployed disk's layout
- This caused curtin to also pass `--part 1` to `efibootmgr --create`, which creates
  an invalid UEFI boot entry pointing to the BIOS boot partition (not EFI)
- With `grub: {install_devices: []}`, curtin skips all of this

**Evidence:**
```
Command: ['unshare', '--fork', '--pid', '--', 'chroot', '/tmp/tmpm4auad04/target',
          'grub2-mkconfig', '-o', '/boot/efi/EFI/rocky/grub.cfg']
Exit code: 1
Stderr: Running `grub2-mkconfig -o /boot/efi/EFI/rocky/grub.cfg' will overwrite the GRUB wrapper.
        Please run `grub2-mkconfig -o /boot/grub2/grub.cfg' instead to update grub.cfg.
        GRUB configuration file was not updated.
```

## Open Questions

None — ready to proceed.

## Files Created / Modified

### `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/templates/curtin_userdata_rocky9.j2` — modified

Added `grub: {install_devices: []}` at root level to tell curtin to skip its built-in
grub installation. The `reinstall_grub_removable` late_command handles grub correctly
with `grub2-mkconfig -o /boot/grub2/grub.cfg` (the correct Rocky 9 path).

### `infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/templates/curtin_userdata_rocky9.j2` — modified

Same change as configure-server template (the two templates are identical).

## Execution Order

1. Apply preseed template changes (done)
2. Annihilate ms01-02: delete from MaaS (system_id tayhp3) + wipe GCS TF state
3. Kill any running build
4. Re-run `./run -b -w "*maas*"`:
   - pxe.maas.seed-server wave re-deploys preseed to MaaS server
   - maas.lifecycle.new → commission → deploy → deployed

## Verification

- curthooks stage completes WITHOUT `install-grub: FAIL`
- late_commands run (check for `--- reinstall_grub_removable start ---` in `aa_debug` log)
- `reinstall_grub_removable` runs `grub2-mkconfig -o /boot/grub2/grub.cfg` (correct path)
- MaaS machine reaches Deployed state
- ms01-02 SSH accessible post-deployment
