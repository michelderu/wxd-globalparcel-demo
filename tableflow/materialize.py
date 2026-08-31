"""Tableflow analog: Kafka topics become Iceberg tables.

No batch ETL job. The same streams that power operations are continuously
materialized as open tables so SQL, apps, and AI share one current picture.

  parcel.events.enriched  →  globalparcel.parcel_events   (append)
  parcel.current          →  globalparcel.parcel_current  (overwrite snapshot)
  fuel.surcharge          →  globalparcel.fuel_surcharge  (overwrite snapshot)
  ops.sla.alerts          →  globalparcel.sla_alerts      (append)
"""

from __future__ import annotations

import argparse
import time
from collections import OrderedDict
from typing import Any

from shared.config import (
    KAFKA_BOOTSTRAP,
    TABLE_ALERTS,
    TABLE_CURRENT,
    TABLE_EVENTS,
    TABLE_SURCHARGE,
    TOPIC_ALERTS,
    TOPIC_CURRENT,
    TOPIC_ENRICHED,
    TOPIC_SURCHARGE,
)
from shared.iceberg_io import (
    append_records,
    ensure_table,
    get_catalog,
    overwrite_records,
    scan_arrow,
)
from shared.kafka_io import consumer


def _poll_values(c, timeout_ms: int = 200) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for recs in c.poll(timeout_ms=timeout_ms).values():
        for rec in recs:
            if rec.value:
                rows.append(rec.value)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kafka", default=KAFKA_BOOTSTRAP)
    parser.add_argument("--group", default="streamhouse-tableflow")
    parser.add_argument("--flush-seconds", type=float, default=2.0)
    args = parser.parse_args()

    catalog = get_catalog()
    events_tbl = ensure_table(catalog, TABLE_EVENTS)
    current_tbl = ensure_table(catalog, TABLE_CURRENT)
    surcharge_tbl = ensure_table(catalog, TABLE_SURCHARGE)
    alerts_tbl = ensure_table(catalog, TABLE_ALERTS)

    enriched = consumer(TOPIC_ENRICHED, f"{args.group}-enriched", bootstrap=args.kafka)
    current_c = consumer(TOPIC_CURRENT, f"{args.group}-current", bootstrap=args.kafka)
    surcharge_c = consumer(TOPIC_SURCHARGE, f"{args.group}-surcharge", bootstrap=args.kafka)
    alerts_c = consumer(TOPIC_ALERTS, f"{args.group}-alerts", bootstrap=args.kafka)

    current_state: OrderedDict[str, dict[str, Any]] = OrderedDict()
    surcharge_state: dict[str, dict[str, Any]] = {}
    try:
        for row in scan_arrow(current_tbl).to_pylist():
            pid = row.get("parcel_id")
            if pid:
                current_state[pid] = row
    except Exception:
        pass
    try:
        for row in scan_arrow(surcharge_tbl).to_pylist():
            region = row.get("region")
            if region:
                surcharge_state[region] = row
    except Exception:
        pass
    event_buffer: list[dict[str, Any]] = []
    alert_buffer: list[dict[str, Any]] = []
    last_flush = time.monotonic()
    appended = 0

    print("Tableflow running (Kafka → Iceberg). Ctrl+C to stop.", flush=True)
    print(f"  warehouse tables: {TABLE_EVENTS}, {TABLE_CURRENT}, {TABLE_SURCHARGE}, {TABLE_ALERTS}", flush=True)
    try:
        while True:
            event_buffer.extend(_poll_values(enriched))
            for row in _poll_values(current_c, timeout_ms=50):
                pid = row.get("parcel_id")
                if pid:
                    current_state[pid] = row
            for row in _poll_values(surcharge_c, timeout_ms=50):
                region = row.get("region")
                if region:
                    surcharge_state[region] = row
            alert_buffer.extend(_poll_values(alerts_c, timeout_ms=50))

            if time.monotonic() - last_flush < args.flush_seconds:
                continue

            if event_buffer:
                appended += append_records(events_tbl, event_buffer)
                print(f"iceberg append parcel_events +{len(event_buffer)} total={appended}", flush=True)
                event_buffer.clear()
            if current_state:
                overwrite_records(current_tbl, list(current_state.values()))
            if surcharge_state:
                overwrite_records(surcharge_tbl, list(surcharge_state.values()))
            if alert_buffer:
                append_records(alerts_tbl, alert_buffer)
                alert_buffer.clear()
            last_flush = time.monotonic()
    except KeyboardInterrupt:
        print("\nTableflow stopped.")
        if event_buffer:
            append_records(events_tbl, event_buffer)
        if current_state:
            overwrite_records(current_tbl, list(current_state.values()))
    finally:
        enriched.close()
        current_c.close()
        surcharge_c.close()
        alerts_c.close()


if __name__ == "__main__":
    main()
