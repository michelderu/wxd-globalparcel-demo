# 01 — Capture the business 🚚

**Capture the business. Run the business.**

Part of the **[StreamHouse workshop](../README.md)** — first chapter: put Global Parcel on Kafka, shift-left into Cassandra, OpenSearch, and Iceberg, and open the control tower on `:8088`.

Work from **this directory**. Keep `PYTHONPATH=.`. Use the workshop venv from the parent folder (`source ../.venv/bin/activate`).

```bash
pip install -U pip
pip install -r requirements.txt
```

That also covers chapter 03 (same FastAPI, Cassandra, and OpenSearch clients).

### 1. Capture — put Global Parcel in motion

```bash
# When watsonx.data (Kind) must reach this broker, advertise a host IP Kind can route to:
export KAFKA_HOST_IP=$(hostname -I | awk '{print $1}')   # Linux; try 172.17.0.1 if Kind still fails
docker compose up -d
docker compose ps
```

**Engines started in this chapter:**

- **Apache Kafka** (message bus; powered by Docker Compose)
- **Apache Cassandra** (authoritative parcel ledger)
- **OpenSearch** (customer tracking & search)
- **Kafka UI** (web interface at [http://localhost:8085](http://localhost:8085))

Wait until **Cassandra** is `healthy` (first boot 1–2 minutes), **OpenSearch** answers on HTTP `:9200`, and **Kafka** is `healthy` on `:9092`:

```bash
docker compose exec cassandra nodetool status
curl -s http://localhost:9200
docker compose exec kafka /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092
```

Then put the business on the bus:

```bash
PYTHONPATH=. python -m capture.produce
```

This creates the topics, replays historical journeys (`PCL-000001` …), and streams live scans (`PCL-LIVE-…`) plus fuel surcharge ticks. Keep it running.

In another terminal, inspect capture (from inside the broker, use the compose listener):

```bash
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:29092 --list
```

You should see `parcel.events`, `fuel.surcharge`, and the downstream topics the transform will write (`parcel.events.enriched`, `parcel.current`, `ops.sla.alerts`). Kafka UI at [http://localhost:8085](http://localhost:8085) shows the same.

Details: [`capture/README.md`](capture/README.md).

### 2. Transform — shift left into IBM engines

In production this job is **Apache Flink**: a continuous SQL pipeline that joins live scans to the latest fuel surcharge, prices the invoice, flags SLA risk, and writes once into Cassandra, OpenSearch, and Kafka. The contract is in [`transform/flink/shift_left.sql`](transform/flink/shift_left.sql) — the same shape Confluent Cloud for Apache Flink runs.

On the laptop you run a **Python script** instead of standing up a Flink cluster. It implements that SQL so you can read it, change it, and watch each engine fill in a second terminal:

```bash
PYTHONPATH=. python -m transform.shift_left
```

Each scan is priced against the latest surcharge and SLA-flagged, then written to:

- **Cassandra** `globalparcel_ops.parcel_events_by_parcel` — ledger
- **OpenSearch** `parcel-events-live` — customer search
- Kafka `parcel.events.enriched` / `parcel.current` — for lakehouse Tableflow

Cassandra schema is created on first connect.

Details: [`transform/README.md`](transform/README.md).

### 3. Query — warehouse current view

In production this is **Confluent Tableflow**: Kafka topics become Apache Iceberg tables so Presto (and watsonx.data) query the stream as a lakehouse, without a handmade ETL job.

On the laptop you run a **Python script** instead of Tableflow in the cloud. It writes the same tables as Parquet under `data/warehouse/` so the control tower can snapshot a current view:

```bash
PYTHONPATH=. python -m tableflow.materialize
```

The SQL in [`query/current_view.sql`](query/current_view.sql) is what you run in watsonx.data next ([`../02-lakehouse/README.md`](../02-lakehouse/README.md)).

Details: [`tableflow/README.md`](tableflow/README.md), [`query/README.md`](query/README.md).

### 4. Run — control tower

```bash
PYTHONPATH=. uvicorn apps.api:app --host 0.0.0.0 --port 8088
```

Open [http://localhost:8088/tower/](http://localhost:8088/tower/) — the current picture of the business from the warehouse materialization.

Details: [`apps/README.md`](apps/README.md). Next: query this business in watsonx.data ([`../02-lakehouse/README.md`](../02-lakehouse/README.md)). Customer tracking and audit are chapter 03 ([`../03-realtime-operations/README.md`](../03-realtime-operations/README.md)).

---

## Stop

Ctrl+C the Python processes, then from this folder:

```bash
docker compose down
rm -rf data/
```
