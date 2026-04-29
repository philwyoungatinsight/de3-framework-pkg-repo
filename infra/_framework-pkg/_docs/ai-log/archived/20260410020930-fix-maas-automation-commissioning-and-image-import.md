---
date: 2026-04-10
title: Fix MaaS rackd DNS failure causing UI "trying to reconnect"
tags: [maas, rackd, dns, ansible, fix]
---

## Problem

MaaS UI (`http://10.0.10.11:5240/MAAS/r/machines`) frequently showed a "trying to reconnect"
overlay when navigating between pages. The rackd log showed:

```
twisted.internet.error.DNSLookupError: DNS lookup failed: Couldn't find the hostname '10.0.10.11'
```

This repeated every ~11 seconds.

## Root Cause

`rackd.conf` was configured with `maas_url: http://10.0.10.11:5240/MAAS`. Twisted's async DNS
resolver (used by rackd) sends real A-record DNS queries for ALL strings in URLs — including bare
IP addresses. Querying `10.0.10.11` as an A-record returns NXDOMAIN from both systemd-resolved
(`127.0.0.53`) and the MaaS bind9 nameserver, because `10.0.10.11` is not a valid hostname in
any zone file.

As a result, rackd never successfully connected to regiond (`connected: None`), causing WebSocket
instability and the UI reconnect overlay.

## Fix

### 1. Changed `_maas_url` to use hostname instead of IP

In `install-maas.yaml`, changed:
```yaml
_maas_url: "http://{{ ansible_host }}:5240/MAAS"
```
to:
```yaml
_maas_url: "http://{{ ansible_hostname }}:5240/MAAS"
```

This affects both `maas init` (for new deployments) and the idempotent URL update block (for
existing deployments).

### 2. Added idempotent `maas config --maas-url` update

Direct edits to `rackd.conf` do not persist — MaaS snap regenerates it from its own config store
on every restart. Added a task block that:
- Reads the current snap config with `maas config --parsable`
- Only calls `maas config --maas-url` if the URL has changed
- Restarts the snap if the URL was updated
- Waits for the API to recover

### 3. Patched cloud-init `/etc/hosts` template for persistence

cloud-init regenerates `/etc/hosts` on every boot from `/etc/cloud/templates/hosts.debian.tmpl`.
By default, the template maps the hostname to `127.0.1.1` (loopback). For systemd-resolved to
return the correct IP when rackd queries `maas-server-1`, the hostname must resolve to a routable
address.

Added two tasks to patch both the live `/etc/hosts` and the cloud-init template:
- Replace `^127\.0\.1\.1 ` with `{{ ansible_host }} ` in both files

### 4. Updated `verify-maas.yaml`

Changed `_maas_verify_url` to also use `ansible_hostname` so verification uses the same URL
pattern as installation.

## Result

- `rackd.conf`: `maas_url: http://maas-server-1:5240/MAAS`
- Zero DNS errors in rackd log
- rackd: "Fully connected to all 4 event-loops on all 1 region controllers (maas-server-1)"
- cloud-init template patched: `10.0.10.11 {{fqdn}} {{hostname}}`

## Files Changed

- `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/install-maas.yaml`
- `infra/maas-pkg/_tg_scripts/maas/configure-server/tasks/verify-maas.yaml`
