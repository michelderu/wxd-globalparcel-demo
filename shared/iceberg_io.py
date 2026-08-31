"""Open-table materialization for the laptop edition.

Production StreamHouse publishes Kafka topics as Apache Iceberg on object
storage. Here we write the same table contract as Parquet under data/warehouse
so the workshop runs on Python 3.11–3.14 without compiling Iceberg native
extensions. DuckDB queries the files; apps never see the difference.
"""

from __future__ import annotations

import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq

from shared.config import TABLE_ALERTS, TABLE_CURRENT, TABLE_EVENTS, TABLE_SURCHARGE, WAREHOUSE_DIR

_ARROW_FIELDS = {
    "parcel_id": pa.string(),
    "event_ts": pa.timestamp("us", tz="UTC"),
    "status": pa.string(),
    "hub_code": pa.string(),
    "hub_city": pa.string(),
    "hub_country": pa.string(),
    "region": pa.string(),
    "latitude": pa.float64(),
    "longitude": pa.float64(),
    "exception_code": pa.string(),
    "customer_eta": pa.timestamp("us", tz="UTC"),
    "delivery_note": pa.string(),
    "origin_hub": pa.string(),
    "destination_hub": pa.string(),
    "base_rate": pa.float64(),
    "fuel_surcharge": pa.float64(),
    "invoice_total": pa.float64(),
    "sla_risk": pa.bool_(),
    "sla_reason": pa.string(),
    "updated_at": pa.timestamp("us", tz="UTC"),
}

EVENT_FIELDS = [
    "parcel_id",
    "event_ts",
    "status",
    "hub_code",
    "hub_city",
    "hub_country",
    "region",
    "latitude",
    "longitude",
    "exception_code",
    "customer_eta",
    "delivery_note",
    "origin_hub",
    "destination_hub",
    "base_rate",
    "fuel_surcharge",
    "invoice_total",
    "sla_risk",
    "sla_reason",
]
SURCHARGE_FIELDS = ["region", "fuel_surcharge", "updated_at"]
ALERT_FIELDS = ["parcel_id", "event_ts", "hub_code", "region", "status", "sla_reason", "delivery_note"]

TABLE_FIELDS = {
    TABLE_EVENTS: EVENT_FIELDS,
    TABLE_CURRENT: EVENT_FIELDS,
    TABLE_SURCHARGE: SURCHARGE_FIELDS,
    TABLE_ALERTS: ALERT_FIELDS,
}

# Kept so tableflow can still "ensure" tables without a catalog service.
EVENT_SCHEMA = EVENT_FIELDS
SURCHARGE_SCHEMA = SURCHARGE_FIELDS
ALERT_SCHEMA = ALERT_FIELDS


def table_dir(ident: str) -> Path:
    return WAREHOUSE_DIR / ident.replace(".", "/")


def get_catalog() -> None:
    WAREHOUSE_DIR.mkdir(parents=True, exist_ok=True)
    return None


def ensure_table(catalog: Any, ident: str, schema: Any = None) -> str:
    table_dir(ident).mkdir(parents=True, exist_ok=True)
    return ident


def _coerce(name: str, value: Any) -> Any:
    field_type = _ARROW_FIELDS[name]
    if value is None or value == "":
        return False if pa.types.is_boolean(field_type) else None
    if pa.types.is_timestamp(field_type) and isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    if pa.types.is_boolean(field_type):
        return bool(value)
    return value


def _to_arrow(records: list[dict[str, Any]], field_names: Iterable[str]) -> pa.Table:
    names = list(field_names)
    arrays = [pa.array([_coerce(name, row.get(name)) for row in records], type=_ARROW_FIELDS[name]) for name in names]
    return pa.table(dict(zip(names, arrays)))


def empty_events_arrow() -> pa.Table:
    return pa.table({name: pa.array([], type=_ARROW_FIELDS[name]) for name in EVENT_FIELDS})


def append_records(table: str, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    dest = table_dir(table)
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"part-{time.time_ns()}.parquet"
    pq.write_table(_to_arrow(records, TABLE_FIELDS[table]), path)
    return len(records)


def overwrite_records(table: str, records: list[dict[str, Any]]) -> int:
    dest = table_dir(table)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if not records:
        return 0
    return append_records(table, records)


def scan_arrow(table: str) -> pa.Table:
    dest = table_dir(table)
    files = sorted(dest.glob("*.parquet")) if dest.exists() else []
    if not files:
        fields = TABLE_FIELDS.get(table, EVENT_FIELDS)
        return pa.table({name: pa.array([], type=_ARROW_FIELDS[name]) for name in fields})
    tables = [pq.read_table(path) for path in files]
    return pa.concat_tables(tables, promote_options="default")
