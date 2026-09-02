"""IBM operational engines: Cassandra ledger + OpenSearch customer index.

StreamHouse captures once on Kafka, then the transform writes into the
fit-for-purpose engines from the hybrid lakehouse edition:

- DataStax HCD / Apache Cassandra — authoritative parcel ledger
- OpenSearch — customer-facing tracking search
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from cassandra.cluster import Cluster
from cassandra.query import PreparedStatement
from opensearchpy import OpenSearch

from shared.config import CASSANDRA_HOST, CASSANDRA_KEYSPACE, CASSANDRA_PORT, OPENSEARCH_INDEX, OPENSEARCH_URL
from shared.domain import parse_iso

SCHEMA_CQL = [
    f"""
    CREATE KEYSPACE IF NOT EXISTS {CASSANDRA_KEYSPACE}
    WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}
    """,
    f"""
    CREATE TABLE IF NOT EXISTS {CASSANDRA_KEYSPACE}.parcel_events_by_parcel (
      parcel_id text,
      event_ts timestamp,
      status text,
      hub_code text,
      region text,
      latitude double,
      longitude double,
      exception_code text,
      customer_eta timestamp,
      delivery_note text,
      PRIMARY KEY ((parcel_id), event_ts)
    ) WITH CLUSTERING ORDER BY (event_ts DESC)
    """,
]

OS_INDEX_BODY = {
    "settings": {"index": {"number_of_shards": 1, "number_of_replicas": 0}},
    "mappings": {
        "properties": {
            "parcel_id": {"type": "keyword"},
            "event_ts": {"type": "date"},
            "status": {"type": "keyword"},
            "hub_code": {"type": "keyword"},
            "region": {"type": "keyword"},
            "exception_code": {"type": "keyword"},
            "customer_eta": {"type": "date"},
            "geo_position": {"type": "geo_point"},
            "sla_risk": {"type": "boolean"},
            "invoice_total": {"type": "float"},
        }
    },
}


def _as_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return parse_iso(str(value))


def connect_cassandra(retries: int = 60) -> tuple[Cluster, Any, PreparedStatement]:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
            session = cluster.connect()
            for stmt in SCHEMA_CQL:
                session.execute(stmt)
            session.set_keyspace(CASSANDRA_KEYSPACE)
            prepared = session.prepare(
                """
                INSERT INTO parcel_events_by_parcel (
                  parcel_id, event_ts, status, hub_code, region, latitude, longitude,
                  exception_code, customer_eta, delivery_note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
            )
            return cluster, session, prepared
        except Exception as exc:
            last = exc
            time.sleep(2)
    raise RuntimeError(f"Cassandra not ready on {CASSANDRA_HOST}:{CASSANDRA_PORT}") from last


def connect_opensearch(retries: int = 30) -> OpenSearch:
    last: Exception | None = None
    for _ in range(retries):
        try:
            client = OpenSearch(hosts=[OPENSEARCH_URL])
            client.info()
            if not client.indices.exists(index=OPENSEARCH_INDEX):
                client.indices.create(index=OPENSEARCH_INDEX, body=OS_INDEX_BODY)
            return client
        except Exception as exc:
            last = exc
            time.sleep(2)
    raise RuntimeError(f"OpenSearch not ready at {OPENSEARCH_URL}") from last


def write_cassandra(session: Any, prepared: PreparedStatement, event: dict[str, Any]) -> None:
    session.execute(
        prepared,
        (
            event["parcel_id"],
            _as_dt(event.get("event_ts")),
            event.get("status"),
            event.get("hub_code"),
            event.get("region"),
            event.get("latitude"),
            event.get("longitude"),
            event.get("exception_code") or None,
            _as_dt(event.get("customer_eta")),
            event.get("delivery_note") or "",
        ),
    )


def write_opensearch(client: OpenSearch, event: dict[str, Any]) -> None:
    event_ts = event.get("event_ts")
    doc = {
        "parcel_id": event["parcel_id"],
        "event_ts": event_ts,
        "status": event.get("status"),
        "hub_code": event.get("hub_code"),
        "region": event.get("region"),
        "exception_code": event.get("exception_code") or "",
        "customer_eta": event.get("customer_eta"),
        "geo_position": {"lat": event.get("latitude"), "lon": event.get("longitude")},
        "sla_risk": bool(event.get("sla_risk")),
        "invoice_total": event.get("invoice_total"),
    }
    doc_id = f"{event['parcel_id']}:{event_ts}"
    client.index(index=OPENSEARCH_INDEX, id=doc_id, body=doc, refresh=False)
