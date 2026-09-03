# Capture

Run these commands from **`01-streamhouse/`** (this file lives in `capture/`).

Put Global Parcel in motion. If it happened in the business, it is a stream.

## Why this is not "ingest to the lake"

This process publishes surcharge ticks on Kafka (`fuel.surcharge`); watsonx.data federates that topic in the query chapter.

Here both facts are captured as Kafka topics from the first second:

| Topic | Key | What it is |
| --- | --- | --- |
| `parcel.events` | `parcel_id` | Hub scans, including a historical replay |
| `fuel.surcharge` | `region` | Compacted live price ticks |

Kafka topics in this capture step represent two fundamental real-time business signals:

- **`parcel.events`**: These are *parcel scan events*. Each message's key is a `parcel_id`, which uniquely identifies a shipment or package. The value is a scan event at a hub—who, when, and where the parcel was seen or processed. When you start the producer, it first **replays historical journeys** (`PCL-000001`, etc.) to create a realistic event stream with a back-catalog of completed deliveries. Then, it begins streaming new, live scans (`PCL-LIVE-*`) as they would happen in real life. This gives downstream systems (transform, ledger, search, lakehouse) a unified feed that supports historical, current, and future state queries.

- **`fuel.surcharge`**: These messages keep the **current fuel surcharge** for each region up to date. The key on each message is `region` (e.g., a country or zone name), while the value is the latest surcharge value. This topic is **compacted**, so at any time, querying or joining will give the latest price per region. Surcharge ticks are generated continuously in the background, ensuring that any cost calculation in the transform can use a current (not stale) price.

You can inspect these topics in real-time through CLI commands or the Kafka UI. Messages are produced indefinitely to mirror the ongoing flow of business operations—the real-time parcel logistics and the fluctuating cost environment they operate in.


```bash
PYTHONPATH=. python -m capture.produce
```

Open [Kafka UI](http://localhost:8085) or consume like `cqlsh` (after produce is running — that is when topics exist):

```bash
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:29092 --list
docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:29092 --topic parcel.events --from-beginning
```

You are watching the business, not a batch window.

`--bootstrap-parcels 80` replays completed journeys as `PCL-000001` … so later queries combine **history and live**. Then `PCL-LIVE-*` scans continue forever.

Surcharge ticks run on a background thread so invoice totals in the transform are never stale list prices.
