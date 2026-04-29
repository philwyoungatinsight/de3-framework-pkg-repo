# curtin late_commands ordering, GUI flex fixes, Chrome profile picker investigation

## Summary

Fixed two bugs left over from the rocky-9 deploy work: curtin alphabetical key-ordering
for late_commands (the poweroff command was inadvertently sorting before GRUB steps),
and GUI panel-header flex-shrink preventing headers from collapsing in tall panels.
Also investigated why certain Chrome profiles don't appear in the Claude Code terminal
URL picker — found and documented the filter condition and wrote a fix script.

## Changes

- **`infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/templates/curtin_userdata_rocky9.j2`**
  — Renamed `maas:` → `zz_signal_maas:` and `poweroff:` → `zzz_poweroff:`. Curtin
  executes late_commands in alphabetical key order. The plain names `maas` and
  `poweroff` sort before `reinstall_grub_removable`, `set_grub_timeout_zero`, and
  `write_*` commands (r, s, w all sort before z), meaning MaaS was being signaled
  deployed and the machine powered off BEFORE GRUB was reinstalled — causing the
  next boot to fail with missing grub. The `zz_`/`zzz_` prefixes guarantee correct
  ordering: GRUB steps → signal MaaS → power off.

- **`infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py`**
  — Added `flex_shrink="0"` to panel headers in all floating panels and the main
  right panel header, so headers don't shrink when content area is constrained.
  Changed `top_right_panel` content area from `height="100%"` to `flex="1"` +
  `min_height="0"` so it correctly fills remaining space in the flex container
  without overflowing.

- **`scripts/ai-only-scripts/build-watchdog/check`**
  — Extended pgrep pattern from `run --build` to `run --build|run -b ` to also
  detect the `-b` shorthand used by some interactive runs.

- **`scripts/ai-only-scripts/reimport-rocky9/`** (new)
  — Ansible playbook + run script for re-importing the Rocky 9 boot resource into
  MaaS when the existing image is stale or missing customizations. Downloads the
  GenericCloud qcow2, customizes it (grub2-efi, openssh, cloud-init, netplan stub),
  converts to ddgz, and imports via `maas CLI`.

- **`docs/ai-plans/maas-snafu-16.md`** (new)
  — Documents the rocky-9 deploy race (poweroff fix) and double-boot commission
  race (ms01-02 auto-commissioned by enrollment hook while wave was commissioning
  it explicitly → two competing PXE boots → Failed commissioning).

- **`docs/ai-log/20260415221612-rocky9-deploy-poweroff-fix.md`** (untracked)
  — AI log from previous session documenting the poweroff fix.

- **`/tmp/add-google-profiles.linux-only.sh`** (not in repo — one-time fix script)
  — Investigated why only 3 of 8 Chrome profiles appear in Claude Code's terminal
  URL picker. Found that Claude Code reads `~/.config/google-chrome/Local State`
  `profile.info_cache` and filters profiles by:
  `user_name != ''` AND (`is_using_default_avatar == false` OR
  `is_consented_primary_account == false`). Profiles 3/5 showed because they had
  custom avatars (`is_using_default_avatar: false`); Profile 8 showed because it's
  a managed work account (`is_consented_primary_account: false`). Default, Profile 1,
  2, 4 were hidden because both flags were `true`. The fix script updates Local State
  to set `is_using_default_avatar: false` for hidden profiles (making them visible)
  and renames `info_cache.name` to the email address for a recognizable display name.

## Root Cause

**curtin ordering**: Curtin late_command keys sort alphabetically. `maas` < `reinstall_grub_removable` and `poweroff` < `reinstall_grub_removable` — so MaaS was being signaled complete and the machine was powered off before GRUB was reinstalled on the EFI partition.

**GUI flex**: Panel headers inside flex containers weren't marked `flex_shrink: 0`, so the browser could shrink them when vertical space was constrained. Content area `height: 100%` doesn't work inside a flex parent without `min_height: 0` (percentage height ignores flex parent bounds).

**Chrome picker filter**: Claude Code uses the picker visibility filter `is_using_default_avatar && is_consented_primary_account` to determine which profiles to hide — profiles with generic avatars that have completed the Google account consent flow are hidden.

## Notes

- The curtin late_commands ordering bug would have caused the rocky-9 deploy to fail
  on the SECOND deploy attempt (first attempt powered off, machine would boot to
  emergency GRUB prompt on next AMT power-on). The poweroff fix from the previous
  commit would have masked this — the machine powers off cleanly but GRUB would be
  wrong on disk.
- For Chrome picker: closing Chrome before running the fix script is mandatory — if
  Chrome is open, it overwrites Local State when it exits, reverting the changes.
  The `"playwright"` option in the picker comes from `~/.cache/ms-playwright/chromium-*`
  (Playwright's Chromium install), which Claude Code detects independently of Chrome
  profile enumeration.
