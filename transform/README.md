# 2 — Transform (shift left)

Do the business work **on the stream**, then land it in the IBM engines that already ran this workshop.

The Python job in `shift_left.py` is the laptop runtime (you write it, like the Cassandra scripts). `flink/shift_left.sql` is the same contract in **Apache Flink SQL** — open source, downloadable, and what Confluent Cloud for Apache Flink runs in production.

## What "shift left" means here

For every scan:

1. Look up the **latest** fuel surcharge for that region.
2. Compute `invoice_total = base_rate + fuel_surcharge`.
3. Flag `sla_risk` on weather delay or missed ETA.
4. Write **once** into fit-for-purpose stores — no producer dual-write.

| Destination | Product | Consumer |
| --- | --- | --- |
| `globalparcel_ops.parcel_events_by_parcel` | **Cassandra / DataStax HCD** | Audit UI, Orchestrate ledger tools |
| `parcel-events-live` | **OpenSearch** | Customer tracking UI, Dashboards |
| `parcel.events.enriched` | Kafka → Tableflow → **watsonx.data Iceberg** | Control tower, Presto |
| `parcel.current` | Kafka compacted current state | Current view of the business |
| `ops.sla.alerts` | Kafka | Operations only |

```bash
PYTHONPATH=. python -m transform.shift_left
```

Wait for Cassandra to be healthy before this command (first boot ~1–2 minutes). `--skip-ibm` is Kafka-only, for debugging.

Hands-on with the same UIs and schema as before: [`../02-realtime-operations/README.md`](../02-realtime-operations/README.md).
