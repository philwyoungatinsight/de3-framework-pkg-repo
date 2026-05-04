# Read This First

**At the start of every session, read `infra/_framework-pkg/_docs/ai-screw-ups/README.md`.** It documents recurring mistakes made by Claude in this repo. Do not repeat them.

# ⚠️ The Goal Is Results *via Automation*  ⚠️

**The goal is ALWAYS for the automation to succeed — not to manually produce the desired end state.**

- A working switch config produced by hand is a failure. A working switch config produced by `./run --build` is success.
- If automation is broken: fix the automation. Do not work around it.
- Do not suggest or perform manual steps to achieve what automation should do. If automation can't do it, fix automation first.
- The only permitted manual steps are one-time physical setup (racking hardware, plugging cables) and one-time credential/permission bootstrapping that cannot itself be automated.
- If a temporary manual task is required, make an ai-only script and run it manually.
- This will ensure that we can more easily automate the one-off task if necessary.

# ⚠️ STOP-FALLING-ASLEEP-AT-THE-WHEEL — HIGH PRIORITY ⚠️

**Never let a long-running operation fail silently. Check every gate immediately. Fix failures without waiting for the user.**

- After EVERY gate or wave, immediately check the next gate — do NOT use background polling if you need to react
- When a gate fails: read the error, diagnose root cause, fix code, commit, kill build, restart — all without waiting for user prompt
- Every ~5 minutes during a long run: output a status line (current wave, gates passed, what's next)
- Before restarting any build: check for stale GCS locks (`grep 'default.tflock' /tmp/run-maas.log`) and clear them
- This rule takes priority over waiting for user confirmation on build failures

# ⚠️ Stop Being Lazy ⚠️

**Never wait passively or tell the user to wait more than 5 minutes.**

- **Poll aggressively**: check state every 10–30s, log every check, act the instant state changes
- **No passive sleeps**: do not go silent for minutes at a time — the user is watching and wasting time
- **Timeouts > 5 min (300s) are config parameters**: extract to `_<RESOURCE>_WAIT_TIMEOUT` env var or YAML key immediately — hardcoding a long wait is a bug
- **If you're about to say "wait X minutes"**: stop, write a polling loop instead, and check it yourself

# ⚠️ NEVER Override Config in MaaS ⚠️

**Never use `maas machine update` to change `power_type`, `power_parameters`, or any other field that is set by Terraform from YAML config.**

- `power_type` and `power_parameters` are set ONCE at enrollment by the `maas_machine` Terraform resource. They must never be changed by scripts, playbooks, or any automation after that point.
- Config is the source of truth. Changing MaaS state to differ from config is a bug, not a fix.
- The ONLY legitimate `maas machine update` calls are: `osystem`/`distro_series` at deploy time (MaaS provider v2.7.2 limitation — provider cannot set osystem in deploy_params).
- Permitted MaaS API calls: `commission`, `allocate`, `deploy`, `release`, `abort`, `delete`, `power-on`, `power-off`. These are lifecycle transitions, not config overrides.

# ⚠️ Delete-Automate-Recreate — No Direct State Manipulation ⚠️

**Rule: delete-automate-recreate-no-manual-update**

When infrastructure gets into a broken or unexpected state: **delete it and let the automation recreate it**. Do not patch internal state directly. Do not monkey-patch. Do not work around a broken state — fix the root cause.

**Never:**
- Edit postgres/database tables directly (`psql maasdb -c "UPDATE maasserver_node..."`, `UPDATE maasserver_bmc...`)
- Manually force MaaS machine status by writing `status=4` (Ready), `status=6` (Deployed), `power_state='off'` etc. to the DB
- Monkey-patch TF state or cloud resource internals to work around a broken state
- Run one-off scripts to push config that automation is supposed to manage

**Instead:**
- Use the MaaS CLI API: `maas machine release`, `maas machine abort`, `maas machine commission`, `maas machine update`, `maas machine delete`
- Use `tofu state rm` to remove stale TF resources, then let automation re-create them
- Fix the root cause in automation code so the state never gets broken in the first place
- If a machine is stuck: delete it from MaaS (`maas machine delete <id>`), remove its TF state, and re-run the wave — the auto-import hook and commission-and-wait.sh handle re-enrollment from scratch

# ⚠️ SOPS — CRITICAL RULES ⚠️

**NEVER decrypt SOPS files to disk.** Secrets must stay encrypted at rest.
- Terragrunt/HCL: use `sops_decrypt_file(path)` — decrypts in-process, nothing written to disk
- Python/shell: `sops --decrypt <file>` piped to stdout, parsed in memory — never redirect to a file
- `_CONFIG_DIR` holds **encrypted** `.secrets.sops.yaml` copies — NEVER `.secrets.yaml` plaintext copies
- `config-mgr generate` copies SOPS files unchanged; it does NOT decrypt them

NEVER use shell redirect (`>`), `tee`, or the Write/Edit tools on `.sops.yaml` files — they truncate the file before writing.

```bash
# Interactive (full file):
sops "$SOPS_FILE"

# Programmatic (single key — example for maas-pkg):
sops --set '["maas-pkg_secrets"]["providers"]["maas"]["config_params"]["<path>"]["<key>"] "<value>"' "$SOPS_FILE"
sops --extract '["maas-pkg_secrets"]["providers"]["maas"]["config_params"]["<path>"]["<key>"]' "$SOPS_FILE"

# Create from scratch (ONLY if file is truly absent):
cat > /tmp/new.yaml << 'EOF'
maas-pkg_secrets:
  key: value
EOF
sops --encrypt --output "$SOPS_FILE" /tmp/new.yaml   # --output is atomic; never use >
rm /tmp/new.yaml
```

`SOPS_FILE="$_INFRA_DIR/_framework-pkg/_config/_framework-pkg_secrets.sops.yaml"`  (if it exists)
`SOPS_FILE="$_INFRA_DIR/<pkg>/_config/<pkg>_secrets.sops.yaml"`                    (per-package secrets; key: `<pkg>_secrets`)

# Why Use Framework Tools (Not Equivalent Shell Commands)

**Always call framework tools (`sops-mgr`, `pkg-mgr`, `unit-mgr`, etc.) instead of their underlying shell equivalents (`sops updatekeys`, `pip install`, etc.).**

- **Traceability**: every SOPS re-encryption in the repo is discoverable by `grep -r sops-mgr`. If you call `sops updatekeys` directly, that call is invisible to auditors, key-rotation reviewers, and future automation.
- **Single source of truth**: improvements (dry-run, logging, error formatting) land once in the tool and propagate to all callers automatically.
- **Consistency**: the framework tool enforces the correct flags, file-discovery scope, and error-exit behaviour — re-implementing these inline invites divergence.

This rule applies whenever a framework tool exists for the operation you need. Do not inline the equivalent shell command "for simplicity" — the cost is invisible operations.

# Primary Goal

**`make clean-all && make` MUST restore the full infrastructure without manual intervention**

# ⚠️ NEVER Destroy or Bypass a Test ⚠️

**When a `test_ansible_playbook` fails: fix the infrastructure. NEVER change the test to make it pass.**

Changing a failing `test_ansible_playbook` to `test_action: reapply`, removing the test, or weakening its assertions does not fix the wave — it removes the only check that caught the real problem. This is worse than doing nothing: the infrastructure is broken AND the signal is gone.

The test exists precisely because Terraform apply can succeed while the actual infrastructure state is wrong. A failing test IS the finding. Work backwards from it to the root cause.

**If and only if the test is genuinely testing the wrong condition** (e.g. it checks `Deployed` at a wave where `Deployed` is not expected): stop, explain the problem clearly to the user, propose what the test SHOULD check at this wave, and wait for confirmation before touching the test.

Under no circumstances change a test to make a wave "pass" without user confirmation.

# Wave Sequencing Rule — Fix Before Advancing

**When running `make clean` or `make`, each wave MUST succeed before working on the next wave.**

- If wave N fails, stop and fix wave N. Do NOT attempt to work on, investigate, or skip ahead to wave N+1 or later.
- Diagnosing the root cause of a wave failure is the only permitted work until that wave passes.
- Do not attempt `make` (build) until `make clean` has run to completion without errors.
- If a Terragrunt `run --all` reports errors from units belonging to multiple waves in a single log file, treat all of them as wave N errors — do NOT treat later-wave errors as a reason to move on. Fix them all at the wave N level before re-running.
- **A wave is only passing when ALL phase logs show success**: apply log, inventory log, AND test-playbook log. Checking only the apply log and ignoring a failing test-playbook log is not verification — it is ignoring the failure. Wave logs are in `~/.run-waves-logs/latest/` — there will be a separate file for each phase (`wave-<name>-apply.log`, `wave-<name>-test-playbook.log`, etc.).

`make clean` ≠ `make clean-all`:
- `make clean` (`./run --clean`): Terraform destroy in reverse wave order; honours `_skip_on_wave_run` on waves — some waves (e.g. `cloud.k8s`, `network.unifi`) are intentionally skipped. Unit-level `_skip_on_wave_run` is not supported (Terragrunt single-exclude-block limitation; use wave-level instead).
- `make clean-all` (`./run --clean-all`): nuclear — destroys ALL resources; sets `_FORCE_DELETE=YES` which root.hcl reads to disable all `exclude` blocks, so `_skip_on_build` units are destroyed too; pre-purges Proxmox VMs and GKE clusters via direct API/gcloud; then wipes the entire GCS state bucket.

Never import resources or manually delete cloud objects to recover from a failed `make clean-all`. Fix the automation instead. (after one-time physical hardware setup per machine). Every automation step must be designed so a clean run produces a fully operational lab.

If a resource cannot be auto-created and destroyed, it is not done — fix the root cause.  
Known exceptions: `infra/_framework-pkg/_docs/idempotence-and-tech-debt.md`

# framework_repo_manager.yaml — Example Entries Must Be Commented Out

**Every entry in `framework_repos:` must represent a real, existing repo — never an example placeholder.**

The fw-repos-diagram-exporter reads ALL uncommented `framework_repos` entries and treats them as real repos (attempts to clone, draws nodes in the diagram). An uncommented example like `my-example-repo` will appear in the diagram as a phantom repo.

- Before adding a new entry, create the actual repo first.
- Keep example/template entries commented out until they are ready to use.
- This applies to every `framework_repo_manager.yaml` across all packages in this repo.

# No Hard-Coded Values — Config Is the Source of Truth

Never hardcode IPs, hostnames, ports, paths, node names, VM IDs, CIDRs, versions, or credentials in `.hcl`, Ansible tasks, scripts, or templates. Every deployment-specific value comes from YAML config.

- **Terragrunt**: values from `include.root.locals.unit_params`. Use `try(local.up.<key>, "")` for optional fields — never fall back to a real infrastructure value.
- **Ansible**: values from `config_base`-loaded YAML facts. Discover resources dynamically by tag or `_wave` — never hardcode paths like `proxmox-pkg/_stack/proxmox/pwy-homelab/pve-nodes/pve-1`.
- **Provider templates**: construct provider-specific strings (e.g. `PVEAPIToken=...`) in `.tpl` files; `root.hcl` passes only generic vars (`API_TOKEN`, `ENDPOINT`, etc.).
- **Scripts** (`tg-scripts`, `wave-scripts`, `ai-only-scripts`): filter `config_params` by property, never hardcode unit paths.
- **`default()` / `try()`**: safe no-op fallbacks only (`""`, `null`, `[]`). Never `default('10.0.10.11')` or `default('pve-1')`.
- **HCL `try()` defaults are fallbacks, not config**: Every meaningful unit input must be explicitly set in `config_params` YAML. HCL `try(local.up.<key>, <value>)` is a safety net only — the YAML is the source of truth and must be complete enough to read without consulting the HCL. Exception: `machine_name` / `name` derived from the unit directory name (correct by construction). Exception: truly-empty optional fields that are always empty for this unit (e.g. `provisioning_ip: ""` on a unit that never uses a static provisioning IP). All other values — OS, user, distro, power type, port, erase flag — must be in YAML.
- **`_extra_providers`**: quote YAML reserved words: `["null"]` not `[null]`.
- **Kubeconfig**: write per-cluster to `$_DYNAMIC_DIR/kubeconfig/<name>.yaml`. Never merge into `~/.kube/config` or the framework shared kubeconfig.
- **`_browser_url`**: always keep active on units with a web UI — read by `de3-gui-pkg`. Never remove or comment out.
- **`common_tags` on every taggable resource**: all Terraform modules MUST accept and apply `common_tags` (map) or `common_tags_list` (list) from `root.hcl`. Cloud resources (AWS, GCP, Azure) use `common_tags` as `tags`/`labels`. Proxmox VMs use `common_tags_list` (flat string list) as `tags`. Providers that don't support tags (MaaS, UniFi, null) are exempt. Never hardcode tag values — always source from `include.root.locals.common_tags` or `include.root.locals.common_tags_list`.

# Script Placement

New scripts MUST go in the correct directory — wrong placement is a bug.

**Decision (check in order):**
1. AI-generated / diagnostic / one-off fix → `infra/_framework-pkg/_scripts/ai-only/`
2. Terragrunt calls it directly (`before_hook`/`after_hook`/`local-exec`) → `infra/<pkg>/_tg_scripts/<role>/<name>/run`
3. Wave hook (`test_ansible_playbook`/`pre_ansible_playbook` in YAML) → `scripts/wave-scripts/default/test-ansible-playbooks/<role>/<name>/`

**Pre-wave playbooks** (`pre_ansible_playbook`): primarily CHECK conditions and FAIL CLEARLY. Failure message must say what needs to happen (e.g. "re-run on_prem.maas.machines first"). Exception: idempotent state normalization that is a mechanical precondition for the wave is permitted — e.g. aborting machines stuck in transitional MaaS states (Commissioning/Deploying) or releasing Allocated machines so the wave can re-deploy them. This is different from orchestration: normalization returns machines to a clean baseline state; the wave itself then runs the full lifecycle. Do not add arbitrary recovery logic or multi-step orchestration.

**Wave hooks**: must be Ansible playbooks. `pre_shell_script`/`test_shell_script` are removed; do not add new ones.

**No hardcoded config values in test-ansible-playbooks**: discover units by `_wave` or tag; read ports from YAML; use `hostvars['localhost']` to pass config-derived values between plays.

# Ad-hoc Maintenance Scripts

Create Ansible playbooks in `infra/_framework-pkg/_scripts/ai-only/<task-name>/` for any operational task. Never run raw SSH commands.

- Structure: `playbook.yaml` + `run` (sources `set_env.sh`, uses `_activate_ansible_locally`)
- Config from `config_base` YAML (Play 1 on localhost → Play 2 on remote host using `hostvars['localhost']`)
- File paths: absolute from `GIT_ROOT="$(git rev-parse --show-toplevel)"` — no relative paths
- Export env vars from `run`; use `lookup('env', '_VAR')` in playbooks

**Existing scripts (check before writing new ones):**
- `check-maas-machines` — machine status; `MAAS_FILTER_HOST` to filter. In `infra/maas-pkg/_wave_scripts/common/`.
- `sync-maas-api-key` — tg-script at `infra/maas-pkg/_tg_scripts/maas/sync-api-key`; fixes 401 on MaaS provider.
- `query-unifi-switch` — live switch port data (link speed + MAC table). In `infra/_framework-pkg/_scripts/ai-only/query-unifi-switch/`. Use `SWITCH_FILTER=Flex ./run` to filter by switch name. **Use this instead of one-off curl commands whenever you need to know which NIC/MAC is on which switch port.**

# ⚠️⚠️⚠️ NEVER MONKEY-PATCH MAAS STATE ⚠️⚠️⚠️

**When a MaaS machine is stuck, do NOT change its state to help it along. That masks the bug.**

**FORBIDDEN — these are monkey-patches:**
- `maas machine update <id> power_type=...` — changes config-managed fields
- `maas machine abort <id>` / `maas machine release <id>` — forcing a state transition by hand
- `maas machine power-on <id>` / `maas machine power-off <id>` — manually cycling power to unstick
- Any direct DB write to change `status`, `power_state`, etc.

**The correct response when a machine is stuck:**
1. **Diagnose first**: read the logs, understand WHY it is stuck. The machine is a symptom; the bug is in the automation code.
2. **Fix the automation**: change the script/module/gate that caused the machine to get stuck.
3. **Annihilate the machine** to reset to a clean slate: `maas machine delete <id>` + remove its GCS TF state files
4. **Re-run the wave** — if the automation fix is correct, the machine will reach the target state on its own.

**Annihilation is the cleanup after a fix, not the first response.** Skipping diagnosis means the same bug will recur on the next machine or the next build.

**Why this rule exists:** Every monkey-patch hides the bug and creates a false impression of progress. After each patch the machine is "unstuck" but the automation is still broken. The only way to know the automation works is to delete the machine and let automation rebuild it from scratch without any manual intervention.

# MaaS Recovery

**The answer is always: `maas machine delete <id>` + `tofu state rm` + re-run the wave.**

Do not manually release, commission, abort, or otherwise poke machine state — that is bypassing automation. See `infra/maas-pkg/_docs/maas-recovery.md` for CLI reference if you need to perform the delete step.

# MaaS Snafu Tracking — Mandatory

**Every MaaS automation fix requires a new numbered plan: `infra/pwy-home-lab-pkg/_docs/ai-plans/maas-snafu-N.md`.**

- Before writing any MaaS fix: check the highest existing snafu number in `infra/pwy-home-lab-pkg/_docs/ai-plans/` and `infra/pwy-home-lab-pkg/_docs/ai-plans/archived/`. Increment by 1.
- The plan documents: what broke, what was fixed, what the remaining gaps are, and any open questions.
- Commit the plan with the fix (or immediately after if the fix is urgent).
- This is how we track the accumulating MaaS hell and avoid fixing the same thing twice.

# ⚠️ Smart Plug — Bounce the Plug Any Time a Machine Is Stuck ⚠️

**Whenever a smart_plug machine shows no activity — at ANY phase of the MaaS lifecycle — bounce the plug immediately. Never wait passively. Never ask for physical intervention.**

This applies at enrollment, commissioning, deploying, or any other phase where the machine should be active but isn't:
- No DHCP / no network activity after ~90s → bounce the plug (off → 10s → on)
- Switch port DOWN → bounce again immediately
- Machine stuck in Commissioning/Deploying/New with `power_state: off` → bounce the plug
- MaaS shows machine as New/Failed/unreachable when it should be progressing → bounce the plug
- **"Power on after AC loss" is always set** on smart_plug machines — bouncing WILL start the machine
- Keep bouncing every 90s until the machine shows activity or total timeout expires
- Automated in `auto-import/run` via `_MAAS_PLUG_BOUNCE_INTERVAL` (default 90s)
- When Claude observes this situation directly: `curl -X POST http://10.0.10.11:7050/power/off?host=<plug_ip>&type=kasa` then on

# AMT + Smart Plug — Role Separation (Critical)

**Smart plug = restore AMT standby power. AMT = tell the machine what to boot.**

Never bypass AMT with a raw plug cycle. A plain plug cycle boots whatever BIOS says
(possibly GRUB on disk). AMT issues the PXE boot override that puts the machine into
the commissioning or deployment environment.

`mgmt_wake_via_plug: true` means the machine loses AMT standby power when fully off.
Bouncing the smart plug restores AC power → AMT wakes up → wsman can then set the PXE
boot override as normal. The smart plug's only job is to get AMT working; AMT's job is
to tell the machine what to boot. Without AMT, a plug cycle just boots whatever BIOS says.

The correct pattern when AMT is unreachable and `mgmt_wake_via_plug: true`:
1. Bounce the smart plug (off → 10s → on) to restore standby power
2. Poll AMT port 16993 for up to 120s
3. AMT responds → MaaS uses AMT normally (wsman sets PXE boot override + power cycle)
4. If AMT still unreachable after bounce → report BMC state via smart plug as fallback

This applies to ALL automation touchpoints:
- Gate playbooks: extend AMT standby restore to run at `commissioning:pre` and `deploying:pre`
- Precheck: if AMT wsman fails → cycle plug as last resort (machine has no OS yet, PXE is fine)
- BMC state query: if AMT unreachable after bounce → query smart plug for power state

If a machine's AMT is **permanently broken** (never responds after bounce): change its
`power_type` to `smart_plug` in config. Do NOT leave it as `power_type: amt` and work
around it in the gate — the proper fix is the config change.

# Terragrunt — Never Run tofu/terraform Directly

**Never run `tofu` or `terraform` directly inside `.terragrunt-cache/`.** Always use `terragrunt apply`, `terragrunt plan`, etc. from the unit directory. Running tofu directly in the cache bypasses terragrunt input resolution — variables are empty, TF plans to destroy everything, and state gets corrupted.

# API Rate Limiting — Stop and Reboot

**When an API returns rate-limit errors, stop making ALL calls immediately.** Do not make further calls to "check" status — each one resets the window and makes recovery slower.

- **UDM (UniFi)**: `ssh admin@192.168.2.1 "reboot"` — clears the login rate limiter in ~2 minutes. Never suggest waiting an hour.
- **General rule**: identify the hardware or service causing the rate limit, reboot it, then proceed with one clean attempt.

# Repeated Failure — Stop and Re-diagnose

**When the same action fails twice in a row, stop.** Do not retry. Repeated identical failures mean the premise is wrong. Re-read the error, re-examine assumptions, then fix the root cause before trying again.

# Autonomous Debugging

When the user says "resume debugging" or "work until it succeeds": proceed through the full fix-and-retry loop WITHOUT asking for approval at each step. Read logs → diagnose → fix code → re-run → repeat until success. Commit fixes and write ai-log entries as you go. Only stop if a truly out-of-scope destructive action is required (e.g., `make clean-all` when only `make` was authorized).

**Status updates**: When running long-running operations (MaaS commissioning/deployment, wave runs, Ansible plays), output a brief status summary every ~5 minutes: what is running, current state, and what to expect next. Do not wait silently.

# Self-Correction

When a rule is missed (user points out a wrong path, skipped log, etc.):
1. Fix the immediate problem
2. Propose a concrete CLAUDE.md change that would have prevented it
3. Apply the confirmed change and commit with an ai-log entry

# Terraform DAG Dependencies

Wave ordering is the primary sequencing mechanism, but Terraform `dependencies` blocks are a secondary mechanism that must be kept correct. **Stretch goal: the codebase should remain operable with `terragrunt run --all` (no wave filtering) as a secondary execution mode.**

Rules:
- **Never hardcode individual unit lists** in `dependencies { paths = [...] }` — e.g. listing every machine name or VM path. If the list can grow or shrink, it is a hardcoded deployment value, which is banned.
- **Use aggregating units** instead. An aggregating unit (e.g. `configure-physical-machines`) depends on all the members; downstream units take a single dep on the aggregating unit. Adding/removing a machine requires no change to downstream deps.
- **`dependencies` must reflect real ordering**. If unit B cannot run before unit A, declare it. Don't rely solely on wave order — explicit Terraform deps survive `terragrunt run --all` without the wave runner.
- The wave system and explicit `dependencies` are complementary, not alternatives. Correct both when adding or removing units.

See `infra/_framework-pkg/_docs/framework/waves.md#terraform-dag-vs-wave-ordering` for full explanation.

# Build and Automation Rules

- **Block and fail in build path**: never silently skip or warn when a step fails. Poll with `wait_for_condition` up to the configured timeout. In destroy/clean paths, best-effort (`|| true`) is acceptable.
- **No manual fixes**: all config managed by Terraform/Ansible. Manual changes are not idempotent and will be overwritten on the next `./run --build`. Trace failures to root cause in code.
- **Fix in code**: wrong value → fix YAML; missing step → add to playbook or `run` script; race → fix polling/wait logic.
- **No `_maas_reachable`-style pre-flight skips** in build stages. Let the actual step fail with a meaningful error.
- **Cloud-init over MaaS-specific config**: use standard cloud-init directives (`packages:`, `runcmd:`, `write_files:`, `users:`, etc.). Curtin `late_commands` only for things that MUST happen before first boot.

# Conventions

- **GNU argument style**: all scripts must use `-a|--long-arg` GNU convention for CLI arguments — no positional subcommands. Running a script with no arguments must print usage to stderr and exit 1. Bash scripts: use a `while case "$1" in ... esac; shift; done` manual loop (not `getopts`, which doesn't support long args; not `getopt`, which isn't portable to macOS). Python scripts: use `argparse` with `add_argument('-a', '--long-arg', ...)`. Short arg is a single letter, long arg is the descriptive name. Always add `-h|--help`.
- **Script naming — `run` only when Makefile present**: name the entry-point script `run` only when a sibling `Makefile` exists in the same directory (Makefile targets call `./run`; renaming breaks `make`). For all other scripts — utility tools not called by `make` — use a descriptive name matching the tool directory (e.g. `pkg-mgr`, `unit-mgr`, `config-mgr`, `ramdisk-mgr`, `clean-all`). This makes tools discoverable via `find . -name pkg-mgr`. Exceptions that keep `run`: per-package framework hooks (`infra/<pkg>/_clean_all/run`, `infra/<pkg>/_tg_scripts/…/run`, `scripts/wave-scripts/…/run`) because the framework discovers them by that conventional name.
- **set_env.sh**: always `source $(git rev-parse --show-toplevel)/set_env.sh` before running terragrunt. Do NOT change existing variables.
- **State backend**: NEVER change to local. Diagnose and fix the actual problem.
- **Config files**: one top-level key matching the package name (public: `<pkg>`, secrets: `<pkg>_secrets`). Package config lives in `infra/<pkg>/_config/config.yaml` and `infra/<pkg>/_config/secrets.sops.yaml`. No `.cfg` files.
- **Logging (ai-log)**: write ai-log BEFORE committing. If commit made without log, write as follow-up immediately. File: `infra/pwy-home-lab-pkg/_docs/ai-log/$(date +%Y%m%d%H%M%S)-<short-description>.md`.
- **Package version history**: whenever code in a package changes, bump `_provides_capability` in `infra/<pkg>/_config/<pkg>.yaml` and append an entry to the peer file `infra/<pkg>/_config/version_history.md`. Format:
  ```markdown
  ## <new-version>  (<YYYY-MM-DD>, git: <short-sha>)
  - <one-line description of what changed>
  ```
  The `/ship` skill and any commit that touches package code must include this update. Use `git rev-parse --short HEAD` for the sha (taken after the commit). Bump patch for bug fixes, minor for new features, major for breaking changes. Create `version_history.md` if it does not yet exist in the package's `_config/` directory.
- **Planning (ai-plans)**: for non-trivial multi-file changes, use `/ai-plan <task>` to research and write a plan to `infra/pwy-home-lab-pkg/_docs/ai-plans/<task-name>.md` BEFORE coding. `/ai-plan` always stops after writing the plan — it never executes code. Plan file format: files to create/modify, design decisions, exact code strategy. Commit the plan, surface open questions, then wait for user confirmation.
- **Finding ai-plans**: plan names are unique across all packages. When looking up a plan by name, search ALL packages: `find infra -path "*/_docs/ai-plans/<name>.md"`. Never assume a plan lives only in `infra/pwy-home-lab-pkg/_docs/ai-plans/`.
- **Executing ai-plans — always use `/doit <plan-name>`**: When the user confirms open questions and says to proceed (e.g. "yes to all"), ALWAYS invoke `/doit <plan-name>` rather than executing inline. This ensures the plan is properly archived (`ai-plans/archived/`) and the `/ship` step runs. Never execute a plan by coding directly — that leaves the plan file behind unarchived.
- **Diagnose from logs first**: wave logs at `~/.run-waves-logs/latest/` — `run.log`, `wave-<name>-apply.log`, `wave-<name>-test-playbook.log`. Never re-run when output already exists in logs.
- **SSH as ubuntu → always sudo for root-owned paths**: `ubuntu` gets "No such file or directory" (not "Permission denied") for root-owned 0700 dirs. Always use `sudo ls`, `sudo stat`, `sudo cat` when checking `/var/snap/`, `/root/`, or other root-restricted paths. `ansible.builtin.copy` with `remote_src: true` also fails on 0700 dirs — use `ansible.builtin.shell: cp` instead.
- **SSH must always bypass known_hosts**: ALWAYS use `-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null` together. `StrictHostKeyChecking=no` alone still blocks on CHANGED keys (happens after every MaaS server rebuild). Applies to: Bash tool SSH calls, Python subprocess SSH, any new script or playbook that SSHes directly. (Ansible ansible.cfg already has both in `ssh_args`.)
- **MaaS machines need jump box**: provisioning VLAN (10.0.12.0/24) is NOT routable from the developer machine. SSH to MaaS machines via `ssh -J ubuntu@10.0.10.11 ubuntu@<machine-ip>`. Ansible inventory auto-injects the jump box for all MaaS machines — never set `ansible_host` to a 10.0.12.x IP.
- **Bash polling**: always use `wait_for_condition "desc" "cmd" TIMEOUT_VAR default_secs interval_secs` from `infra/_framework-pkg/_framework/_utilities/bash/framework-utils.sh`. Never write raw `while/sleep` loops. Default 300s; use -1 when human action required. Env var: `_<RESOURCE>_WAIT_TIMEOUT`.
- **Timeouts over 5 minutes MUST be config parameters**: Any hardcoded wait or timeout exceeding 300s is a bug. Extract it to a named env var (`_<RESOURCE>_WAIT_TIMEOUT`) or YAML config key immediately. There should be almost no legitimate reason for a static >5 min wait in code.
- **Poll aggressively — never sleep passively**: When waiting for state to change (MaaS commissioning, VM boot, API recovery, etc.), poll at the shortest reasonable interval (10–30s) and log each check. Do NOT tell the user "wait 20 minutes" and go silent — check state actively, report it, and act the moment it changes. Passive sleeps waste tokens and user time.
- **No absolute symlinks**: All symlinks — committed or otherwise — must use relative paths. Absolute symlinks (`/home/user/...`) break on any machine other than the creator's. When creating symlinks in scripts: compute a relative path with `os.path.relpath(target, symlink_dir)` (Python) or equivalent. `pkg-mgr` enforces this for `_ext_packages/` — never override it with a hardcoded absolute path.
- **Labels**: `a-z`, `0-9`, `-`, `_` only.
- **Terragrunt `run --all`**: `terragrunt run --all apply --non-interactive` — auto-approve is the default. Do NOT pass `--auto-approve`. Use `--no-auto-approve` to suppress.
- **`_FORCE_DELETE=YES`**: skips the destructive-action prompt. Only set when an outer script has already confirmed. Never set without user confirmation.
- **YAML reserved words as keys**: `"null":`, `"true":`, `"false":` must be quoted or HCL `yamldecode` fails.
- **Mac/Linux compat**: avoid `mapfile`/`readarray` (Bash 4+, unavailable on macOS). Use `while IFS= read -r` loops.
- **Never use the `timeout` command**: not available on macOS. Use a background process + kill pattern instead: `cmd & PID=$!; sleep N; kill $PID 2>/dev/null; wait $PID 2>/dev/null || true`. For polling loops that need a deadline, use `wait_for_condition` (bash) or a `time.time()` loop (Python).
- **No out-of-repo path fallbacks**: scripts must never fall back to `$HOME`, `~`, or `/tmp` for state files, logs, or markers. If an env var like `_GUI_DIR` or `_WAVE_LOGS_DIR` is unset, fail loudly with an error — do not silently write outside the repo. Exception: `$HOME/.ssh`, `$HOME/.sops`, `$HOME/.aws` reads (user credentials, intentional).
- **No AI/Claude hooks**: automation must work without them.
- **README.md**: update when making code changes in a directory that has a Makefile. Describe how the code works; do not narrate changes.
- **README style**: bullet lists for procedural steps; non-obvious details in linked appendix sections; keep the main Steps section short.
- **Package docs**: every package stores its documentation in `infra/<pkg>/_docs/`. No README at the package root — use `_docs/README.md` instead.
- **infra config**: component-specific config belongs in provider units under `infra/`, not in generic top-level sections.
- **`_skip_FOO` params**: use `_skip_on_build: true` (inherited) to disable example subtrees (set at ancestor path; children inherit). To skip a wave during both build and clean, use `_skip_on_wave_run: true` on the **wave definition**. **`make clean-all` ignores ALL skip flags** — no exceptions. See `infra/_framework-pkg/_docs/framework/skip-parameters.md`.
- **`_skip_on_build` evaluatability requirement**: Terragrunt evaluates ALL unit `locals` during dependency-graph discovery, BEFORE applying exclude blocks. A unit whose config crashes during evaluation will fail the entire wave even if it has `_skip_on_build: true`. Therefore: any unit subtree marked `_skip_on_build: true` MUST also provide all config values required for its units' `try()` fallbacks to evaluate without crashing. Typically this means setting dummy values (`project_prefix: example`, `_env: example`, `_region: <region>`) at the ancestor level so that string-interpolation fallbacks succeed.

# Network IP Scheme

`10.0.<VLAN-ID>.x` — third octet always equals the VLAN ID. Any deviation is a bug.

| VLAN ID | Name | Subnet |
|---------|------|--------|
| 10 | cloud_public | 10.0.10.0/24 |
| 11 | management | 10.0.11.0/24 |
| 12 | provisioning | 10.0.12.0/24 |
| 13 | guest | 10.0.13.0/24 |
| 14 | storage | 10.0.14.0/24 |

# Reference

- Known pitfalls and fixes: `infra/_framework-pkg/_docs/known-pitfalls.md`
- Packer details (auth, boot timing, ISO pre-download, Rocky/Ubuntu quirks): `infra/image-maker-pkg/_docs/README.md`
- Idempotence tech-debt: `infra/_framework-pkg/_docs/idempotence-and-tech-debt.md`
- Package docs: `infra/<pkg>/_docs/` — every package has a `_docs/` directory; no README at the package root.
- Framework tool locations: `infra/_framework-pkg/_framework/` — `_ramdisk-mgr/`, `_generate-inventory/`, `_unit-mgr/`, `_pkg-mgr/`, `_clean_all/`, `_utilities/`
- Framework config: `infra/_framework-pkg/_config/framework.yaml`, `waves_ordering.yaml`, `framework_packages.yaml`
