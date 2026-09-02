#!/usr/bin/env python3
"""Smoke-test Cassandra ledger tools against a local session 02 cluster."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "cassandra_ledger"))

from get_parcel_delivery_notes import get_parcel_delivery_notes  # noqa: E402
from get_parcel_latest_status import get_parcel_latest_status  # noqa: E402
from get_parcel_timeline import get_parcel_timeline  # noqa: E402
from reconcile_parcel_dispute import reconcile_parcel_dispute  # noqa: E402


def show(label: str, result) -> None:
    payload = result.content if hasattr(result, "content") else result
    print(f"=== {label} ===")
    print(json.dumps(payload, indent=2))


def main() -> None:
    parcel_id = sys.argv[1] if len(sys.argv) > 1 else "PCL-000001"
    show("get_parcel_latest_status", get_parcel_latest_status(parcel_id))
    show("get_parcel_delivery_notes", get_parcel_delivery_notes(parcel_id))
    timeline = get_parcel_timeline(parcel_id)
    payload = timeline.content if hasattr(timeline, "content") else timeline
    if payload.get("timeline"):
        payload = {**payload, "timeline": payload["timeline"][:3]}
    print("\n=== get_parcel_timeline (first 3 events) ===")
    print(json.dumps(payload, indent=2))
    show("reconcile_parcel_dispute", reconcile_parcel_dispute(parcel_id, "DELIVERED"))


if __name__ == "__main__":
    main()
