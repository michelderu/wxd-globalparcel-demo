"""Capture: put Global Parcel in motion as Kafka streams.

Run from `01-streamhouse/`:

    python -m capture.produce

This is the StreamHouse capture step only. It writes to Apache Kafka
(localhost:9092). It does not write Cassandra, OpenSearch, or Iceberg —
`transform.shift_left` does that next.

Default sequence:
  1. Create topics (compacted: fuel.surcharge, parcel.current).
  2. Publish a full fuel-surcharge snapshot, then tick prices in a background thread.
  3. Stream live scans forever (PCL-LIVE-…) until Ctrl+C.

Topics this process publishes:
  parcel.events    — live hub scans (PCL-LIVE-*)
  fuel.surcharge   — latest price per region (compacted)

Downstream topics are created empty so the transform can write them:
  parcel.events.enriched, parcel.current, ops.sla.alerts
"""

from __future__ import annotations

import argparse
import random
import threading
import time
from datetime import UTC, datetime, timedelta

from shared.config import (
    DEFAULT_SURCHARGE,
    KAFKA_BOOTSTRAP,
    TOPIC_CURRENT,
    TOPIC_ENRICHED,
    TOPIC_EVENTS,
    TOPIC_SURCHARGE,
    TOPIC_ALERTS,
)
from shared.domain import (
    HUBS,
    JourneyCursor,
    LANES,
    build_scan_event,
    is_done,
)
from shared.kafka_io import ensure_topics, producer


def _topics() -> dict[str, dict[str, str]]:
    """Topic names and Kafka configs. Compacted topics keep last value per key."""
    compact = {"cleanup.policy": "compact"}
    return {
        TOPIC_EVENTS: {},
        TOPIC_SURCHARGE: compact,
        TOPIC_ENRICHED: {},
        TOPIC_CURRENT: compact,
        TOPIC_ALERTS: {},
    }


def produce_surcharge_snapshot(prod, surcharge: dict[str, float], updated_at: datetime | None = None) -> None:
    """Publish one surcharge row per region. Key = region so compact keeps latest price."""
    ts = (updated_at or datetime.now(UTC)).isoformat()
    for region, value in surcharge.items():
        prod.send(
            TOPIC_SURCHARGE,
            key=region,
            value={"region": region, "fuel_surcharge": round(value, 2), "updated_at": ts},
        )
    prod.flush()


def stream_live(
    prod,
    *,
    events_per_second: float,
    seed: int,
    max_events: int,
    delay_rate: float,
) -> None:
    """Emit one scan at a time at a steady rate (default ~6/sec).

    Each tick either starts a new PCL-LIVE-* journey or advances an in-flight
    one. Weather delays are injected at delay_rate. Runs until Ctrl+C unless
    --max-events is set.
    """
    rng = random.Random(seed)
    active: list[JourneyCursor] = []
    parcel_seq = 1
    emitted = 0
    interval = 1.0 / events_per_second
    next_tick = time.monotonic()
    print(f"Live capture on {TOPIC_EVENTS} at ~{events_per_second:.1f} scans/sec. Ctrl+C to stop.")
    while True:
        if max_events and emitted >= max_events:
            break
        create_new = (not active) or (rng.random() < 0.35)
        if create_new:
            now = datetime.now(UTC)
            cursor = JourneyCursor(
                parcel_id=f"PCL-LIVE-{parcel_seq:06d}",
                lane=list(rng.choice(LANES)),
                step=0,
                customer_eta=now + timedelta(hours=rng.randint(8, 96)),
            )
            parcel_seq += 1
            active.append(cursor)
        else:
            cursor = rng.choice(active)

        event = build_scan_event(cursor, rng, delay_rate=delay_rate)
        prod.send(TOPIC_EVENTS, key=event["parcel_id"], value=event)
        cursor.step += 1
        if is_done(cursor.lane, cursor.step):
            active.remove(cursor)
        emitted += 1
        if emitted % max(1, int(events_per_second)) == 0:
            print(f"live emitted={emitted} in_flight_journeys={len(active)} last={event['parcel_id']} {event['status']}")
        next_tick += interval
        sleep_for = max(0.0, next_tick - time.monotonic())
        if sleep_for:
            time.sleep(sleep_for)


def stream_surcharge(prod, *, interval_seconds: float, seed: int) -> None:
    """Random-walk one region's fuel surcharge so invoice totals keep moving."""
    rng = random.Random(seed)
    current = dict(DEFAULT_SURCHARGE)
    produce_surcharge_snapshot(prod, current)
    print(f"Fuel surcharge stream on {TOPIC_SURCHARGE} every {interval_seconds:.0f}s. Ctrl+C to stop.")
    while True:
        time.sleep(interval_seconds)
        region = rng.choice(list(HUBS.values())).region
        delta = rng.uniform(-0.35, 0.45)
        current[region] = max(2.5, round(current[region] + delta, 2))
        produce_surcharge_snapshot(prod, {region: current[region]})
        print(f"surcharge tick {region}={current[region]:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events-per-second", type=float, default=6.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-events", type=int, default=0, help="Stop after N live scans; 0 means run forever.")
    parser.add_argument("--delay-rate", type=float, default=0.08)
    parser.add_argument("--surcharge-only", action="store_true")
    parser.add_argument("--surcharge-interval", type=float, default=12.0)
    parser.add_argument("--kafka", default=KAFKA_BOOTSTRAP)
    args = parser.parse_args()

    ensure_topics(_topics(), bootstrap=args.kafka)
    prod = producer(args.kafka)
    try:
        if args.surcharge_only:
            stream_surcharge(prod, interval_seconds=args.surcharge_interval, seed=args.seed)
            return
        # Snapshot first so the transform has prices before the first scan lands.
        produce_surcharge_snapshot(prod, dict(DEFAULT_SURCHARGE))
        ticks = threading.Thread(
            target=stream_surcharge,
            args=(prod,),
            kwargs={"interval_seconds": args.surcharge_interval, "seed": args.seed},
            daemon=True,
        )
        ticks.start()
        stream_live(
            prod,
            events_per_second=args.events_per_second,
            seed=args.seed + 1,
            max_events=args.max_events,
            delay_rate=args.delay_rate,
        )
    except KeyboardInterrupt:
        print("\nCapture stopped.")
    finally:
        prod.flush()
        prod.close()


if __name__ == "__main__":
    main()
