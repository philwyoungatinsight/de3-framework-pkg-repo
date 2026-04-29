"""GCS status helpers for the wave runner."""
from __future__ import annotations
import json
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path


def _bucket() -> str:
    import os
    bucket = os.environ.get("_GCS_BUCKET")
    if not bucket:
        raise RuntimeError("_GCS_BUCKET is not set — source set_env.sh before running")
    return bucket


def _ts() -> str:
    """ISO-8601 UTC timestamp safe for GCS keys (colons → hyphens)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _gcs_put_async(uri: str, payload: dict) -> None:
    """Write JSON to a GCS URI in a background thread (fire-and-forget)."""
    data = json.dumps(payload).encode()

    def _run():
        proc = subprocess.Popen(
            ["gsutil", "cp", "-", uri],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.communicate(data)

    threading.Thread(target=_run, daemon=True).start()


def write_wave_status(
    wave_name: str,
    phase: str,
    status: str,
    *,
    started_at: str | None = None,
    units_total: int = 0,
    units_ok: int = 0,
    units_fail: int = 0,
) -> None:
    """
    Write wave_status/<wave_name>/<ts>.json.
    Call with status='running' at phase start, status='ok'|'fail' at phase end.
    """
    try:
        bucket = _bucket()
    except Exception:
        return  # never block the wave runner if GCS config is missing

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload: dict = {
        "wave_name": wave_name,
        "phase": phase,
        "status": status,
        "updated_at": now,
        "units_total": units_total,
        "units_ok": units_ok,
        "units_fail": units_fail,
    }
    if started_at:
        payload["started_at"] = started_at
    if status in ("ok", "fail"):
        payload["finished_at"] = now
    uri = f"gs://{bucket}/wave_status/{wave_name}/{_ts()}.json"
    _gcs_put_async(uri, payload)
