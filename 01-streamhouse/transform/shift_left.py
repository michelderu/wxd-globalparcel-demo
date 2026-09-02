"""Shift-left transform: raw scans become a business-ready stream.

Run from `01-streamhouse/` (after capture is producing):

    PYTHONPATH=. python -m transform.shift_left

Shift left means the business rules run on the stream, once, instead of
being re-implemented in every warehouse job and every app:

  surcharge join  — latest fuel.surcharge per region (held in process state)
  invoice_total   — base_rate + that surcharge
  sla_risk        — weather delay or past customer ETA without DELIVERED

Each scan is then written once to every engine that needs it:

  Cassandra        — parcel ledger (audit UI)
  OpenSearch       — tracking search (customer UI)
  Kafka enriched   — parcel.events.enriched (history for Tableflow)
  Kafka current    — parcel.current (latest row per parcel_id, compacted)
  Kafka alerts     — ops.sla.alerts (only when sla_risk is true)

The Flink SQL in flink/shift_left.sql is the same contract in production shape.
This Python loop is the laptop runtime.
"""

from __future__ import annotations

import argparse
import time

from shared.config import (
    DEFAULT_SURCHARGE,
    KAFKA_BOOTSTRAP,
    TOPIC_ALERTS,
    TOPIC_CURRENT,
    TOPIC_ENRICHED,
    TOPIC_EVENTS,
    TOPIC_SURCHARGE,
)
from shared.domain import enrich_event
from shared.ibm_sinks import connect_cassandra, connect_opensearch, write_cassandra, write_opensearch
from shared.kafka_io import consumer, producer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kafka", default=KAFKA_BOOTSTRAP)
    parser.add_argument("--group", default="streamhouse-transform")
    parser.add_argument(
        "--skip-ibm",
        action="store_true",
        help="Kafka-only (no Cassandra / OpenSearch). Default is to write both IBM engines.",
    )
    args = parser.parse_args()

    # Latest surcharge per region. Starts from defaults, then follows fuel.surcharge ticks.
    surcharge = dict(DEFAULT_SURCHARGE)
    prod = producer(args.kafka)
    events = consumer(TOPIC_EVENTS, f"{args.group}-events", bootstrap=args.kafka)
    ticks = consumer(TOPIC_SURCHARGE, f"{args.group}-surcharge", bootstrap=args.kafka)

    cass_cluster = cass_session = cass_prepared = os_client = None
    if not args.skip_ibm:
        print("Connecting to Cassandra ledger and OpenSearch index…", flush=True)
        cass_cluster, cass_session, cass_prepared = connect_cassandra()
        os_client = connect_opensearch()
        print("IBM engines ready: Cassandra + OpenSearch.", flush=True)

    print("Transform running (shift-left). Ctrl+C to stop.", flush=True)
    print(
        f"  {TOPIC_EVENTS} + {TOPIC_SURCHARGE} → Cassandra + OpenSearch + "
        f"{TOPIC_ENRICHED} / {TOPIC_CURRENT} / {TOPIC_ALERTS}",
        flush=True,
    )
    processed = 0
    try:
        while True:
            # Drain price ticks first so the next scan joins the current surcharge.
            for record in ticks.poll(timeout_ms=50).values():
                for rec in record:
                    row = rec.value or {}
                    if row.get("region"):
                        surcharge[row["region"]] = float(row["fuel_surcharge"])

            batches = events.poll(timeout_ms=250)
            if not batches:
                time.sleep(0.05)
                continue
            for recs in batches.values():
                for rec in recs:
                    event = rec.value or {}
                    if not event.get("parcel_id"):
                        continue
                    enriched = enrich_event(event, surcharge)
                    # Compacted current topic: same key overwrites → latest scan per parcel.
                    prod.send(TOPIC_ENRICHED, key=enriched["parcel_id"], value=enriched)
                    prod.send(TOPIC_CURRENT, key=enriched["parcel_id"], value=enriched)
                    if cass_session is not None and cass_prepared is not None:
                        write_cassandra(cass_session, cass_prepared, enriched)
                    if os_client is not None:
                        write_opensearch(os_client, enriched)
                    if enriched["sla_risk"]:
                        prod.send(
                            TOPIC_ALERTS,
                            key=enriched["parcel_id"],
                            value={
                                "parcel_id": enriched["parcel_id"],
                                "event_ts": enriched["event_ts"],
                                "hub_code": enriched["hub_code"],
                                "region": enriched["region"],
                                "status": enriched["status"],
                                "sla_reason": enriched["sla_reason"],
                                "delivery_note": enriched["delivery_note"],
                            },
                        )
                    processed += 1
                    if processed % 25 == 0:
                        print(
                            f"transformed={processed} last={enriched['parcel_id']} "
                            f"{enriched['status']} sla_risk={enriched['sla_risk']}",
                            flush=True,
                        )
            prod.flush()
    except KeyboardInterrupt:
        print("\nTransform stopped.")
    finally:
        prod.close()
        events.close()
        ticks.close()
        if cass_cluster is not None:
            cass_cluster.shutdown()
        if os_client is not None:
            os_client.close()


if __name__ == "__main__":
    main()
