# Query the current view

The point of StreamHouse is not "we have Kafka" or "we have Iceberg". It is that **one SQL surface** sees historical and live operational data as a current picture of the business.

Open [`current_view.sql`](current_view.sql). Run those statements in **watsonx.data Presto**. The control tower snapshots the same warehouse files with PyArrow.

Try this progression:

1. `parcel_current` KPIs — how is Global Parcel running **right now**?
2. Hub breakdown — who is creating SLA pressure **this hour**?
3. `parcel_events` grouped by `origin_hub` — delay rate across the **whole captured stream**, including yesterday's replay.
4. One `parcel_id` — the same row an app and an AI tool would fetch.

History (`PCL-000001`) and live (`PCL-LIVE-000001`) are not federated from two ad-hoc copies. They are one continuously captured business.

The **IBM** version of this SQL runs in **watsonx.data** Presto over Iceberg plus the federated Kafka table `shipping_ops.default.fuel_surcharge` — [`../../02-lakehouse/README.md`](../../02-lakehouse/README.md).
