# MaaS RPC Isolation — Block Rack→Region Ports on Provisioning NIC

**Date**: 2026-04-13  
**Session**: maas-rpc-isolation

## Problem

The MaaS API became unresponsive during machine provisioning. Root cause: the rack
controller was connecting to the region controller via the provisioning NIC (`enp6s19`,
`10.0.12.2`) instead of the management NIC (`eth0`, `10.0.10.11`).

The `/MAAS/rpc/` endpoint advertises both IPs for each event loop, with `10.0.12.2`
listed first in some loops. The rack picked it as the first reachable address. During
active PXE provisioning that same NIC was simultaneously handling DHCP responses,
TFTP/HTTP boot image transfers, and the rack→region RPC stream, causing the RPC channel
to degrade and the API to hang.

Confirmed from journal:
```
ClusterClient connection established (HOST=10.0.12.2:60252 PEER=10.0.12.2:5252)
```

## Fix

Added iptables `INPUT DROP` rules for TCP 5250–5253 on every `rack_ip` defined in
`managed_networks` config. For this deployment: `10.0.12.2`.

This forces the rack to fall back to `10.0.10.11` (management NIC) for all region RPC
connections, separating provisioning traffic from internal cluster communication:

- `eth0` (10.0.10.11) — API traffic, rack→region RPC  
- `enp6s19` (10.0.12.2) — DHCP, TFTP/HTTP PXE, DNS

## Files Changed

- `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/configure-maas-networking.yaml`
  — added `_provisioning_rack_ips` collection and iptables DROP rules; persist step now
  always runs (removed conditional guard that caused stale `rules.v4` on re-runs)
- `infra/maas-pkg/_docs/README.md` — added "RPC Isolation" section documenting the
  problem, fix, and how to apply to a running server
- `scripts/ai-only-scripts/fix-maas-rpc-isolation/` — one-off script to apply the fix
  to the live server without a full rebuild

## Applied to Live Server

Rule confirmed active and persisted:
```
-A INPUT -d 10.0.12.2/32 -p tcp -m tcp --dport 5250:5253 -j DROP
```
