# root.hcl
# Root Terragrunt configuration for the stack.
#
# Design:
# - Package and provider are derived explicitly from the infra/ path structure.
# - Config is loaded directly from per-package YAML files — no Python merge script.
# - All package resources (modules, providers, scripts) live under infra/<pkg>/.
#
# Unit path layout: infra/<package>/_stack/<provider>/<path...>/<leaf-unit>/

# ============================================================================

locals {
  # Root of this stack – anchored on root.hcl
  stack_root = dirname(find_in_parent_folders("root.hcl"))

  # ---------------------------------------------------------------------------
  # Path parsing — package and leaf unit derived from directory structure.
  #
  # Layout: infra/<package>/_stack/<path...>/<leaf-unit>
  #   path_parts[0] = package     (e.g. "pwy-home-lab-pkg")
  #   path_parts[1] = "_stack"    (literal separator)
  #   path_parts[2..] = path segments (provider no longer encoded here)
  #   path_parts[-1] = leaf unit name
  #
  # The Terraform provider is NOT derived from the path — it is set via
  # _provider in config_params and inferred below after unit_params is merged.
  # ---------------------------------------------------------------------------
  _rel_path_raw = path_relative_to_include()
  _after_infra  = trimprefix(local._rel_path_raw, "infra/")
  _infra_guard  = local._after_infra != local._rel_path_raw ? true : error("Invalid unit path: expected path under infra/. Got: ${local._rel_path_raw}")
  path_parts    = split("/", local._after_infra)
  _path_guard   = length(local.path_parts) >= 3 ? true : error("Invalid unit path: expected infra/<pkg>/_stack/<path...> Got: ${local._rel_path_raw}")

  # Package and leaf unit from path; provider comes from config_params (_provider key)
  p_package = local.path_parts[0]
  p_unit    = local.path_parts[length(local.path_parts) - 1]

  # rel_path: full path after infra/ — used for state path and config_params key matching
  rel_path = local._after_infra

  # Ancestor path prefixes (top-down). Used to merge flat config_params.
  _ancestor_paths = [
    for i in range(1, length(local.path_parts) + 1) :
    join("/", slice(local.path_parts, 0, i))
  ]

  # ---------------------------------------------------------------------------
  # Config loading — reads from pre-merged $_CONFIG_DIR.
  # config-mgr generate (called from set_env.sh) merges config_source overlays
  # and copies encrypted SOPS files. SOPS secrets are decrypted at runtime by
  # sops_decrypt_file() — never written to disk.
  #
  # Framework config: backend, wave ordering, ssh_config, etc.
  # Package config:   providers, config_params, wave definitions.
  # Secrets:          per-package encrypted SOPS file copy in _CONFIG_DIR (decrypted at runtime).
  # ---------------------------------------------------------------------------
  _framework_main_package_dir = get_env("_MAIN_PKG_DIR", "")
  _fw_backend_path = (
    fileexists("${local.stack_root}/config/framework_backend.yaml")
    ? "${local.stack_root}/config/framework_backend.yaml"
    : local._framework_main_package_dir != "" && fileexists("${local._framework_main_package_dir}/_config/_framework_settings/framework_backend.yaml")
    ? "${local._framework_main_package_dir}/_config/_framework_settings/framework_backend.yaml"
    : "${local.stack_root}/infra/_framework-pkg/_config/_framework_settings/framework_backend.yaml"
  )
  _framework_backend = yamldecode(file(local._fw_backend_path))["framework_backend"]

  # $_CONFIG_DIR must be set by sourcing set_env.sh before running terragrunt.
  _config_dir = get_env("_CONFIG_DIR")

  _package_cfg_file = "${local._config_dir}/${local.p_package}.yaml"
  _package_cfg_raw  = yamldecode(file(local._package_cfg_file))
  # Top-level key in package config matches the package name
  _package_cfg = try(local._package_cfg_raw[local.p_package], {})
  # _cfg: public config alias for units (e.g. all-config) that upload config as
  # JSON to cloud storage. Secrets are intentionally excluded.
  _cfg = local._package_cfg

  # Package secrets: load if present; sops_decrypt_file decrypts at runtime — never on disk.
  _pkg_sec_path  = "${local._config_dir}/${local.p_package}.secrets.sops.yaml"
  _package_sec   = fileexists(local._pkg_sec_path) ? yamldecode(sops_decrypt_file(local._pkg_sec_path)) : {}
  # Per-package secrets top-level key is <pkg>_secrets, falling back to <pkg>
  _package_sec_cfg = try(local._package_sec["${local.p_package}_secrets"], local._package_sec[local.p_package], local._package_sec)

  # Framework secrets: backend_auth and any cross-package secrets.
  _fw_sec_path   = "${local._config_dir}/_framework-pkg.secrets.sops.yaml"
  _framework_sec = fileexists(local._fw_sec_path) ? yamldecode(sops_decrypt_file(local._fw_sec_path)) : {}
  _framework_sec_cfg = try(local._framework_sec["framework_secrets"], {})

  # ---------------------------------------------------------------------------
  # config_params — flat at the package level (not scoped under a provider).
  # Keys mirror the unit path (e.g. "pwy-home-lab-pkg/_stack/pwy-homelab/proxmox").
  # Deeper keys override shallower ones (ancestor-merge, top-down).
  # ---------------------------------------------------------------------------
  _config_params = jsondecode(jsonencode(try(local._package_cfg.config_params, {})))
  _ancestor_param_list = [
    for p in local._ancestor_paths :
    try(local._config_params[p], null)
    if try(local._config_params[p], null) != null
  ]
  unit_params = merge(local._ancestor_param_list...)

  # ---------------------------------------------------------------------------
  # Provider — from _provider in config_params (set once at the top of each
  # provider subtree; inherited by all children via ancestor-merge).
  # Falls back to path_parts[2] so packages that haven't migrated still work.
  # ---------------------------------------------------------------------------
  p_tf_provider = try(tostring(local.unit_params._provider), local.path_parts[2])

  # ---------------------------------------------------------------------------
  # Per-path secret params — from infra/<pkg>/_config/<pkg>_secrets.sops.yaml
  # under the config_params key.  Ancestor-merged identically to public params.
  # ---------------------------------------------------------------------------
  _secret_params = jsondecode(jsonencode(try(local._package_sec_cfg.config_params, {})))
  _ancestor_secret_list = [
    for p in local._ancestor_paths :
    try(local._secret_params[p], null)
    if try(local._secret_params[p], null) != null
  ]
  unit_secret_params = merge(local._ancestor_secret_list...)

  # ---------------------------------------------------------------------------
  # Module directory resolution — 3-tier fallback:
  #   1. This package's own _modules/ directory
  #   2. <provider>-pkg/_modules/ (canonical provider package)
  #   3. _framework-pkg/_modules/ (shared null/utility modules)
  #
  # Override per unit/subtree via _modules_dir in config_params:
  #   _modules_dir: _framework-pkg/_modules   # relative to infra/
  # ---------------------------------------------------------------------------
  _modules_dir_override = try(local.unit_params._modules_dir, null)
  modules_dir = (
    local._modules_dir_override != null
    # Explicit override — relative to infra/
    ? "${local.stack_root}/infra/${local._modules_dir_override}"
    # Tier 1: package has its own modules (sentinel file present)
    : fileexists("${local.stack_root}/infra/${local.p_package}/_modules/.modules-root")
    ? "${local.stack_root}/infra/${local.p_package}/_modules"
    # Tier 2: canonical provider package (e.g. gcp-pkg for gcp provider)
    : fileexists("${local.stack_root}/infra/${local.p_tf_provider}-pkg/_modules/.modules-root")
    ? "${local.stack_root}/infra/${local.p_tf_provider}-pkg/_modules"
    # Tier 3: _framework-pkg (always present)
    : "${local.stack_root}/infra/_framework-pkg/_modules"
  )

  # ---------------------------------------------------------------------------
  # Provider template — 3-tier fallback:
  #   1. This package's _providers/<provider>.tpl
  #   2. <provider>-pkg/_providers/<provider>.tpl
  #   3. _framework-pkg/_providers/<provider>.tpl  (framework fallback)
  # ---------------------------------------------------------------------------
  _provider_tpl_path = (
    fileexists("${local.stack_root}/infra/${local.p_package}/_providers/${local.p_tf_provider}.tpl")
    ? "${local.stack_root}/infra/${local.p_package}/_providers/${local.p_tf_provider}.tpl"
    : fileexists("${local.stack_root}/infra/${local.p_tf_provider}-pkg/_providers/${local.p_tf_provider}.tpl")
    ? "${local.stack_root}/infra/${local.p_tf_provider}-pkg/_providers/${local.p_tf_provider}.tpl"
    : "${local.stack_root}/infra/_framework-pkg/_providers/${local.p_tf_provider}.tpl"
  )

  # Package-relative script roots — overridable via _tg_scripts_dir / _wave_scripts_dir in config_params
  # Use case: deployment packages (e.g. pwy-home-lab-pkg) reference canonical package scripts.
  # Example: _tg_scripts_dir: proxmox-pkg/_tg_scripts
  _tg_scripts   = "${local.stack_root}/infra/${try(local.unit_params._tg_scripts_dir, "${local.p_package}/_tg_scripts")}"
  _wave_scripts = "${local.stack_root}/infra/${try(local.unit_params._wave_scripts_dir, "${local.p_package}/_wave_scripts")}"

  # ---------------------------------------------------------------------------
  # Required parameters — from config_params inheritance
  # ---------------------------------------------------------------------------
  p_region = try(local.unit_params._region, null)
  p_env    = try(local.unit_params._env, null)

  _region_guard = local.p_region != null ? true : error("unit_params._region is required for ${local._rel_path_raw} (set via config_params)")
  _env_guard    = local.p_env    != null ? true : error("unit_params._env is required for ${local._rel_path_raw} (set via config_params)")

  # ---------------------------------------------------------------------------
  # Backend — from framework config
  # ---------------------------------------------------------------------------
  backend_type   = local._framework_backend.type
  backend_config = try(local._framework_backend.config, {})

  _state_fragment = (
    local.backend_type == "gcs"   ? { prefix = local.rel_path } :
    local.backend_type == "local" ? {
      path = "${get_parent_terragrunt_dir()}/${local.rel_path}/terraform.tfstate"
    } :
    { key = "${local.rel_path}/terraform.tfstate" }
  )

  # ---------------------------------------------------------------------------
  # Deterministic MAC address — based on full rel_path (prevents collisions)
  # ---------------------------------------------------------------------------
  _rel_path_label = substr(replace(lower(local.rel_path), "/", "__"), 0, 63)
  _rel_path_full  = replace(lower(local.rel_path), "/", "__")
  _raw_hash       = md5(local._rel_path_full)
  _h              = substr(local._raw_hash, 0, 12)
  _mac_seed       = format("%s2%s", substr(local._h, 0, 1), substr(local._h, 2, 10))
  _default_mac_address = format("%s:%s:%s:%s:%s:%s",
    substr(local._mac_seed, 0, 2),
    substr(local._mac_seed, 2, 2),
    substr(local._mac_seed, 4, 2),
    substr(local._mac_seed, 6, 2),
    substr(local._mac_seed, 8, 2),
    substr(local._mac_seed, 10, 2)
  )

  common_tags = {
    provider            = local.p_tf_provider
    region              = local.p_region
    environment         = local.p_env
    rel_path            = local._rel_path_label
    rel_path_md5        = local._raw_hash
    cost_center         = try(local.unit_params._cost_center, "")
    owner               = try(local.unit_params._owner, "")
    application         = try(local.unit_params._application, "")
    managed_by          = try(tostring(local.unit_params._managed_by), "terragrunt")
    default_mac_address = "default_mac_${replace(local._default_mac_address, ":", "")}"
  }

  # common_tags_list — Proxmox-style flat string tags derived from common_tags.
  # Use this (not common_tags) for resources whose tags argument is list(string).
  # Optional fields (owner, application, cost_center) are omitted when empty.
  common_tags_list = compact([
    local.common_tags.environment,
    "managed-by-${local.common_tags.managed_by}",
    local.common_tags.owner       != "" ? "owner-${local.common_tags.owner}"             : "",
    local.common_tags.application != "" ? "app-${local.common_tags.application}"         : "",
    local.common_tags.cost_center != "" ? "cost-center-${local.common_tags.cost_center}" : "",
  ])

  # ---------------------------------------------------------------------------
  # Provider template variable map — passed to templatefile().
  # All variables are passed; unused ones are silently ignored by templatefile().
  # All values come from config_params via unit_params / unit_secret_params.
  # Public provider config: _provider_<name>_<key> in config_params.
  # Secret provider config: <key> in config_params of the secrets file.
  # ---------------------------------------------------------------------------
  _provider_template_vars = {
    # ── Public config ──────────────────────────────────────────────────────────
    REGION              = local.p_region
    PROJECT             = try(local.unit_params["_provider_${local.p_tf_provider}_project"],             "")
    ACCOUNT_ID          = try(local.unit_params["_provider_${local.p_tf_provider}_account_id"],          "")
    ENDPOINT            = try(local.unit_params["_provider_${local.p_tf_provider}_endpoint"],            "")
    HOST                = try(local.unit_params["_provider_${local.p_tf_provider}_host"],                "")
    URI                 = try(local.unit_params["_provider_${local.p_tf_provider}_uri"],                 "")
    API_URL             = try(local.unit_params["_provider_${local.p_tf_provider}_api_url"],             "")
    HOSTNAME            = try(local.unit_params["_provider_${local.p_tf_provider}_hostname"],            "")
    TARGET              = try(local.unit_params["_provider_${local.p_tf_provider}_target"],              "")
    VSPHERE_SERVER      = try(local.unit_params["_provider_${local.p_tf_provider}_vsphere_server"],      "")
    SERIAL_NUMBER       = try(local.unit_params["_provider_${local.p_tf_provider}_serial_number"],       "")
    PMAX_VERSION        = try(local.unit_params["_provider_${local.p_tf_provider}_pmax_version"],        "")
    S3_ENDPOINT         = try(local.unit_params["_provider_${local.p_tf_provider}_s3_endpoint"],         "")
    MINIO_ENDPOINT      = try(local.unit_params["_provider_${local.p_tf_provider}_minio_endpoint"],      "")
    OBJECTS_ENDPOINT    = try(local.unit_params["_provider_${local.p_tf_provider}_objects_endpoint"],    "")
    INSECURE            = tostring(try(local.unit_params["_provider_${local.p_tf_provider}_insecure"],   true))
    SSL_INSECURE        = tostring(try(local.unit_params["_provider_${local.p_tf_provider}_ssl_insecure"], true))
    AUTH_TYPE           = tostring(try(local.unit_params["_provider_${local.p_tf_provider}_auth_type"],  0))
    AUTH_METHOD         = try(local.unit_params["_provider_${local.p_tf_provider}_auth_method"],         "")
    PROFILE             = try(local.unit_params["_provider_${local.p_tf_provider}_profile"],             "")
    INSTALLATION_METHOD = try(local.unit_params["_provider_${local.p_tf_provider}_installation_method"], "snap")
    TLS_INSECURE        = tostring(try(local.unit_params["_provider_${local.p_tf_provider}_tls_insecure"], false))
    SSH_USERNAME        = try(local.unit_params["_provider_${local.p_tf_provider}_ssh_username"],        "")
    SSH_AGENT           = tostring(try(local.unit_params["_provider_${local.p_tf_provider}_ssh_agent"],  true))
    # ── Secrets ────────────────────────────────────────────────────────────────
    # Keys follow the same _provider_<name>_<key> convention as public params above.
    USERNAME            = try(local.unit_secret_params["_provider_${local.p_tf_provider}_username"],           "")
    PASSWORD            = try(local.unit_secret_params["_provider_${local.p_tf_provider}_password"],           "")
    ACCESS_KEY          = try(local.unit_secret_params["_provider_${local.p_tf_provider}_access_key"],         "")
    SECRET_KEY          = try(local.unit_secret_params["_provider_${local.p_tf_provider}_secret_key"],         "")
    API_KEY             = try(local.unit_secret_params["_provider_${local.p_tf_provider}_api_key"],            "")
    API_TOKEN           = try(local.unit_secret_params["_provider_${local.p_tf_provider}_api_token"],          "")
    TOKEN_ID            = try(local.unit_secret_params["_provider_${local.p_tf_provider}_token_id"],           "")
    TOKEN_SECRET        = try(local.unit_secret_params["_provider_${local.p_tf_provider}_token_secret"],       "")
    USER                = try(local.unit_secret_params["_provider_${local.p_tf_provider}_user"],               "")
    S3_ACCESS_KEY       = try(local.unit_secret_params["_provider_${local.p_tf_provider}_s3_access_key"],      "")
    S3_SECRET_KEY       = try(local.unit_secret_params["_provider_${local.p_tf_provider}_s3_secret_key"],      "")
    MINIO_ACCESS_KEY    = try(local.unit_secret_params["_provider_${local.p_tf_provider}_minio_access_key"],   "")
    MINIO_SECRET_KEY    = try(local.unit_secret_params["_provider_${local.p_tf_provider}_minio_secret_key"],   "")
    OBJECTS_ACCESS_KEY  = try(local.unit_secret_params["_provider_${local.p_tf_provider}_objects_access_key"], "")
    OBJECTS_SECRET_KEY  = try(local.unit_secret_params["_provider_${local.p_tf_provider}_objects_secret_key"], "")
    SUBSCRIPTION_ID     = try(local.unit_secret_params["_provider_${local.p_tf_provider}_subscription_id"],    "")
    TENANT_ID           = try(local.unit_secret_params["_provider_${local.p_tf_provider}_tenant_id"],          "")
    CLIENT_ID           = try(local.unit_secret_params["_provider_${local.p_tf_provider}_client_id"],          "")
    CLIENT_SECRET       = try(local.unit_secret_params["_provider_${local.p_tf_provider}_client_secret"],      "")
    GCP_CREDENTIALS     = try(local.unit_secret_params["_provider_${local.p_tf_provider}_credentials"],        "")
  }

  _provider_content_raw = templatefile(local._provider_tpl_path, local._provider_template_vars)

  # ---------------------------------------------------------------------------
  # Extra providers — additional plugins needed beyond the primary provider.
  # Declared via _extra_providers: ["null"] in config_params.
  # Fragment lookup order mirrors primary templates (3 tiers).
  # ---------------------------------------------------------------------------
  _extra_providers = [
    for v in try(tolist(local.unit_params._extra_providers), []) : tostring(v)
    if v != null
  ]

  _extra_provider_entry_paths = [
    for name in local._extra_providers :
    fileexists("${local.stack_root}/infra/${local.p_package}/_providers/${name}.entry.tpl")
    ? "${local.stack_root}/infra/${local.p_package}/_providers/${name}.entry.tpl"
    : fileexists("${local.stack_root}/infra/${name}-pkg/_providers/${name}.entry.tpl")
    ? "${local.stack_root}/infra/${name}-pkg/_providers/${name}.entry.tpl"
    : "${local.stack_root}/infra/_framework-pkg/_providers/${name}.entry.tpl"
  ]

  _extra_entries_str = join("\n    ", [
    for p in local._extra_provider_entry_paths : trimspace(file(p))
  ])

  _provider_content = length(local._extra_providers) > 0 ? replace(
    local._provider_content_raw,
    "required_providers {",
    "required_providers {\n    ${local._extra_entries_str}"
  ) : local._provider_content_raw

  # ── Wave filtering ───────────────────────────────────────────────────────────
  _unit_wave = try(tostring(local.unit_params._wave), null)
  _tg_wave   = get_env("TG_WAVE", "")
  _wave_skip = (
    local._unit_wave != null &&
    local._tg_wave   != "" &&
    local._tg_wave   != "all"
  ) ? !contains(split(",", local._tg_wave), local._unit_wave) : false

  # ── Unit skip flags ───────────────────────────────────────────────────────────
  #
  # _skip_on_build (INHERITED via unit_params):
  #   Set at an ancestor config_params path to disable deployment of an entire
  #   subtree (e.g. "examples/" trees shipped with a package but not run by
  #   default). All descendants inherit the flag via ancestor-path merging.
  #   Override with _skip_on_build: false at a child path to re-enable a subtree.
  #   Excluded from ALL terraform actions (actions = ["all"] in the exclude block
  #   below). Since these units are never deployed there is no state to destroy.
  #
  # _skip_on_wave_run — wave-level, handled by the Python orchestrator in run:
  #   Set _skip_on_wave_run: true on a wave definition in <pkg>.yaml. The `run`
  #   script skips the wave during both build and clean passes. No HCL change
  #   needed — this flag is read and applied entirely in Python.
  #
  # _FORCE_DELETE=YES overrides all skip flags so make clean-all destroys every
  # unit unconditionally, including _skip_on_build example trees.
  #
  _force_delete  = get_env("_FORCE_DELETE", "") == "YES"
  _skip_on_build = try(tobool(local.unit_params._skip_on_build), false)

  # _unit_purpose (NOT inherited — exact config_params key for this unit only):
  #   Optional human-readable description of what this unit does and why it exists.
  #   Read from the exact path entry only so ancestor-level values do not bleed
  #   into child units.  No effect on apply/destroy behaviour.
  unit_purpose = try(tostring(local._config_params[local.rel_path]._unit_purpose), "")

}

# ── Backend ──────────────────────────────────────────────────────────────────
remote_state {
  backend = local.backend_type

  config = merge(
    local.backend_config,
    try(local._framework_sec_cfg.backend_auth, {}),
    local._state_fragment,
  )

  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

# ── Provider ─────────────────────────────────────────────────────────────────
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = local._provider_content
}

# ── Unit-path env file — sourced by long-running tg-scripts for status reporting ──
# Written into every module cache directory alongside backend.tf / provider.tf.
# Scripts source this to get UNIT_PATH (rel_path) and UNIT_REL_FULL (_rel_path_full)
# without needing per-unit TF variable changes.
generate "unit_path_env" {
  path      = "unit_path.env"
  if_exists = "overwrite_terragrunt"
  contents  = "export UNIT_PATH=\"${local.rel_path}\"\nexport UNIT_REL_FULL=\"${local._rel_path_full}\"\n"
}

# ── Wave / unit skip ──────────────────────────────────────────────────────────
# Two conditions trigger the exclude (OR'd):
#   _wave_skip       — unit's wave doesn't match TG_WAVE filter
#   _skip_on_build   — ancestor-inherited subtree skip flag (config_params)
# Both map to actions = ["all"]: no apply, plan, init, output, or destroy.
# Wave-level _skip_on_wave_run is handled by the Python orchestrator in run,
# not here. _FORCE_DELETE=YES (set by make clean-all) disables this block
# entirely so every unit is destroyed unconditionally.
exclude {
  if      = !local._force_delete && (local._wave_skip || local._skip_on_build)
  actions = ["all"]
}

# ── Exit-status hooks ─────────────────────────────────────────────────────────
# Two-hook pattern to capture ok vs fail for every apply/destroy in all
# execution contexts (GUI, wave runner, manual tg apply, make, etc.).
#
# Hook 1 (exit_status_mark_ok): runs ONLY on success (run_on_error=false).
#   Drops a hidden marker file in $_DYNAMIC_DIR/unit-status/. If this hook
#   is skipped (terraform exited non-zero), no marker is written.
#
# Hook 2 (exit_status_write): ALWAYS runs (run_on_error=true).
#   Reads the marker to determine ok vs fail, writes the exit-status YAML,
#   and cleans up any stale MaaS intermediate status for this unit.
#
# Status files land in $_DYNAMIC_DIR/unit-status/ (config/tmp/dynamic/unit-status/),
# which is per-repo-checkout — no conflicts between running instances.
terraform {
  after_hook "exit_status_mark_ok" {
    commands     = ["apply", "destroy"]
    execute      = [
      "bash", "-c",
      "source $(git rev-parse --show-toplevel)/set_env.sh && mkdir -p \"$_DYNAMIC_DIR/unit-status\" && touch \"$_DYNAMIC_DIR/unit-status/.ok-${local._rel_path_full}\""
    ]
    run_on_error = false
  }

  after_hook "exit_status_write" {
    commands     = ["apply", "destroy"]
    execute      = [
      get_env("_WRITE_EXIT_STATUS"),
      local.rel_path,
      local._rel_path_full,
    ]
    run_on_error = true
  }
}
