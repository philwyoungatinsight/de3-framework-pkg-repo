# SOPS consolidation + config file naming convention

## Date
2026-04-08

## Changes

### SOPS config consolidation
- Merged `config/.sops.yaml` into root `.sops.yaml`; `config/.sops.yaml` is now a symlink to `../.sops.yaml`
- Updated `path_regex` from old `config/files/` path to `.*infra/[^/]+/_config/.*\.sops\.yaml$`
- Removed `encrypted_regex` — SOPS now encrypts all values by default
- PGP-only rules (no age) — age key was in archived key file, not active `SOPS_AGE_KEY_FILE`

### Secrets file repair
- 4 packages (maas-pkg, mesh-central-pkg, proxmox-pkg, unifi-pkg) had only an age recipient
  whose private key is in `computer-setup-private/ARCHIVED/age/pwyoung-home-lab/pwy-home-lab.keys.txt`
- Added PGP fingerprints to all 4 via `SOPS_AGE_KEY_FILE=<archived> sops -r -i --add-pgp ...`
- All 7 packages now decrypt via GPG (fingerprint `1FAFFDF2C76C758F736178E2B776DF4CEB6B692B`)

### `verify-encryption.sh` fixed
- Was hardcoded to `config/files` (eliminated); updated to `$_INFRA_DIR`

### `_find_component_config` redesigned
- Was hardcoded to `infra/<pkg>/_config/config.yaml`
- Now: `find "$_INFRA_DIR" -maxdepth 3 -name "${key_name}.yaml" -o -name "${key_name}.sops.yaml" -path "*/_config/*"`
- Removed dead `terragrunt_lab_stack` legacy alias
- Seed scripts (`gcp_seed/run`, `aws_seed/run`, `azure_seed/run`) now call `_find_component_config`

### Config file naming convention enforced
- **Rule:** every config file named after its top-level key — `<key>.yaml` / `<key>_secrets.sops.yaml`
- **Before:** all packages used generic `config.yaml` / `secrets.sops.yaml`
- **After:** `infra/<pkg>/_config/<pkg>.yaml` and `infra/<pkg>/_config/<pkg>_secrets.sops.yaml`
- All 11 packages renamed; all references updated across root.hcl, run, framework/*, scripts/*, tg_scripts, wave_scripts

### GCP seed config created
- `infra/pwy-home-lab-pkg/_config/gcp_seed.yaml` — project, region, auth_method, state_bucket
- `infra/pwy-home-lab-pkg/_config/gcp_seed_secrets.sops.yaml` — billing_id, sa_name
- Seed scripts discover config via `_find_component_config` — no hardcoded package paths

## Key decisions
- `config/.sops.yaml` as symlink keeps the file discoverable from both `config/` and repo root
- No `encrypted_regex` in `.sops.yaml` = encrypt everything; simpler and safer
- Package-name convention means you can move any config file to another `_config/` dir and
  `_find_component_config` finds it by name, regardless of which package owns it
- Creating new sops files: use `EDITOR="cp /tmp/plain.yaml" sops <target>` — works because
  sops edit mode uses the target path for rule matching (bypasses the `/tmp` path_regex mismatch)
