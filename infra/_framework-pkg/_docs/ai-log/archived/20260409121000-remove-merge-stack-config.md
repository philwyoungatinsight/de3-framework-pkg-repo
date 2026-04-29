---
date: 2026-04-09
title: Remove dead framework/lib/merge-stack-config.py
---

## What changed

Deleted `framework/lib/merge-stack-config.py` — it had zero callers anywhere
in the repo.

## Why it was dead

The script's docstring claimed it was "Called by root.hcl via run_cmd()" to
deep-merge `terragrunt_lab_stack*` config files. That was true in an earlier
architecture. `root.hcl` now documents explicitly (line 6): "Config is loaded
directly from per-package YAML files — no Python merge script." It uses
`yamldecode(file(...))` directly for both framework config
(`config/framework.yaml`) and per-package config (`infra/<pkg>/_config/<pkg>.yaml`).

Neither the `--secrets` mode, the `--from-jsons` mode, nor the default mode
were referenced by any `.hcl`, `.sh`, `run`, or `.py` file outside the script
itself.
