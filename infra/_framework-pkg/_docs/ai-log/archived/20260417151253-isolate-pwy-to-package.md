# Isolate "pwy" to infra/pwy-home-lab-pkg

## What changed

Renamed all generic `pwy`-specific identifiers outside `infra/pwy-home-lab-pkg/` to generic equivalents.
Historical ai-log files and deployment-specific GCP resource names (bucket/project IDs) were left untouched.

### Files modified

- `infra/gcp-pkg/_stack/gcp/us-central1/dev/test-bucket-pwy-3/` → `test-bucket-3/` (git mv)
- `infra/gcp-pkg/_stack/gcp/us-central1/dev/test-bucket-3/terragrunt.hcl` — comment: example bucket_name
- `infra/gcp-pkg/_stack/gcp/us-central1/dev/test-bucket/terragrunt.hcl` — comment: example bucket_name
- `set_env.sh` — comment: "pwy-home-lab stack" → "de3 stack"
- `framework/manage-unit/manage_unit/main.py` — docstring + argparse description
- `utilities/ansible/roles/config_base/filter_plugins/lab_config.py` — docstring
- `utilities/python/validate-config.py` — default flag_file path
- `CLAUDE.md` — `pwy-home-lab-GUI` → `de3-gui-pkg`
- `infra/mikrotik-pkg/_docs/README.md` — example cd path and config key name
- `infra/maas-pkg/_modules/maas_machine/variables.tf` — variable description example token name
- `infra/image-maker-pkg/_tg_scripts/image-maker/build-images/README.md` — troubleshooting table token example
- `infra/unifi-pkg/_wave_scripts/test-ansible-playbooks/network/network-validate-config/README.md` — "Running Directly" example path
- `infra/maas-pkg/_tg_scripts/maas/configure-plain-hosts/playbook.configure-plain-hosts.yaml` — inline comment
- `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/fix-maas-amt-ssl.yaml` — inline comment
- `infra/de3-gui-pkg/_application/de3-gui/homelab_gui/homelab_gui.py` — default repo path, description string, Cytoscape demo elements, ReactFlow demo elements

## Why

Generic framework code was using "pwy-home-lab" naming, making it appear deployment-specific.
All deployment-specific code belongs in `infra/pwy-home-lab-pkg/`.
