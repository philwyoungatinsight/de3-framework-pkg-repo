# Troubleshooting

---

## Tainted resources after a failed provisioner

When a `local-exec` provisioner fails during resource creation, Terraform
automatically marks that resource as **tainted**. On the next `apply`, Terraform
will destroy the tainted resource and recreate it, re-running the provisioner.

This means you do not need to manually taint the resource — just fix the
underlying cause and re-run apply.

### Example: commission script fails due to SSH key not in agent

The `null_resource.commission` in each MaaS machine unit SSHes to the MaaS
server. If the correct SSH key is not loaded in the agent when `apply` runs,
the SSH command fails with `Permission denied (publickey,password)` and the
provisioner exits non-zero. Terraform marks `null_resource.commission` as
tainted.

**Fix**: add your key to the agent, then re-run apply:

```bash
ssh-add ~/.ssh/id_ed25519
# enter passphrase when prompted

source $(git rev-parse --show-toplevel)/set_env.sh
cd "infra/pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-01"
terragrunt apply --auto-approve
```

Terraform will automatically replace the tainted `null_resource.commission`
and re-run the commissioning script.

### Manually tainting a resource

If you need to force a provisioner to re-run when it previously succeeded
(e.g. the machine state changed outside Terraform), taint the resource manually:

```bash
terragrunt run -- taint null_resource.commission
terragrunt apply --auto-approve
```

### Checking taint status

`terragrunt state list` does not show taint status. To see it:

```bash
terragrunt run -- show
```

Tainted resources appear as `# <resource> is tainted` in the plan output on
the next apply.

---

## Stale GCS state lock

If `apply` or `destroy` was killed mid-run, it may leave a lock file in GCS
that blocks subsequent runs:

```
Error acquiring the state lock: storage: object doesn't exist
```

or

```
Error locking state: Error acquiring the state lock
```

**Fix**:

```bash
gsutil rm gs://seed-tf-state-pwy-homelab-20260308-1700/<unit-path>/default.tflock
```

For example:
```bash
gsutil rm gs://seed-tf-state-pwy-homelab-20260308-1700/pwy-home-lab-pkg/_stack/maas/pwy-homelab/machines/ms01-01/default.tflock
```

---

## YAML parse error blocking all terragrunt commands

Symptom: every `terragrunt` command (even `state list`) fails with:

```
Call to function "yamldecode" failed: on line NNN, column NN: did not find expected key.
```

This means the per-package YAML config file (or its secrets file) has a syntax
error. Common causes:

- Double colon (`::`) instead of single colon (`:`) after a mapping key
- YAML reserved words (`null`, `true`, `false`, `yes`, `no`) used as unquoted
  mapping keys
- Indentation error

**Fix**: open the indicated file, go to the reported line, and correct the
syntax. Verify with:

```bash
python3 -c "import yaml, sys; yaml.safe_load(open(sys.argv[1]))" \
  infra/pwy-home-lab-pkg/_config/pwy-home-lab-pkg.yaml
```

---

## MaaS failures (commission blocked, stuck in New, stuck deploying)

See `infra/maas-pkg/_docs/troubleshooting.md` for MaaS-specific troubleshooting:
- Commission blocked (`power_state=error`)
- Machine stuck in New after commission triggered
- Commission or deploy stuck for 10+ minutes

---

## Proxmox API 401 Unauthorized

Symptom: Proxmox provider fails with `401 no such user`.

The API token in use is wrong. The `proxmox-iso` plugin constructs:
`PVEAPIToken=<username>=<token>`, so `username` must be the full token ID
(e.g. `root@pam!tg-token`) and `token` must be only the UUID secret.

Check the token in SOPS: `providers.proxmox.config_params` → `proxmox_token_id`
and `proxmox_token_secret`. Verify the token exists in Proxmox:
`pveum user token list root@pam`.
