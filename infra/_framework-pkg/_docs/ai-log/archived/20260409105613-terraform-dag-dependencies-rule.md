# Terraform DAG Dependencies Rule

## What changed

`update-mesh-central/terragrunt.hcl` (both `pwy-home-lab-pkg` and `mesh-central-pkg`
examples) had a hardcoded list of every physical machine in its `dependencies` block.
When a new machine is added to the fleet the list would silently become stale,
causing the update step to run before all machines are enrolled.

## Fix

Replaced the hardcoded machine list with a single dep on the `configure-physical-machines`
aggregating unit, which already depends on all machine enrollment units:

```hcl
# Before — hardcoded, drifts when fleet changes
dependencies {
  paths = [
    ".../mesh-central/enroll-ms01-01",
    ".../mesh-central/enroll-ms01-02",
    ".../mesh-central/enroll-nuc-1",
  ]
}

# After — single aggregating dep, never needs updating
dependencies {
  paths = [
    "${local._stack_root}/infra/pwy-home-lab-pkg/_stack/null/pwy-homelab/configure-physical-machines",
  ]
}
```

## New rule added

**CLAUDE.md** — new "Terraform DAG Dependencies" section: never hardcode unit lists
in `dependencies` blocks; use aggregating units; stretch goal is `terragrunt run --all`
working without the wave runner.

**docs/framework/waves.md** — new section "Terraform DAG vs Wave Ordering" explaining
the two mechanisms, when each applies, and rules for writing `dependencies` blocks.

**memory** — `feedback_terraform_dag_dependencies.md` saved.
