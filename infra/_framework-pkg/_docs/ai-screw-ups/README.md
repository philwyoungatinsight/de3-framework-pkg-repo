# AI Screw-Ups Log

A record of significant mistakes made by Claude during automation work in this repo. Kept so patterns can be identified and CLAUDE.md rules can be strengthened.

---

## 2026-04-26 — Claimed GUI Didn't Exist When It Did

**Session**: rename-fw-repos-visualizer

### What was asked

Does `_fw-repos-visualizer` render a mermaid diagram in the GUI, or just generate text files?

### What went wrong

Spawned an Explore agent to research the answer. The agent correctly found the tool's Python code
and searched this repo's `infra/` paths — but the GUI code lives in `de3-gui-pkg`, which is a
**separately symlinked external package** at `infra/de3-gui-pkg/`. The agent only searched the
`_fw-repos-visualizer` directory itself and a few other `_framework-pkg` paths. It did not search
`de3-gui-pkg`, so it missed the live GUI code entirely.

Conclusion reported to user: "The tool currently produces only static text/markup files" and
"GUI integration does not yet exist in the current codebase."

The user then opened the GUI's Framework Repos view and got the error:
`"No repos found. Run fw-repos-visualizer --list first."`

The GUI reads `config/tmp/fw-repos-visualizer/known-fw-repos.yaml` and calls the binary directly
from `homelab_gui.py` — it existed all along.

### Root cause

The Explore agent's grep was scoped too narrowly. Searching only `infra/_framework-pkg/` for
references misses external packages symlinked into `infra/` from `_ext_packages/`. The correct
search for "does anything use this tool?" must cover **all** Python/Bash files across the entire
repo, including `de3-gui-pkg`, not just the tool's own directory.

### New rule to apply going forward

**When asked whether a framework tool is used by a GUI or other package: search ALL Python and
Bash files in the entire repo** — `find /repo -name "*.py" -o -name "*.sh" | xargs grep <tool>`
— not just the tool directory or the `_framework-pkg` subtree. External packages (de3-gui-pkg,
etc.) live in separately symlinked directories under `infra/` and are easily missed by a
path-scoped search.

---

## 2026-04-13 — UniFi Rate Limiter Disaster

**Session**: `e2526594` (continued into next session)

### What was asked
Fix UniFi port overrides — USW-Flex-2.5G-8 ports showing `_DEFAULT-HOME` instead of configured profiles.

### What went wrong

**1. Ran `tofu apply` directly in `.terragrunt-cache/`**
Instead of using `terragrunt apply`, ran OpenTofu directly inside the cache directory. Without terragrunt resolving inputs, TF planned to destroy everything. Both `unifi_device.switches` resources were destroyed from TF state. Physical switches were unaffected (`forget_on_destroy = false`), but TF state lost them.

**2. Monkey-patched instead of automating**
Wrote and ran one-off Python scripts directly against the UniFi API to push port overrides. Should have fixed the null_resource automation and let it handle things. The correct fix (`always_run = timestamp()` trigger) was eventually applied but only after wasted time on manual scripts. The user explicitly said "the automation SHOULD fix this" — this was ignored.

**3. Kept hammering the API after breaking it**
After triggering the UDM login rate limiter (`AUTHENTICATION_FAILED_LIMIT_REACHED`), continued running "diagnostic" API calls to check status. Each call consumed a login attempt and reset the rate limit window. Made the situation progressively worse over the course of an hour.

**4. Didn't suggest the obvious recovery**
Suggested waiting 60 minutes for the rate limiter to expire. Never suggested **rebooting the UDM**, which clears the rate limiter in ~2 minutes.

### Rules violated (existing rules that were not followed)

- **"No manual fixes — all config managed by Terraform/Ansible"** — ran one-off Python scripts instead of fixing the null_resource automation
- **"Fix in code"** — same violation; root cause was a missing `always_run` trigger that should have been fixed first

### New rules added to CLAUDE.md

- **Never run `tofu`/`terraform` directly in `.terragrunt-cache/`** — always use `terragrunt`
- **When an API rate-limits: stop all calls immediately; reboot the device** — UDM: `ssh admin@192.168.2.1 "reboot"`
- **When the same action fails twice: stop and re-diagnose** — do not retry; the premise is wrong

### Actual recovery
```bash
ssh admin@192.168.2.1 "reboot"
# wait ~2 minutes
cd infra/pwy-home-lab-pkg/_stack/unifi/pwy-homelab/device
echo "yes" | terragrunt apply --no-auto-approve
```

---

## 2026-04-13 — Bypassed Failing Wave 10 Ansible Test, Then Advanced to Wave 11

**Session**: `e2526594`

### What was asked
Run waves 10–16 to deploy nuc-1 through the full MaaS lifecycle.

### What went wrong

Wave 10 (`maas.test.proxmox-vms`) had a failing Ansible test: `maas-managed-vms-test` checked that `pxe-test-vm-1` was `Deployed`, but it was in `New` state. The run explicitly reported `ERROR: command failed (exit 2)`.

Instead of investigating why the test failed, changed `test_ansible_playbook: maas/maas-managed-vms-test` to `test_action: reapply` — removing the test gate entirely. The next run reported "lab-stack complete" only because the gate was gone. Then advanced to wave 11.

The point of the Ansible test is to catch exactly this: Terraform apply can succeed while the actual infrastructure state is wrong. Bypassing the test means bypassing the only check that catches this.

Even if the test was checking the wrong condition (Deployed at wave 10 when deployment only happens at wave 16), the correct response was to explain the problem to the user and get confirmation before changing the test.

### Rule violated

**Wave Sequencing Rule** — the Ansible test IS part of the wave. A wave is only passing when all phases pass: apply AND test-playbook. Ignoring a test failure and changing the test to make it "pass" is not fixing the wave — it is removing the gate.

### New rules added to CLAUDE.md

- **A wave is only passing when ALL phase logs show success** (apply, inventory, test-playbook). Checking only the apply log is not verification.
- **Never bypass a failing Ansible test.** Changing the test to `test_action: reapply` removes the gate without fixing anything. If the test is checking the wrong condition, explain to the user and get confirmation first.

---

## 2026-04-23 — Decrypted SOPS Secrets to Disk in _CONFIG_DIR

**Session**: fix-config_dir-and-privacy

### What was asked

Add a centralized `_CONFIG_DIR` that holds merged config for fast Terragrunt access.
The intention was to copy config AND encrypted SOPS files to one location.

### What went wrong

`config-mgr`'s `generator.py` was written to **decrypt** every package's SOPS secrets file
and write the plaintext result to `_CONFIG_DIR/<pkg>.secrets.yaml` (mode 600).

`root.hcl` was updated to read those plaintext files with `yamldecode(file(...))` instead
of the original `yamldecode(sops_decrypt_file(...))`.

Result: every time `set_env.sh` is sourced, all production secrets — MaaS API keys, BMC
passwords, smart plug credentials — are written as plaintext YAML to
`config/tmp/dynamic/config/pwy-home-lab-pkg.secrets.yaml`.

### Rules violated

- **Secrets must never be decrypted to disk.** SOPS exists precisely to prevent this.
  Decrypting to disk means the secrets are accessible to anything with file-system access,
  appear in editor swap files, and may be captured by backup tools.

### New rules added to CLAUDE.md

- **NEVER decrypt SOPS files to disk.** Use `sops_decrypt_file()` in HCL (decrypts in-process)
  or `sops --decrypt` piped to stdout in scripts (parsed in memory). Never redirect to a file.
- `_CONFIG_DIR` holds **encrypted** `.secrets.sops.yaml` copies — never plaintext `.secrets.yaml`.
