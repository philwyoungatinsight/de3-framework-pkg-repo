# sops-mgr — SOPS Secrets File Manager

## Purpose

`sops-mgr` is the framework tool for maintaining the encrypted secrets files
(`*.sops.yaml`) that live under `infra/`.  It is used by both humans (for key rotation,
onboarding, and verification) and automation (`fw-repo-mgr`, after writing `.sops.yaml`
into a generated repo).

---

## Commands

### `sops-mgr --re-encrypt`

Re-encrypts every `*.sops.yaml` file using the key recipients declared in the nearest
`.sops.yaml` key-config file.

**When to use:**

- **Key rotation** — after adding or removing a GPG or age recipient in `.sops.yaml`,
  run `--re-encrypt` so all existing secrets files are re-encrypted to the new key set.
  Without this, old files remain readable only by the old key holders.
- **New developer onboarding** — after adding a new team member's public key to
  `.sops.yaml`, re-encrypt so they can decrypt existing secrets.
- **Key revocation** — after removing a departed team member's key from `.sops.yaml`,
  re-encrypt to ensure their key can no longer open any file.

Uses `sops updatekeys --yes` internally, which re-encrypts in place without ever
writing plaintext to disk.

### `sops-mgr --verify`

Test-decrypts every `*.sops.yaml` file to confirm the active key (age/GPG/KMS) can
open each one.  Decrypted content is discarded — plaintext is never written to disk.

**When to use:**

- After key rotation or any change to `.sops.yaml`, to confirm all files are still
  accessible with the new keys.
- When `validate-config` reports a SOPS decryption failure (RULE 4) and you want a
  focused, human-readable report of which files are broken.
- As a sanity check when setting up a new machine or adding a new key to the agent.

If a file has no SOPS metadata at all (i.e. it was accidentally left as plaintext),
`--verify` prompts interactively to encrypt it on the spot.

---

## When automation calls this

`fw-repo-mgr` calls `sops-mgr --re-encrypt --infra-dir <target-repo>/infra/` immediately
after writing `.sops.yaml` into a generated repo.  This ensures that any `*.sops.yaml`
files already present in the repo (e.g. `gcp_seed_secrets.sops.yaml` copied from
`_framework_settings/`) are re-encrypted to the key set declared in the new `.sops.yaml`.

Using `sops-mgr` (rather than calling `sops updatekeys` directly) means every SOPS
re-encryption operation in the codebase is discoverable by grepping for `sops-mgr` —
audit coverage, key-rotation traceability, and future improvements stay in one place.

`validate-config` (run automatically at `source set_env.sh`) performs its own SOPS
decryption check (RULE 4) using a direct `sops --decrypt` call integrated into its
reporting loop.  It does not delegate to `sops-mgr` because it needs per-file status
for its structured output.

---

## CLI

```
sops-mgr -r|--re-encrypt [-d PATH]  re-encrypt all *.sops.yaml with current .sops.yaml keys
sops-mgr -v|--verify     [-d PATH]  verify all *.sops.yaml files can be decrypted
sops-mgr -d|--infra-dir PATH        scope search to PATH instead of $_INFRA_DIR
sops-mgr -h|--help                  show usage
```

`$_SOPS_MGR` is exported by `set_env.sh` so scripts can invoke it as:

```bash
"$_SOPS_MGR" --verify
"$_SOPS_MGR" --re-encrypt --infra-dir "$repo_dir/infra"
```
