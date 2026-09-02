# Capture

Run these commands from **`01-streamhouse/`** (this file lives in `capture/`).

Put Global Parcel in motion. If it happened in the business, it is a stream.

## Why this is not "ingest to the lake"

The previous edition generated a CSV of shipping history and loaded it once. Finance then kept fuel surcharge in PostgreSQL until you federated it. This edition publishes surcharge ticks on Kafka (`fuel.surcharge`); watsonx.data federates that topic in the query chapter.

Here both facts are captured as Kafka topics from the first second:

| Topic | Key | What it is |
| --- | --- | --- |
| `parcel.events` | `parcel_id` | Hub scans, including a historical replay |
| `fuel.surcharge` | `region` | Compacted live price ticks |

```bash
PYTHONPATH=. python -m capture.produce
```

Open [Kafka UI](http://localhost:8080) or consume like `cqlsh` (after produce is running — that is when topics exist):

```bash
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:29092 --list
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:29092 --topic parcel.events --from-beginning
```

You are watching the business, not a batch window.

`--bootstrap-parcels 80` replays completed journeys as `PCL-000001` … so later queries combine **history and live**. Then `PCL-LIVE-*` scans continue forever.

Surcharge ticks run on a background thread so invoice totals in the transform are never stale list prices.
