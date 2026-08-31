# 1 — Capture

Put Global Parcel in motion. If it happened in the business, it is a stream.

## Why this is not "ingest to the lake"

The previous edition generated a CSV of shipping history and loaded it once. Finance then kept fuel surcharge in PostgreSQL until you federated it.

Here both facts are captured as Kafka topics from the first second:

| Topic | Key | What it is |
| --- | --- | --- |
| `parcel.events` | `parcel_id` | Hub scans, including a historical replay |
| `fuel.surcharge` | `region` | Compacted live price ticks |

Open [Kafka UI](http://localhost:8080) or consume like `cqlsh`:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic parcel.events --from-beginning
```

You are watching the business, not a batch window.

```bash
docker compose up -d
PYTHONPATH=. python -m capture.produce
```

`--bootstrap-parcels 80` replays completed journeys as `PCL-000001` … so later queries combine **history and live**. Then `PCL-LIVE-*` scans continue forever.

Surcharge ticks run on a background thread so invoice totals in the transform are never stale list prices.
