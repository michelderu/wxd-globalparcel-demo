# 01 — Capture the business

**Capture the business. Run the business.**

Part of the **[StreamHouse workshop](../README.md)** — first chapter: put Global Parcel on Kafka, shift-left into Cassandra, OpenSearch, and Iceberg, and open the apps on `:8088`.

Work from **this directory**. Keep `PYTHONPATH=.`. Use the workshop venv from the parent folder (`source ../.venv/bin/activate`).

### 1. Capture — put Global Parcel in motion

```bash
# When watsonx.data (Kind) must reach this broker, advertise a host IP Kind can route to:
export KAFKA_HOST_IP=$(hostname -I | awk '{print $1}')   # Linux; try 172.17.0.1 if Kind still fails
docker compose up -d
docker compose ps
```

Wait until **Cassandra** is `healthy` (first boot 1–2 minutes), **OpenSearch** answers on HTTP `:9200`, and **Kafka** is `healthy` on `:9092`:

```bash
docker compose exec cassandra nodetool status
curl -s http://localhost:9200
```

OpenSearch should return a JSON cluster name. Then put the business on the bus:

```bash
PYTHONPATH=. python -m capture.produce
```

This creates the topics, replays historical journeys (`PCL-000001` …), and streams live scans (`PCL-LIVE-…`) plus fuel surcharge ticks. Keep it running.

In another terminal, inspect capture (from inside the broker, use the compose listener):

```bash
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:29092 --list
```

You should see `parcel.events`, `fuel.surcharge`, and the downstream topics the transform will write (`parcel.events.enriched`, `parcel.current`, `ops.sla.alerts`). Kafka UI at [http://localhost:8080](http://localhost:8080) shows the same.

Details: [`capture/README.md`](capture/README.md).

### 2. Transform — shift left into IBM engines

In a second terminal (`cd 01-streamhouse`, venv active):

```bash
PYTHONPATH=. python -m transform.shift_left
```

Each scan is priced against the latest surcharge and SLA-flagged, then written to:

- **Cassandra** `globalparcel_ops.parcel_events_by_parcel` — ledger
- **OpenSearch** `parcel-events-live` — customer search
- Kafka `parcel.events.enriched` / `parcel.current` — for lakehouse Tableflow

Cassandra schema is created on first connect. Flink SQL for the same contract: [`transform/flink/shift_left.sql`](transform/flink/shift_left.sql).

Details: [`transform/README.md`](transform/README.md).

### 3. Query — warehouse current view

Laptop materialization (always on):

```bash
PYTHONPATH=. python -m tableflow.materialize
```

Topics become open tables under `data/warehouse/`. The same SQL in [`query/current_view.sql`](query/current_view.sql) is what you run in watsonx.data next ([`../02-data-federation/README.md`](../02-data-federation/README.md)).

Details: [`tableflow/README.md`](tableflow/README.md), [`query/README.md`](query/README.md).

### 4. Run — apps on those products

```bash
PYTHONPATH=. uvicorn apps.api:app --host 0.0.0.0 --port 8088
```

| You want to show | Open |
| --- | --- |
| Current picture of the business | http://localhost:8088/tower/ |
| Customer “where is my parcel?” | http://localhost:8088/customer-ui/ (**OpenSearch**) |
| Dispute / source of truth | http://localhost:8088/audit-ui/ (**Cassandra**) |

Details: [`apps/README.md`](apps/README.md). Next: query this business in watsonx.data ([`../02-data-federation/README.md`](../02-data-federation/README.md)), then the operations walkthrough ([`../03-realtime-operations/README.md`](../03-realtime-operations/README.md)).

---

## Stop

Ctrl+C the Python processes, then from this folder:

```bash
docker compose down
rm -rf data/
```
