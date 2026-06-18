"""Shared Cassandra client for Global Parcel ledger tools (session 02 schema)."""

from __future__ import annotations

import os
from typing import Any

from cassandra.cluster import Cluster


KEYSPACE = os.environ.get("CASSANDRA_KEYSPACE", "globalparcel_ops")
HOST = os.environ.get("CASSANDRA_HOST", "host.docker.internal")
PORT = int(os.environ.get("CASSANDRA_PORT", "9042"))

TIMELINE_QUERY = """
SELECT parcel_id, event_ts, status, hub_code, region, latitude, longitude,
       exception_code, customer_eta
FROM parcel_events_by_parcel
WHERE parcel_id = %s
"""

_cluster: Cluster | None = None
_session = None


def get_session():
    """Return a cached Cassandra session for the workshop keyspace."""
    global _cluster, _session
    if _session is None:
        host = os.environ.get("CASSANDRA_HOST", "host.docker.internal")
        port = int(os.environ.get("CASSANDRA_PORT", "9042"))
        keyspace = os.environ.get("CASSANDRA_KEYSPACE", "globalparcel_ops")
        _cluster = Cluster([host], port=port)
        _session = _cluster.connect(keyspace)
    return _session


def fetch_timeline(parcel_id: str) -> list[dict[str, Any]]:
    """Load parcel events newest-first (table clustering order)."""
    rows = get_session().execute(TIMELINE_QUERY, [parcel_id])
    return [row_to_event(row) for row in rows]


def row_to_event(row: Any) -> dict[str, Any]:
    return {
        "event_ts": row.event_ts.isoformat() if row.event_ts else None,
        "status": row.status,
        "hub_code": row.hub_code,
        "region": row.region,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "exception_code": row.exception_code or "",
        "customer_eta": row.customer_eta.isoformat() if row.customer_eta else None,
    }
