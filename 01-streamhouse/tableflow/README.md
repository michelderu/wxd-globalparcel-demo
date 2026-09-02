# Tableflow analog — topics as Iceberg tables

Confluent Tableflow materializes Kafka topics as Apache Iceberg tables so analytical engines query streaming data without a handmade ETL estate.

`tableflow/materialize.py` is that idea on your laptop:

| Kafka topic | Iceberg table | Write style |
| --- | --- | --- |
| `parcel.events.enriched` | `globalparcel.parcel_events` | append |
| `parcel.current` | `globalparcel.parcel_current` | snapshot overwrite |
| `fuel.surcharge` | `globalparcel.fuel_surcharge` | snapshot overwrite |
| `ops.sla.alerts` | `globalparcel.sla_alerts` | append |

Warehouse files land in `data/warehouse/` as Parquet snapshots of those streams. In production this is Apache Iceberg on object storage plus a REST catalog; the **concept** is identical: the stream and the table are the same data.

```bash
PYTHONPATH=. python -m tableflow.materialize
```

**IBM query plane:** after this laptop materialization, load the same business into **watsonx.data** Iceberg and federate live Kafka `fuel.surcharge`. See [`../../02-lakehouse/README.md`](../../02-lakehouse/README.md).
