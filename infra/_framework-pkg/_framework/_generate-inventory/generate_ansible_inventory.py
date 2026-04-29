#!/usr/bin/env python3
"""generate_ansible_inventory.py

Generates an Ansible inventory (hosts.yml) by reading Terraform remote state
from the configured backend and cross-referencing with per-package YAML config.

Sources:
  - <pkg>.yaml            : backend config, provider config, cloud_init_user
  - Terraform remote state     : VM/machine names, IPv4 addresses, tags

Host discovery:
  - A unit is a host candidate iff its terragrunt.hcl source matches a module
    in ansible_inventory.modules_to_include (e.g. proxmox_virtual_environment_vm,
    maas_machine). The unit's own _is_host config_params key (never inherited)
    overrides. Non-host units (ISOs, snippets, null scripts, cloud buckets) are
    skipped without fetching state regardless of inherited additional_tags.
  - The host type (Proxmox VM, MaaS machine, etc.) is auto-detected from the
    resource types present in the Terraform state — no hardcoded module paths.

Role → group mapping:
  - Tags of the form 'role_<name>' map to Ansible host group '<name>'.
  - If --roles is given, only those named roles get their own groups; role_* tags
    that do not appear in the filter go to 'role_did_not_match'.
  - Hosts with no role_* tags at all go to 'no_role'.
  - --only-matched skips hosts in 'no_role' and 'role_did_not_match'.

Setup:
  source set_env.sh              # sets $_CONFIG_DIR and $_STACK_ROOT
  pip install pyyaml
  pip install google-cloud-storage             # if backend.type == gcs
  pip install boto3                            # if backend.type == s3
  pip install azure-storage-blob azure-identity  # if backend.type == azurerm

Usage:
  python3 generate_ansible_inventory.py \\
      [--roles web,db] \\
      [--only-matched] \\
      [--output hosts.yml] \\
      [--no-ssh-check] \\
      [--exclude-unreachable] \\
      [--provider-keys omit|include|comment] \\
      [--null-vars omit|comment] \\
      [--config PATH] \\
      [--stack-root PATH]
"""

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml")


# ---------------------------------------------------------------------------
# Backend abstraction
# ---------------------------------------------------------------------------

class StateFetchError(Exception):
    pass


class StateFetcher:
    def fetch(self, rel_path: str) -> Optional[dict]:
        raise NotImplementedError

    def state_path(self, rel_path: str) -> str:
        """Human-readable description of where the state lives (for error messages)."""
        return rel_path


class GCSStateFetcher(StateFetcher):
    """Fetches state from Google Cloud Storage.

    GCS path convention (from root.hcl): <bucket>/<rel_path>/default.tfstate
    """

    def __init__(self, bucket: str, **_kwargs):
        self.bucket_name = bucket
        try:
            from google.cloud import storage  # noqa: PLC0415
            self._client = storage.Client()
        except ImportError:
            sys.exit("GCS backend requires: pip install google-cloud-storage")

    def state_path(self, rel_path: str) -> str:
        return f"gs://{self.bucket_name}/{rel_path}/default.tfstate"

    def fetch(self, rel_path: str) -> Optional[dict]:
        bucket = self._client.bucket(self.bucket_name)
        blob = bucket.blob(f"{rel_path}/default.tfstate")
        if not blob.exists():
            return None
        return json.loads(blob.download_as_text())


class S3StateFetcher(StateFetcher):
    """Fetches state from AWS S3 (or any S3-compatible store).

    S3 key convention (from root.hcl): <rel_path>/terraform.tfstate
    Extra kwargs (region, endpoint_url, etc.) are passed through to boto3.
    """

    def __init__(self, bucket: str, region: Optional[str] = None,
                 endpoint: Optional[str] = None, **_kwargs):
        self.bucket = bucket
        try:
            import boto3  # noqa: PLC0415
            client_kwargs = {}
            if region:
                client_kwargs["region_name"] = region
            if endpoint:
                client_kwargs["endpoint_url"] = endpoint
            self._s3 = boto3.client("s3", **client_kwargs)
        except ImportError:
            sys.exit("S3 backend requires: pip install boto3")

    def state_path(self, rel_path: str) -> str:
        return f"s3://{self.bucket}/{rel_path}/terraform.tfstate"

    def fetch(self, rel_path: str) -> Optional[dict]:
        import botocore.exceptions  # noqa: PLC0415
        key = f"{rel_path}/terraform.tfstate"
        try:
            response = self._s3.get_object(Bucket=self.bucket, Key=key)
            return json.loads(response["Body"].read())
        except botocore.exceptions.ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("NoSuchKey", "404"):
                return None
            raise StateFetchError(
                f"S3 error fetching {self.state_path(rel_path)}: {exc}"
            ) from exc


class AzurermStateFetcher(StateFetcher):
    """Fetches state from Azure Blob Storage.

    Azure blob path convention (from root.hcl): <container>/<rel_path>/terraform.tfstate
    Authentication uses DefaultAzureCredential (env vars, managed identity, Azure CLI, etc.).
    """

    def __init__(self, storage_account_name: str, container_name: str, **_kwargs):
        self.storage_account_name = storage_account_name
        self.container_name = container_name
        try:
            from azure.identity import DefaultAzureCredential      # noqa: PLC0415
            from azure.storage.blob import BlobServiceClient        # noqa: PLC0415
            account_url = f"https://{storage_account_name}.blob.core.windows.net"
            self._client = BlobServiceClient(
                account_url=account_url,
                credential=DefaultAzureCredential(),
            )
        except ImportError:
            sys.exit(
                "Azure backend requires: pip install azure-storage-blob azure-identity"
            )

    def state_path(self, rel_path: str) -> str:
        return (
            f"https://{self.storage_account_name}.blob.core.windows.net"
            f"/{self.container_name}/{rel_path}/terraform.tfstate"
        )

    def fetch(self, rel_path: str) -> Optional[dict]:
        from azure.core.exceptions import ResourceNotFoundError  # noqa: PLC0415
        key = f"{rel_path}/terraform.tfstate"
        try:
            blob_client = self._client.get_blob_client(
                container=self.container_name, blob=key
            )
            data = blob_client.download_blob().readall()
            return json.loads(data)
        except ResourceNotFoundError:
            return None
        except Exception as exc:
            raise StateFetchError(
                f"Azure error fetching {self.state_path(rel_path)}: {exc}"
            ) from exc


class LocalStateFetcher(StateFetcher):
    """Fetches state from the local filesystem.

    Path convention (from root.hcl):
      <get_parent_terragrunt_dir()>/<rel_path>/terraform.tfstate
    which resolves to <stack_root>/<rel_path>/terraform.tfstate.
    Note: rel_path does NOT include 'infra/' (it is stripped in root.hcl).
    """

    def __init__(self, stack_root: str, **_kwargs):
        self._root = Path(stack_root)

    def state_path(self, rel_path: str) -> str:
        return str(self._root / rel_path / "terraform.tfstate")

    def fetch(self, rel_path: str) -> Optional[dict]:
        path = self._root / rel_path / "terraform.tfstate"
        if not path.exists():
            return None
        return json.loads(path.read_text())


_FETCHER_CLASSES = {
    "gcs":     GCSStateFetcher,
    "s3":      S3StateFetcher,
    "azurerm": AzurermStateFetcher,
    "local":   LocalStateFetcher,
}


def make_fetcher(backend_type: str, backend_config: dict, stack_root: str) -> StateFetcher:
    cls = _FETCHER_CLASSES.get(backend_type)
    if not cls:
        sys.exit(
            f"Unsupported backend type: {backend_type!r}. "
            f"Supported: {list(_FETCHER_CLASSES)}"
        )
    return cls(stack_root=stack_root, **backend_config)





# ---------------------------------------------------------------------------
# YAML config loading and ancestor-merge (mirrors root.hcl logic)
# ---------------------------------------------------------------------------

def load_stack_config(path: str) -> dict:
    """Load framework config and return a flat dict of framework keys.

    Accepts either a directory (reads all framework_*.yaml files) or a single
    YAML file (legacy single-file format).
    """
    p = Path(path)
    if p.is_dir():
        result: dict = {}
        for f in sorted(p.glob("framework_*.yaml")):
            if "secrets" in f.name:
                continue
            try:
                raw = yaml.safe_load(f.read_text())
            except yaml.YAMLError:
                continue
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if k.startswith("framework_"):
                        result[k[len("framework_"):]] = v
        return result
    # Legacy: single file
    with open(path) as fh:
        raw = yaml.safe_load(fh)
    return next(iter(raw.values()))


def ancestor_paths(rel_path: str) -> list:
    """Return all ancestor path prefixes from root down to rel_path."""
    parts = rel_path.split("/")
    return ["/".join(parts[: i + 1]) for i in range(len(parts))]


def merge_ancestor_params(config_params: dict, rel_path: str) -> dict:
    """Merge config_params from all ancestors; deeper entries override shallower."""
    result = {}
    for path in ancestor_paths(rel_path):
        entry = config_params.get(path) or {}
        if isinstance(entry, dict):
            result.update(entry)
    return result


def find_all_unit_paths(stack_root: str) -> list:
    """
    Walk infra/ under stack_root and return rel_path for every leaf
    terragrunt.hcl directory.

    rel_path mirrors the key used in config_params and the Terraform state
    path prefix.
    """
    infra_root = Path(stack_root) / "infra"
    results = []
    for hcl_file in sorted(infra_root.rglob("terragrunt.hcl")):
        if ".terragrunt-cache" in hcl_file.parts:
            continue
        results.append(str(hcl_file.parent.relative_to(infra_root)))
    return results


def unit_is_host(
    infra_root: str,
    rel_path: str,
    modules_to_include: list,
    own_params: dict,
) -> bool:
    """
    Return True if this unit should be treated as an Ansible inventory host.

    Priority:
    1. _is_host in the unit's own config_params entry (leaf only, never inherited).
       true → always include; false → always exclude.
    2. The unit's terragrunt.hcl source contains one of the module paths in
       ansible_inventory.modules_to_include (e.g. proxmox_virtual_environment_vm,
       maas_machine). All other module types are infrastructure, not hosts.
    """
    # Leaf-only override — _is_host must not be inherited from parent units.
    is_host_override = own_params.get("_is_host")
    if is_host_override is not None:
        return bool(is_host_override)

    if not modules_to_include:
        return False

    hcl_path = Path(infra_root) / rel_path / "terragrunt.hcl"
    if not hcl_path.is_file():
        return False

    content = hcl_path.read_text()
    m = re.search(r'source\s*=\s*"([^"]*)"', content)
    if not m:
        return False
    source = m.group(1)
    return any(mod in source for mod in modules_to_include)


def extract_host_info(state: dict) -> Optional[dict]:
    """Auto-detect host type from state resource types and extract host info.

    Tries each known provider extractor in order. Returns a unified dict on
    the first match, or None if the state contains no recognised host resource.

    Returned dict fields:
      name       (str)  - hostname or VM name
      vm_id      (int|None) - Proxmox VM ID, or None
      node_name  (str|None) - Proxmox node name, or None
      ip         (str|None) - primary routable IPv4, or None
      state_tags (list) - tags from state (Proxmox); empty for other providers
      provider   (str)  - "proxmox" | "maas"
    """
    info = extract_vm_info(state)
    if info is not None:
        return {
            "name":       info["name"],
            "vm_id":      info["vm_id"],
            "node_name":  info.get("node_name"),
            "ip":         get_primary_ip(info["ipv4_addresses"]),
            "state_tags": info["tags"],
            "provider":   "proxmox",
        }

    info = extract_maas_machine_info(state)
    if info is not None:
        return {
            "name":       info["hostname"],
            "vm_id":      None,
            "node_name":  None,
            "ip":         get_primary_maas_ip(info["ip_addresses"]),
            "state_tags": [],
            "provider":   "maas",
        }

    return None


# ---------------------------------------------------------------------------
# State parsing
# ---------------------------------------------------------------------------

def extract_vm_info(state: dict) -> Optional[dict]:
    """Return a dict with name, vm_id, node_name, tags, ipv4_addresses from a VM state file."""
    for resource in state.get("resources", []):
        if resource.get("type") != "proxmox_virtual_environment_vm":
            continue
        for instance in resource.get("instances", []):
            attrs = instance.get("attributes", {})
            return {
                "name":           attrs.get("name"),
                "vm_id":          attrs.get("vm_id"),
                "node_name":      attrs.get("node_name"),
                "tags":           list(attrs.get("tags") or []),
                "ipv4_addresses": list(attrs.get("ipv4_addresses") or []),
            }
    return None


def extract_maas_machine_info(state: dict) -> Optional[dict]:
    """Return hostname and ip_addresses from a maas-pxe-machine state file.

    Reads hostname from maas_machine (which reflects the MaaS-assigned hostname
    after the Terraform apply sets it) and ip_addresses from maas_instance (the
    deployed machine's IPs). Returns None if either resource is absent.
    """
    hostname = None
    ip_addresses = []
    for resource in state.get("resources", []):
        rtype = resource.get("type")
        for instance in resource.get("instances", []):
            attrs = instance.get("attributes", {})
            if rtype == "maas_machine":
                hostname = attrs.get("hostname")
            elif rtype == "maas_instance":
                ip_addresses = list(attrs.get("ip_addresses") or [])
    if hostname is None:
        return None
    return {"hostname": hostname, "ip_addresses": ip_addresses}


def get_primary_ip(ipv4_addresses: list) -> Optional[str]:
    """Return the first non-loopback IPv4 address across all interfaces."""
    for iface in ipv4_addresses:
        for addr in (iface or []):
            if addr and not addr.startswith("127.") and addr not in ("0.0.0.0", ""):
                return addr
    return None


def get_primary_maas_ip(ip_addresses: list) -> Optional[str]:
    """Return the first non-loopback IPv4 from a flat maas_instance.ip_addresses list."""
    for addr in (ip_addresses or []):
        if addr and not addr.startswith("127.") and addr not in ("0.0.0.0", ""):
            return addr
    return None


def extract_roles(tags: list) -> list:
    """Return role names from tags of the form 'role_<name>'."""
    return [t[5:] for t in tags if isinstance(t, str) and t.startswith("role_")]


# ---------------------------------------------------------------------------
# SSH verification
# ---------------------------------------------------------------------------

def check_ssh(host: str, user: str, timeout: int = 5,
              extra_args: Optional[list] = None) -> bool:
    """Check SSH reachability for a single host.

    extra_args: additional SSH flags (e.g. ProxyJump from ansible_ssh_common_args).
    These are inserted before the destination so options like -J work correctly.
    """
    cmd = [
        "ssh",
        "-o", f"ConnectTimeout={timeout}",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
    ]
    if extra_args:
        cmd.extend(extra_args)
    cmd += [f"{user}@{host}", "true"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout + 30,  # extra buffer for ProxyJump round-trip
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except FileNotFoundError:
        print("WARNING: ssh binary not found in PATH", file=sys.stderr)
        return False


def _parse_ssh_extra_args(args_str: str) -> list:
    """Split an ansible_ssh_common_args string into a list of tokens.

    Simple whitespace split that handles -J user@host and -o Option=Value.
    """
    if not args_str:
        return []
    import shlex  # noqa: PLC0415
    try:
        return shlex.split(args_str)
    except ValueError:
        return args_str.split()


def check_ssh_parallel(hosts: list, max_workers: int = 10) -> dict:
    """
    Check SSH for a list of (name, ip, user, params) dicts in parallel.
    Uses ansible_ssh_common_args (e.g. ProxyJump) from host params when present.
    Returns {name: bool}.
    """
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {}
        for h in hosts:
            if not h.get("ip"):
                continue
            extra = _parse_ssh_extra_args(
                (h.get("params") or {}).get("ansible_ssh_common_args", "")
            )
            futures[pool.submit(check_ssh, h["ip"], h["user"], 5, extra or None)] = h["name"]
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception:
                results[name] = False
    return results


# ---------------------------------------------------------------------------
# Group assignment
# ---------------------------------------------------------------------------

def assign_groups(roles: list, roles_filter: list) -> list:
    """
    Determine which Ansible groups a host belongs to.

    - No filter given         → one group per role name; no roles → ['_no_matching_role']
    - Filter given, matched   → one group per matched role name
    - Anything else           → ['_no_matching_role']
    """
    if not roles_filter:
        return list(roles) if roles else ["_no_matching_role"]
    matched = [r for r in roles if r in roles_filter]
    return matched if matched else ["_no_matching_role"]


# ---------------------------------------------------------------------------
# Host vars: flattening, filtering, and YAML output
# ---------------------------------------------------------------------------

def split_params(params: dict, provider_keys_mode: str, null_vars_mode: str) -> tuple:
    """
    Partition a params dict into (normal_params, commented_params).

    Operates only on top-level keys; nested structure is preserved as-is in
    normal_params so that yaml.dump can render it with proper nesting and lists.

    Provider keys (starting with '_provider_') are routed by provider_keys_mode:
      omit    – dropped entirely (default)
      include – added to normal_params
      comment – added to commented_params

    Non-provider keys with a None value are routed by null_vars_mode:
      omit    – dropped entirely (default)
      comment – added to commented_params as ''

    All other keys go to normal_params unchanged (nested dicts/lists intact).
    """
    normal: dict = {}
    commented: dict = {}
    for k, v in (params or {}).items():
        if k.startswith("_provider_"):
            val = "" if v is None else v
            if provider_keys_mode == "include":
                normal[k] = val
            elif provider_keys_mode == "comment":
                commented[k] = val
            # else: omit
        elif v is None:
            if null_vars_mode == "comment":
                commented[k] = ""
            # else: omit
        else:
            normal[k] = v
    return normal, commented


def _yaml_scalar(v) -> str:
    """Format a Python scalar as an inline YAML value with correct quoting.

    Delegates to PyYAML by rendering a one-item flow list and stripping the
    brackets, so all quoting rules (booleans, colons, special chars, etc.)
    are handled correctly.
    """
    if v is None:
        return "''"
    rendered = yaml.dump([v], default_flow_style=True, width=float("inf")).strip()
    return rendered[1:-1].strip()


def write_inventory_yaml(fh, inventory: dict, host_comments: dict) -> None:
    """Write Ansible inventory YAML, appending commented lines after each host's vars."""
    indent = "          "  # 10 spaces — host var level
    fh.write("all:\n")
    children = inventory.get("all", {}).get("children")
    if not children:
        fh.write("  {}\n")
        return
    fh.write("  children:\n")
    for group, group_data in sorted(children.items()):
        fh.write(f"    {group}:\n")
        hosts = group_data.get("hosts") or {}
        if not hosts:
            continue
        fh.write("      hosts:\n")
        for hostname, vars_dict in sorted(hosts.items()):
            fh.write(f"        {hostname}:\n")
            if vars_dict:
                dumped = yaml.dump(
                    vars_dict,
                    default_flow_style=False,
                    sort_keys=True,
                    allow_unicode=True,
                )
                for line in dumped.splitlines():
                    fh.write(f"{indent}{line}\n")
            for k, v in sorted((host_comments.get(hostname) or {}).items()):
                fh.write(f"{indent}# {k}: {_yaml_scalar(v)}\n")


# ---------------------------------------------------------------------------
# PVE hosts group (from YAML config, independent of Terraform state)
# ---------------------------------------------------------------------------

def build_pve_hosts_group(proxmox_config_params: dict) -> dict:
    """Build a 'pve_hosts' group from providers.proxmox.config_params pve-node entries.

    Returns a dict of the form
    {"hosts": {<node_name>: {<host_vars>}}} or {} if no pve-node entries found.

    Bridge configuration is emitted as pve_bridges (list of bridge dicts).
    If the pve-node config has a 'bridges:' key, it is passed through directly.
    Otherwise, the old flat fields (bridge_technology, vlan_bridge, cloud_public_ip,
    gateway) are synthesized into a single-entry pve_bridges list for backward
    compatibility.
    """
    hosts = {}
    for path, params in (proxmox_config_params or {}).items():
        m = re.search(r"pve-nodes/([^/]+)$", path)
        if not m:
            continue
        host_name = m.group(1)
        if not isinstance(params, dict) or "ansible_host" not in params:
            continue

        # Build pve_bridges list.
        if "bridges" in params:
            # New declarative schema — pass through as-is.
            pve_bridges = params["bridges"]
        else:
            # Backward-compat: synthesize from flat fields.
            cloud_public_ip = params.get("cloud_public_ip", "")
            bridge = {
                "name": params.get("vlan_bridge", "vmbr0"),
                "nic": "",
                "technology": params.get("bridge_technology", "vlan-aware"),
                "host_ip": cloud_public_ip,
                "host_vlan": 10 if cloud_public_ip else None,
                "gateway": "",  # don't change the provisioning gateway
                "comment": "primary bridge (auto-migrated from flat config)",
            }
            pve_bridges = [bridge]

        host_vars = {
            "ansible_host":      params["ansible_host"],
            "ansible_user":      params.get("ansible_user", "root"),
            "pve_node":          params.get("node_name", params.get("pve_node", "")),
            "pve_datastore_iso": params.get("datastore_iso", "local"),
            "pve_api_token_id":  params.get("api_token_id", "tg-token"),
            "pve_config_path":   path,
            "pve_bridges":       pve_bridges,
        }
        if "ansible_ssh_common_args" in params:
            host_vars["ansible_ssh_common_args"] = params["ansible_ssh_common_args"]
        hosts[host_name] = host_vars
    if not hosts:
        return {}
    return {"hosts": dict(sorted(hosts.items()))}


# ---------------------------------------------------------------------------
# Inventory builder
# ---------------------------------------------------------------------------

def build_inventory(
    vm_records: list,
    roles_filter: list,
    only_matched: bool,
    provider_keys_mode: str = "omit",
    null_vars_mode: str = "omit",
) -> tuple:
    """
    Build the Ansible inventory dict and per-host comment dicts.

    vm_records is a list of dicts with keys:
      name, ip, user, roles, params, ssh_ok

    Returns (inventory, host_comments) where host_comments maps hostname to
    a flat dict of vars that should appear commented-out in the output.
    """
    groups: dict = {}
    host_comments: dict = {}

    for vm in vm_records:
        host_groups = assign_groups(vm["roles"], roles_filter)

        if only_matched and host_groups == ["_no_matching_role"]:
            continue

        normal_params, commented_params = split_params(
            vm.get("params") or {}, provider_keys_mode, null_vars_mode
        )

        # For Proxmox VMs: QEMU agent IP always wins over any YAML ansible_host
        # (parent pve-node entries have ansible_host set to the PVE host IP, which
        # must not bleed into child VMs).
        # For MaaS machines: if the YAML explicitly sets ansible_host, trust it.
        # MaaS ip_addresses is a set of all DHCP leases ever issued to the machine;
        # when a machine has multiple leases (e.g. commissioning + deployment phases),
        # the lexicographically-first IP may be a stale lease that is no longer active.
        effective_ip = (
            normal_params.get("ansible_host") or vm["ip"]
            if vm.get("provider") == "maas"
            else vm["ip"]
        )
        host_vars = {
            **normal_params,
            "ansible_host": effective_ip,
            "ansible_user": vm["user"],
        }

        for group in host_groups:
            groups.setdefault(group, {})[vm["name"]] = host_vars

        if commented_params:
            host_comments[vm["name"]] = commented_params

    if not groups:
        return {"all": {}}, {}

    inventory = {
        "all": {
            "children": {
                group: {"hosts": dict(sorted(hosts.items()))}
                for group, hosts in sorted(groups.items())
            }
        }
    }
    return inventory, host_comments


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args(defaults=None):
    if defaults is None:
        defaults = {}
    parser = argparse.ArgumentParser(
        description="Generate an Ansible inventory from Terragrunt lab stack state.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--roles",
        metavar="ROLE1,ROLE2,...",
        default=defaults.get("roles", ""),
        help=(
            "Comma-separated list of role names to put in their own host groups. "
            "Hosts with role_* tags not in this list go to 'role_did_not_match'. "
            "If omitted, every role_* tag becomes a group."
        ),
    )
    parser.add_argument(
        "--only-matched",
        action="store_true",
        default=defaults.get("only_matched", False),
        help="Only include hosts that have at least one matched role (skip no_role and role_did_not_match).",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        default=defaults.get("output_file", "hosts.yml"),
        help="Output file path (default: hosts.yml).",
    )
    parser.add_argument(
        "--no-ssh-check",
        action="store_true",
        default=not defaults.get("ssh_check", True),
        help="Skip SSH reachability verification.",
    )
    parser.add_argument(
        "--exclude-unreachable",
        action="store_true",
        default=defaults.get("exclude_unreachable", False),
        help="Exclude hosts that fail the SSH check from the inventory.",
    )
    parser.add_argument(
        "--fail-on-unreachable",
        action="store_true",
        default=defaults.get("fail_on_unreachable", False),
        help=(
            "Exit non-zero if any host fails the SSH check. "
            "Use in --build mode so the pipeline aborts when hosts are unreachable."
        ),
    )
    parser.add_argument(
        "--wave",
        metavar="NAME",
        default=None,
        help=(
            "Current wave name (from config/framework.yaml waves[].name). "
            "When set, SSH failures for hosts whose _wave param does not match NAME "
            "are downgraded to warnings — the host remains in the inventory but the "
            "failure does not trigger --fail-on-unreachable. Hosts with no _wave param "
            "or _wave matching NAME are checked strictly."
        ),
    )
    parser.add_argument(
        "--provider-keys",
        choices=["omit", "include", "comment"],
        default=defaults.get("provider_keys", "omit"),
        help=(
            "How to handle _provider_* config params in host vars. "
            "omit (default): drop them. include: add as normal vars. "
            "comment: write as commented-out lines."
        ),
    )
    parser.add_argument(
        "--null-vars",
        choices=["omit", "comment"],
        default=defaults.get("null_vars", "omit"),
        help=(
            "How to handle config params with null/None values. "
            "omit (default): drop them. comment: write as commented-out lines with value ''."
        ),
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help=(
            "Path to framework.yaml. "
            "Defaults to config/framework.yaml (relative to git root)."
        ),
    )
    parser.add_argument(
        "--stack-root",
        metavar="PATH",
        default=None,
        help=(
            "Path to the lab stack root (directory containing root.hcl). "
            "Defaults to the parent of this script's directory."
        ),
    )
    return parser.parse_args()


def resolve_config_path(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    infra_dir = os.environ.get("_INFRA_DIR")
    if not infra_dir:
        sys.exit(
            "ERROR: $_INFRA_DIR is not set. "
            "Run: source $(git rev-parse --show-toplevel)/set_env.sh"
        )
    git_root = str(Path(infra_dir).parent)
    # Primary location: split framework_*.yaml files in infra/_framework-pkg/_config/
    config_dir = os.path.join(git_root, "infra", "_framework-pkg", "_config")
    if os.path.isdir(config_dir) and any(Path(config_dir).glob("framework_*.yaml")):
        return config_dir
    sys.exit("ERROR: could not find framework_*.yaml files in infra/_framework-pkg/_config/")


def resolve_stack_root(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    # Script lives in <stack_root>/framework/generate-ansible-inventory/
    return str(Path(__file__).resolve().parent.parent.parent)


def main():
    # Pre-load ansible_inventory defaults from config (best-effort).
    # $_CONFIG_DIR must already be set (the `run` script sources set_env.sh).
    # CLI args passed explicitly will still override these.
    inv_defaults = {}
    if os.environ.get("_INFRA_DIR"):
        try:
            default_config_path = resolve_config_path(None)
            pre_cfg = load_stack_config(default_config_path)
            inv_defaults = pre_cfg.get("ansible_inventory") or {}
        except Exception:
            pass  # Missing config section — fall back to argparse defaults

    args = parse_args(inv_defaults)

    roles_filter = [r.strip() for r in args.roles.split(",") if r.strip()]

    config_path = resolve_config_path(args.config)
    stack_root  = resolve_stack_root(args.stack_root)

    print(f"Config : {config_path}", file=sys.stderr)
    print(f"Stack  : {stack_root}", file=sys.stderr)

    # ── Load config ────────────────────────────────────────────────────────
    stack_cfg = load_stack_config(config_path)
    backend_type, backend_config = (
        stack_cfg["backend"]["type"],
        stack_cfg["backend"].get("config", {}),
    )
    print(f"Backend: {backend_type}", file=sys.stderr)

    fetcher = make_fetcher(backend_type, backend_config, stack_root)

    # ── Build a merged config_params map for ancestor-merge lookups ────────
    # Read pre-merged, pre-decrypted config from $_CONFIG_DIR (written by
    # config-mgr generate, which runs before any inventory generation).
    # config_params are stored flat under the package top-level key.
    config_dir_env = os.environ.get("_CONFIG_DIR")
    if not config_dir_env:
        sys.exit(
            "ERROR: $_CONFIG_DIR is not set. "
            "Run: source $(git rev-parse --show-toplevel)/set_env.sh"
        )
    config_dir_path = Path(config_dir_env)

    all_config_params: dict = {}
    for pkg_config_file in sorted(config_dir_path.glob("*.yaml")):
        if pkg_config_file.name.endswith(".secrets.yaml"):
            continue
        try:
            raw = yaml.safe_load(pkg_config_file.read_text()) or {}
            for pkg_key, pkg_val in raw.items():
                if not isinstance(pkg_val, dict):
                    continue
                cp = pkg_val.get("config_params") or {}
                if isinstance(cp, dict):
                    all_config_params.update(cp)
        except Exception:
            pass

    # ── Build PVE hosts group from YAML config (no state required) ─────────
    proxmox_config_params: dict = {}
    for pkg_config_file in sorted(config_dir_path.glob("*.yaml")):
        if pkg_config_file.name.endswith(".secrets.yaml"):
            continue
        try:
            raw = yaml.safe_load(pkg_config_file.read_text()) or {}
            for pkg_key, pkg_val in raw.items():
                if not isinstance(pkg_val, dict):
                    continue
                cp = pkg_val.get("config_params") or {}
                if not isinstance(cp, dict):
                    continue
                for path, params in cp.items():
                    if isinstance(params, dict) and params.get("_provider") == "proxmox":
                        proxmox_config_params[path] = params
        except Exception:
            pass
    pve_hosts_group = build_pve_hosts_group(proxmox_config_params)
    if pve_hosts_group:
        pve_names = list(pve_hosts_group["hosts"])
        print(f"PVE hosts ({len(pve_names)}): {pve_names}", file=sys.stderr)

    # ── Discover all infra units and build host records ────────────────────
    # Host detection uses ansible_inventory.modules_to_include from the YAML:
    # a unit is a host iff its terragrunt.hcl source matches one of those
    # module paths. The unit's own config_params _is_host key (never inherited)
    # overrides. additional_tags (and all other params) are still fully inherited
    # from ancestors and used for group/role assignment.
    inv_cfg = stack_cfg.get("ansible_inventory") or {}
    modules_to_include = inv_cfg.get("modules_to_include") or []
    infra_root = str(Path(stack_root) / "infra")

    all_units = find_all_unit_paths(stack_root)
    print(f"Found {len(all_units)} infra unit(s) total.", file=sys.stderr)

    vm_records = []
    for rel_path in all_units:
        params = merge_ancestor_params(all_config_params, rel_path)
        own_params = all_config_params.get(rel_path) or {}

        # Skip non-host units (ISOs, snippets, null configs, cloud buckets, etc.)
        if not unit_is_host(infra_root, rel_path, modules_to_include, own_params):
            continue

        # Roles come from merged additional_tags (inheritance fully preserved).
        config_roles = extract_roles(params.get("additional_tags") or [])

        # ansible_user in the unit's own config overrides cloud_init_user (useful for
        # images whose default SSH user differs from the cloud-init user, e.g. Kairos Rocky
        # uses "rocky" while the pve-node parent has cloud_init_user="ubuntu").
        cloud_init_user = (
            own_params.get("ansible_user")
            or params.get("cloud_init_user", "ubuntu")
        )

        try:
            state = fetcher.fetch(rel_path)
        except StateFetchError as exc:
            print(f"WARNING: {exc}", file=sys.stderr)
            continue

        if state is None:
            print(
                f"  SKIP {rel_path}: no state at {fetcher.state_path(rel_path)}",
                file=sys.stderr,
            )
            continue

        host_info = extract_host_info(state)
        if host_info is None:
            print(
                f"  SKIP {rel_path}: state contains no recognised host resource",
                file=sys.stderr,
            )
            continue

        ip = host_info["ip"]
        if not ip:
            print(
                f"  SKIP {host_info['name']}: no routable IPv4 address in state",
                file=sys.stderr,
            )
            continue

        # Roles: state tags (Proxmox carries tags in state) + config_params additional_tags.
        # Merging both means YAML is the source of truth even before 'terragrunt apply'
        # pushes the tags into the provider's state.
        state_roles = extract_roles(host_info["state_tags"])
        roles = list(dict.fromkeys(state_roles + config_roles))  # merge, dedup, preserve order

        # Inject ProxyJump for hosts on isolated VLANs (e.g. MaaS machines on VLAN 12).
        # maas_server_ip is set in config_params for paths under pwy-home-lab-pkg/_stack/maas/pwy-homelab.
        # Skip the injection when the VM's own IP IS the MaaS server (self-jump).
        host_params = dict(params)
        maas_server_ip = params.get("maas_server_ip", "")
        if maas_server_ip and ip != maas_server_ip:
            host_params.setdefault(
                "ansible_ssh_common_args",
                f"-o StrictHostKeyChecking=no -J ubuntu@{maas_server_ip}",
            )

        vm_records.append({
            "name":      host_info["name"],
            "vm_id":     host_info["vm_id"],
            "node_name": host_info["node_name"],
            "provider":  host_info["provider"],
            "ip":        ip,
            "user":      cloud_init_user,
            "tags":      host_info["state_tags"],
            "roles":     roles,
            "params":    host_params,
            "ssh_ok":    None,  # filled in below
        })
        print(
            f"  OK   {host_info['name']:30s}  ip={ip:15s}  user={cloud_init_user:10s}  "
            f"provider={host_info['provider']:8s}  roles={roles or ['(none)']}",
            file=sys.stderr,
        )

    if not vm_records:
        if pve_hosts_group:
            print(
                "WARNING: No hosts with routable IPs found in state; "
                "inventory will contain only pve_hosts.",
                file=sys.stderr,
            )
        else:
            print(
                "WARNING: No hosts found in state and no PVE hosts configured. "
                "Writing empty inventory.",
                file=sys.stderr,
            )

    # ── Disambiguate duplicate VM names ────────────────────────────────────
    name_counts: dict = {}
    for vm in vm_records:
        name_counts[vm["name"]] = name_counts.get(vm["name"], 0) + 1
    duplicates = {n for n, c in name_counts.items() if c > 1}
    if duplicates:
        print(f"Disambiguating duplicate names: {sorted(duplicates)}", file=sys.stderr)
        for vm in vm_records:
            if vm["name"] in duplicates:
                node = vm.get("node_name") or vm.get("provider") or "unknown"
                vm["name"] = f"{vm['name']}-{node}"

    # ── SSH verification ───────────────────────────────────────────────────
    if args.no_ssh_check:
        print("SSH check: skipped (--no-ssh-check)", file=sys.stderr)
        for vm in vm_records:
            vm["ssh_ok"] = None
    else:
        # Hosts with skip_ssh_check: true in their config_params are excluded
        # from SSH verification (e.g. Kairos/immutable OS VMs that don't run sshd).
        check_hosts = [vm for vm in vm_records
                       if not (vm.get("params") or {}).get("skip_ssh_check")]
        skip_hosts  = [vm for vm in vm_records
                       if (vm.get("params") or {}).get("skip_ssh_check")]
        for vm in skip_hosts:
            vm["ssh_ok"] = None
            print(f"  SSH SKIP  {vm['user']}@{vm['ip']}  ({vm['name']}) [skip_ssh_check=true]",
                  file=sys.stderr)

        print(f"SSH check: verifying {len(check_hosts)} host(s) in parallel…", file=sys.stderr)
        ssh_results = check_ssh_parallel(check_hosts)
        for vm in check_hosts:
            ok = ssh_results.get(vm["name"], False)
            vm["ssh_ok"] = ok
            status = "OK" if ok else "FAIL"
            print(f"  SSH {status:4s}  {vm['user']}@{vm['ip']}  ({vm['name']})", file=sys.stderr)

        failed = [vm for vm in check_hosts if vm["ssh_ok"] is False]
        if failed:
            # When --wave is given, split failures into in-wave (critical) and
            # out-of-wave (advisory).  Advisory failures are warned about but the
            # host stays in the inventory and does not trigger --fail-on-unreachable.
            # In-wave failures (or all failures when --wave is not given) go through
            # the normal exclude/fail logic unchanged.
            if args.wave:
                failed_advisory = [
                    vm for vm in failed
                    if (vm.get("params") or {}).get("_wave") != args.wave
                ]
                failed_critical = [vm for vm in failed if vm not in failed_advisory]
                for vm in failed_advisory:
                    vm_wave = (vm.get("params") or {}).get("_wave") or "(none)"
                    print(
                        f"  SSH WARN  {vm['user']}@{vm['ip']}  ({vm['name']}) "
                        f"[wave={vm_wave} \u2260 {args.wave} \u2014 ignored]",
                        file=sys.stderr,
                    )
                if failed_advisory:
                    print(
                        f"WARNING: {len(failed_advisory)} out-of-wave host(s) unreachable "
                        f"(kept in inventory): "
                        + ", ".join(v["name"] for v in failed_advisory),
                        file=sys.stderr,
                    )
                failed = failed_critical

            if failed:
                names = ", ".join(v["name"] for v in failed)
                if args.exclude_unreachable:
                    failed_set = set(id(v) for v in failed)
                    print(
                        f"WARNING: excluding {len(failed)} unreachable host(s): {names}",
                        file=sys.stderr,
                    )
                    vm_records = [vm for vm in vm_records if id(vm) not in failed_set]
                elif args.fail_on_unreachable:
                    sys.exit(
                        f"ERROR: {len(failed)} host(s) failed SSH check: {names}\n"
                        "Fix connectivity or use --no-ssh-check / --exclude-unreachable to override."
                    )
                else:
                    print(
                        f"WARNING: {len(failed)} host(s) failed SSH (included in inventory): {names}",
                        file=sys.stderr,
                    )

    # ── Build and write inventory ──────────────────────────────────────────
    inventory, host_comments = build_inventory(
        vm_records, roles_filter, args.only_matched,
        provider_keys_mode=args.provider_keys,
        null_vars_mode=args.null_vars,
    )

    # Merge PVE hosts group (populated from YAML config, independent of state).
    if pve_hosts_group:
        inv_children = inventory.setdefault("all", {}).setdefault("children", {})
        inv_children["pve_hosts"] = pve_hosts_group

    # Resolve output path: relative paths are anchored to $_DYNAMIC_DIR when set.
    output_path = args.output
    dynamic_dir = os.environ.get("_DYNAMIC_DIR")
    if dynamic_dir and not os.path.isabs(output_path):
        output_path = os.path.join(dynamic_dir, output_path)
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as fh:
        write_inventory_yaml(fh, inventory, host_comments)

    print(f"\nWrote inventory to: {output_path}", file=sys.stderr)

    # Print a summary of groups
    children = inventory.get("all", {}).get("children", {})
    for group, data in sorted(children.items()):
        hosts = data.get("hosts", {})
        print(f"  group '{group}': {list(hosts)}", file=sys.stderr)


if __name__ == "__main__":
    main()
