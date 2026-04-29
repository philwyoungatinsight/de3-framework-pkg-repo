# Plan: maas-snafu-22 — Switch Rocky 9 Image to packer-maas tgz Format

## Objective

Switch the Rocky 9 MaaS boot resource from `ddgz` (raw disk image, DD'd to disk) to
`tgz` (root filesystem tarball) with `base_image=rhel/9`, following the official
Canonical packer-maas approach. This gives curtin full control of partitioning and
GRUB installation via its RHEL-specific hooks, eliminating the chain of preseed
workarounds that have caused snafus 17–21.

## Context

**Why ddgz was wrong for Rocky 9:**

`ddgz` DDs a pre-built disk image (including partition table) directly to the target
disk. curtin then runs curthooks including GRUB installation. Rocky 9's
`grub2-mkconfig` rejects the path curtin uses (`/boot/efi/EFI/rocky/grub.cfg`) because
Rocky 9 BLS treats that as a wrapper file. This caused snafu-20. The fix was
`grub: {install_devices: []}` + manual `reinstall_grub_removable` late_command.

**Why tgz with `base_image=rhel/9` is correct:**

The official [packer-maas Rocky 9 template](https://github.com/canonical/packer-maas/blob/main/rocky9/README.md)
produces a `tgz` rootfs tarball uploaded with `filetype=tgz base_image=rhel/9`. With
this format:

1. curtin creates its own partition layout (EFI + root)
2. curtin extracts the tarball to the root partition
3. curtin runs RHEL-specific curthooks that use `grub2-install` and
   `grub2-mkconfig -o /boot/grub2/grub.cfg` (the CORRECT Rocky 9 path)
4. No preseed hacks needed for GRUB

**Minimal required preseed changes:**

With tgz deployment, the `partitioning_commands` block must be removed — curtin creates
its own partition layout and mounts EFI itself. If `partitioning_commands` is kept, the
`mount_efi` command (which uses `set -eu`) would fail when curtin has already mounted
EFI.

We keep `grub: {install_devices: []}` + `reinstall_grub_removable` as a safety net
since we can verify GRUB works correctly before removing them.

**Ordering bug fixed incidentally:**

The ordering bug (r < s → `reinstall_grub_removable` runs before
`set_grub_timeout_zero` → grub.cfg gets GRUB_TIMEOUT=30 not 0) is fixed by setting
GRUB_TIMEOUT=0 in the image itself during the customization step. `set_grub_timeout_zero`
is then belt-and-suspenders.

## Open Questions

None — ready to proceed.

## Files to Modify

### `infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/import-rocky-image.yaml` — modify

Key changes:
1. Remove "Mount EFI partition" step (EFI contents not needed in tgz; curtin creates a new EFI partition)
2. Remove "Pre-install GRUB2 to EFI partition" step (`reinstall_grub_removable` handles GRUB at deploy time)
3. Change "Update GRUB config" to set `GRUB_TIMEOUT=0` (was 30) — fixes alphabetical ordering bug
4. Replace "Convert qcow2 → raw" + "Gzip raw image" steps with single "Create rootfs tgz" step
5. Change MaaS import command: `filetype=ddgz` → `filetype=tgz` + `base_image=rhel/9`
6. Update variable names and cleanup

### `infra/maas-pkg/_tg_scripts/maas/configure-region/tasks/templates/curtin_userdata_rocky9.j2` — modify

Remove `partitioning_commands` block entirely (conflicts with tgz deployment — curtin
creates its own partitions and EFI mount; `mount_efi` with `set -eu` would fail).

Keep everything else for now (`grub: {install_devices: []}` + `reinstall_grub_removable`
as safety net). Can be removed once tgz deployment is confirmed working.

### `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/templates/curtin_userdata_rocky9.j2` — modify

Same change as configure-region template (the two are identical).

## Execution Order

1. Update `import-rocky-image.yaml`
2. Update both `curtin_userdata_rocky9.j2` files
3. Annihilate ms01-02 + wipe GCS TF state (existing failed deployment)
4. Re-run `./run -b -w "*maas*"`
   - `pxe.maas.seed-server` wave re-imports Rocky 9 image (tgz this time) + deploys new preseed
   - `maas.lifecycle.new` → commission → deploy → deployed

## Verification

- Import step log shows `filetype=tgz base_image=rhel/9` in the MaaS import command
- No `partitioning_commands` in deployed preseed
- Deployment log shows curtin running RHEL curthooks (grub2-mkconfig path is `/boot/grub2/grub.cfg`)
- `reinstall_grub_removable` runs as belt-and-suspenders
- Machine reaches "Deployed" state and is SSH-accessible
