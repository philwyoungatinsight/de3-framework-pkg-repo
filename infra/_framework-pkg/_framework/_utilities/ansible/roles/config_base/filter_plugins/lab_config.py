"""
Ansible filter plugins for de3 config_base role.

ancestor_merge(path, config_params)
    Root.hcl-style ancestor merge: given a unit path and a flat config_params dict,
    return the merged dict of all ancestor entries (top-down, deeper overrides shallower).
    Mirrors the HCL logic in root.hcl:
        _ancestor_param_list = [
          for p in _ancestor_paths :
          try(local._config_params[p], null)
          if try(local._config_params[p], null) != null
        ]
        unit_params = merge(local._ancestor_param_list...)
"""


def ancestor_merge(path, config_params):
    """Merge config_params entries for all ancestor prefixes of path (top-down).

    Example:
        path = "pkg/_stack/null/env/maas/configure-server"
        config_params = {
            "pkg/_stack/null/env": {"region": "env"},
            "pkg/_stack/null/env/maas/configure-server": {"admin_username": "admin"},
        }
        → {"region": "env", "admin_username": "admin"}
    """
    if not isinstance(path, str) or not isinstance(config_params, dict):
        return {}
    parts = path.split("/")
    result = {}
    for i in range(1, len(parts) + 1):
        prefix = "/".join(parts[:i])
        entry = config_params.get(prefix)
        if isinstance(entry, dict):
            result = {**result, **entry}
    return result


class FilterModule:
    def filters(self):
        return {
            "ancestor_merge": ancestor_merge,
        }
