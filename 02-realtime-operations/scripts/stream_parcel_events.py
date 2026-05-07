"""Stream synthetic parcel lifecycle events into Cassandra (and optionally OpenSearch).

This utility produces realistic multi-step parcel journeys and writes each event to
`globalparcel_ops.parcel_events_by_parcel`. It is designed for workshop demos where
the data model must look plausible while continuously updating.

The same events can be indexed into OpenSearch to power low-latency customer-facing
tracking queries. In that mode, Cassandra remains the authoritative write path while
OpenSearch acts as the query-optimized read layer.

Examples:
    python scripts/stream_parcel_events.py --events-per-second 10
    python scripts/stream_parcel_events.py --events-per-second 10 --index-opensearch
"""

from __future__ import annotations

import argparse
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cassandra.cluster import Cluster
from opensearchpy import OpenSearch

from generate_parcel_events import HUBS, LANES, Hub


@dataclass
class JourneyCursor:
    """Tracks one in-flight parcel and its position in a lane-based journey."""

    parcel_id: str
    lane: list[str]
    step: int
    customer_eta: datetime


def jitter(value: float, spread: float, rng: random.Random) -> float:
    """Add bounded random noise to latitude/longitude for less repetitive routes."""

    return round(value + rng.uniform(-spread, spread), 6)


def step_to_event(lane: list[str], step: int, rng: random.Random) -> tuple[str, str]:
    """Map a journey step to `(hub_code, status)` for the next emitted event.

    Journey model:
    - step 0: label created at origin
    - step 1: picked up at origin
    - middle steps: sorted/in transit through intermediate hubs
    - final steps: out for delivery, then delivered at destination
    """

    # Sequence: label -> pickup -> transit/sort through lane -> out_for_delivery -> delivered
    if step == 0:
        return lane[0], "LABEL_CREATED"
    if step == 1:
        return lane[0], "PICKED_UP"

    transit_start = 2
    transit_end = transit_start + len(lane) - 1
    if transit_start <= step < transit_end:
        hub_code = lane[step - transit_start]
        return hub_code, rng.choice(["SORTED_AT_HUB", "IN_TRANSIT"])
    if step == transit_end:
        return lane[-1], "OUT_FOR_DELIVERY"
    return lane[-1], "DELIVERED"


def is_done(lane: list[str], step: int) -> bool:
    """Return True when a parcel has emitted all lifecycle events for its lane."""

    # 2 fixed steps + (len(lane) - 1) transit steps + out_for_delivery + delivered
    max_step = 2 + (len(lane) - 1) + 2 - 1
    return step > max_step


def ensure_opensearch_index(client: OpenSearch, index_name: str) -> None:
    """Create the OpenSearch index with expected mapping when missing."""

    if client.indices.exists(index=index_name):
        return
    body = {
        "settings": {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
            }
        },
        "mappings": {
            "properties": {
                "parcel_id": {"type": "keyword"},
                "event_ts": {"type": "date"},
                "status": {"type": "keyword"},
                "hub_code": {"type": "keyword"},
                "region": {"type": "keyword"},
                "exception_code": {"type": "keyword"},
                "customer_eta": {"type": "date"},
                "geo_position": {"type": "geo_point"},
            }
        },
    }
    client.indices.create(index=index_name, body=body)


def main() -> None:
    """Run the continuous event production loop.

    The loop emits approximately `events_per_second` events by sleeping between ticks.
    On each tick, it either starts a new parcel journey or advances an existing one.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Cassandra host (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=9042, help="Cassandra CQL port (default: 9042).")
    parser.add_argument("--keyspace", default="globalparcel_ops", help="Keyspace to write into.")
    parser.add_argument(
        "--events-per-second",
        type=float,
        default=10.0,
        help="Target write rate per second (default: 10).",
    )
    parser.add_argument(
        "--new-parcel-probability",
        type=float,
        default=0.35,
        help="Probability of starting a new parcel on each tick (default: 0.35).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility.")
    parser.add_argument(
        "--max-events",
        type=int,
        default=0,
        help="Optional cap for generated events; 0 means run forever.",
    )
    parser.add_argument(
        "--index-opensearch",
        action="store_true",
        help="Also index produced events into OpenSearch.",
    )
    parser.add_argument(
        "--opensearch-url",
        default="http://localhost:9200",
        help="OpenSearch URL (default: http://localhost:9200).",
    )
    parser.add_argument(
        "--opensearch-index",
        default="parcel-events-live",
        help="OpenSearch index name (default: parcel-events-live).",
    )
    args = parser.parse_args()

    if args.events_per_second <= 0:
        raise ValueError("--events-per-second must be > 0")

    rng = random.Random(args.seed)
    cluster = Cluster([args.host], port=args.port)
    session = cluster.connect(args.keyspace)
    prepared = session.prepare(
        """
        INSERT INTO parcel_events_by_parcel (
          parcel_id, event_ts, status, hub_code, region, latitude, longitude, exception_code, customer_eta
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )

    active: list[JourneyCursor] = []
    parcel_seq = 1
    emitted = 0
    interval = 1.0 / args.events_per_second
    next_tick = time.monotonic()
    os_client: OpenSearch | None = None

    if args.index_opensearch:
        os_client = OpenSearch(hosts=[args.opensearch_url])
        ensure_opensearch_index(os_client, args.opensearch_index)

    # Main streaming loop: produces parcel events at approximately the requested rate.
    # Each loop iteration emits either a new parcel journey or an update to an in-flight parcel.
    print(f"Streaming events to Cassandra at ~{args.events_per_second:.2f}/sec. Press Ctrl+C to stop.")
    try:
        while True:
            # Stop the loop if we've reached the maximum allowed events (if specified)
            if args.max_events and emitted >= args.max_events:
                break

            # Decide whether to create a new parcel or advance an existing one
            # - Always start a new one if there are no active journeys.
            # - Else, use the probability threshold for starting new journeys.
            create_new = (not active) or (rng.random() < args.new_parcel_probability)
            if create_new:
                # Randomly pick a new route ("lane"), create a JourneyCursor for the new parcel.
                lane = list(rng.choice(LANES))
                now = datetime.now(UTC)
                cursor = JourneyCursor(
                    parcel_id=f"PCL-LIVE-{parcel_seq:06d}",
                    lane=lane,
                    step=0,  # first event is label creation
                    customer_eta=now + timedelta(hours=rng.randint(8, 96)),  # plausible delivery window
                )
                parcel_seq += 1
                active.append(cursor)
            else:
                # Choose any parcel with unfinished journey to emit its next event
                cursor = rng.choice(active)

            # Determine the next hub and event status for this step
            hub_code, status = step_to_event(cursor.lane, cursor.step, rng)
            hub: Hub = HUBS[hub_code]

            # Apply location jitter; more jitter for in-transit vs. stationary events
            spread = 0.03 if status in {"LABEL_CREATED", "PICKED_UP"} else 0.12

            # Randomly inject occasional "weather delay" for realism
            exception_code = None
            if status in {"IN_TRANSIT", "SORTED_AT_HUB"} and rng.random() < 0.06:
                exception_code = "WX_DELAY"

            event_ts = datetime.now(UTC)
            lat = jitter(hub.lat, spread, rng)
            lon = jitter(hub.lon, spread, rng)

            # Write the event to Cassandra (source of truth)
            session.execute(
                prepared,
                (
                    cursor.parcel_id,
                    event_ts,
                    status,
                    hub.code,
                    hub.region,
                    lat,
                    lon,
                    exception_code,
                    cursor.customer_eta,
                ),
            )

            # Optionally index into OpenSearch—a query-optimized read path
            if os_client is not None:
                doc = {
                    "parcel_id": cursor.parcel_id,
                    "event_ts": event_ts.isoformat(),
                    "status": status,
                    "hub_code": hub.code,
                    "region": hub.region,
                    "exception_code": exception_code or "",
                    "customer_eta": cursor.customer_eta.isoformat(),
                    "geo_position": {"lat": lat, "lon": lon},
                }
                doc_id = f"{cursor.parcel_id}:{event_ts.isoformat()}"
                os_client.index(index=args.opensearch_index, id=doc_id, body=doc, refresh=False)

            # Advance the journey step.
            cursor.step += 1

            # If the parcel journey is done, remove this cursor from the active set.
            if is_done(cursor.lane, cursor.step):
                active.remove(cursor)

            emitted += 1
            # Print a progress update roughly once per (simulated) second.
            if emitted % int(max(1, round(args.events_per_second))) == 0:
                print(f"emitted={emitted} active_parcels={len(active)}")

            # Rate limiting: wait so that event emission rate matches events_per_second
            next_tick += interval
            sleep_for = max(0.0, next_tick - time.monotonic())
            if sleep_for:
                time.sleep(sleep_for)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        print(f"Total emitted events: {emitted}")
        cluster.shutdown()


if __name__ == "__main__":
    main()
