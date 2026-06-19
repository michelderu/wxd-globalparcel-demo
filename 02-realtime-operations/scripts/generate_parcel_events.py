"""Generate realistic parcel events for session 02.

Outputs:
- parcel_events.csv: human-readable sample events
- parcel_events_seed.cql: CQL inserts ready for cqlsh

Run from 02-realtime-operations/:
    python scripts/generate_parcel_events.py --parcels 50
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from delivery_notes import delivery_note


@dataclass(frozen=True)
class Hub:
    code: str
    city: str
    country: str
    region: str
    lat: float
    lon: float


HUBS: dict[str, Hub] = {
    "CDG-01": Hub("CDG-01", "Paris", "FR", "EU-WEST", 49.0097, 2.5479),
    "AMS-01": Hub("AMS-01", "Amsterdam", "NL", "EU-WEST", 52.3105, 4.7683),
    "FRA-01": Hub("FRA-01", "Frankfurt", "DE", "EU-WEST", 50.0379, 8.5622),
    "JFK-01": Hub("JFK-01", "New York", "US", "NA-EAST", 40.6413, -73.7781),
    "ORD-01": Hub("ORD-01", "Chicago", "US", "NA-CENTRAL", 41.9742, -87.9073),
    "GRU-01": Hub("GRU-01", "Sao Paulo", "BR", "SA-EAST", -23.4356, -46.4731),
    "DXB-01": Hub("DXB-01", "Dubai", "AE", "MEA", 25.2532, 55.3657),
    "BOM-01": Hub("BOM-01", "Mumbai", "IN", "APAC-SOUTH", 19.0896, 72.8656),
    "SIN-01": Hub("SIN-01", "Singapore", "SG", "APAC-SE", 1.3644, 103.9915),
    "HKG-01": Hub("HKG-01", "Hong Kong", "CN", "APAC-EAST", 22.3080, 113.9185),
    "NRT-01": Hub("NRT-01", "Tokyo", "JP", "APAC-EAST", 35.7719, 140.3929),
    "SYD-01": Hub("SYD-01", "Sydney", "AU", "APAC-OCEANIA", -33.9399, 151.1753),
}

# Plausible corridor templates for cross-border parcel events.
LANES: list[list[str]] = [
    ["CDG-01", "FRA-01", "JFK-01", "ORD-01"],
    ["AMS-01", "CDG-01", "DXB-01", "BOM-01", "SIN-01"],
    ["FRA-01", "DXB-01", "SIN-01", "SYD-01"],
    ["JFK-01", "ORD-01", "GRU-01"],
    ["NRT-01", "HKG-01", "SIN-01", "BOM-01", "DXB-01", "CDG-01"],
]

STATUSES = [
    "LABEL_CREATED",
    "PICKED_UP",
    "SORTED_AT_HUB",
    "IN_TRANSIT",
    "OUT_FOR_DELIVERY",
    "DELIVERED",
]


def ts_for_cql(dt: datetime) -> str:
    """Format timestamp for CQL literal."""
    return dt.strftime("%Y-%m-%d %H:%M:%S+0000")


def escaped(value: str) -> str:
    return value.replace("'", "''")


def jitter(value: float, spread: float, rng: random.Random) -> float:
    return round(value + rng.uniform(-spread, spread), 6)


def generate_rows(parcels: int, seed: int) -> list[dict[str, object]]:
    rng = random.Random(seed)
    base_time = datetime.now(UTC) - timedelta(hours=18)
    rows: list[dict[str, object]] = []

    for i in range(1, parcels + 1):
        parcel_id = f"PCL-{i:06d}"
        lane = rng.choice(LANES)
        event_time = base_time + timedelta(minutes=rng.randint(0, 180))
        eta = event_time + timedelta(hours=rng.randint(20, 96))

        # 1) Label created near origin hub
        first_hub = HUBS[lane[0]]
        rows.append(
            {
                "parcel_id": parcel_id,
                "event_ts": event_time,
                "status": "LABEL_CREATED",
                "hub_code": first_hub.code,
                "region": first_hub.region,
                "latitude": jitter(first_hub.lat, 0.04, rng),
                "longitude": jitter(first_hub.lon, 0.04, rng),
                "exception_code": "",
                "customer_eta": eta,
                "delivery_note": delivery_note("LABEL_CREATED", first_hub, None, rng),
            }
        )
        event_time += timedelta(minutes=rng.randint(20, 90))

        # 2) Event progression through lane
        for idx, hub_code in enumerate(lane):
            hub = HUBS[hub_code]
            if idx < len(lane) - 1:
                status = rng.choice(["SORTED_AT_HUB", "IN_TRANSIT"])
            else:
                status = "OUT_FOR_DELIVERY"
            ex = "WX_DELAY" if rng.random() < 0.08 else ""
            rows.append(
                {
                    "parcel_id": parcel_id,
                    "event_ts": event_time,
                    "status": status,
                    "hub_code": hub.code,
                    "region": hub.region,
                    "latitude": jitter(hub.lat, 0.12, rng),
                    "longitude": jitter(hub.lon, 0.12, rng),
                    "exception_code": ex,
                    "customer_eta": eta,
                    "delivery_note": delivery_note(status, hub, ex or None, rng),
                }
            )
            event_time += timedelta(hours=rng.randint(2, 10), minutes=rng.randint(5, 55))

        # 3) Final delivery event
        final_hub = HUBS[lane[-1]]
        rows.append(
            {
                "parcel_id": parcel_id,
                "event_ts": event_time,
                "status": "DELIVERED",
                "hub_code": final_hub.code,
                "region": final_hub.region,
                "latitude": jitter(final_hub.lat, 0.18, rng),
                "longitude": jitter(final_hub.lon, 0.18, rng),
                "exception_code": "",
                "customer_eta": eta,
                "delivery_note": delivery_note("DELIVERED", final_hub, None, rng),
            }
        )

    rows.sort(key=lambda r: (str(r["parcel_id"]), r["event_ts"]), reverse=False)
    return rows


def write_csv(rows: list[dict[str, object]], out_path: Path) -> None:
    fieldnames = [
        "parcel_id",
        "event_ts",
        "status",
        "hub_code",
        "region",
        "latitude",
        "longitude",
        "exception_code",
        "customer_eta",
        "delivery_note",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            csv_row["event_ts"] = row["event_ts"].isoformat()
            csv_row["customer_eta"] = row["customer_eta"].isoformat()
            writer.writerow(csv_row)


def write_cql(rows: list[dict[str, object]], out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8") as f:
        f.write("USE globalparcel_ops;\n\n")
        for row in rows:
            ex = row["exception_code"] or None
            ex_literal = f"'{escaped(ex)}'" if ex else "null"
            note = escaped(str(row["delivery_note"]))
            f.write(
                "INSERT INTO parcel_events_by_parcel "
                "(parcel_id, event_ts, status, hub_code, region, latitude, longitude, exception_code, customer_eta, delivery_note) "
                f"VALUES ('{escaped(str(row['parcel_id']))}', "
                f"'{ts_for_cql(row['event_ts'])}', "
                f"'{escaped(str(row['status']))}', "
                f"'{escaped(str(row['hub_code']))}', "
                f"'{escaped(str(row['region']))}', "
                f"{row['latitude']}, {row['longitude']}, "
                f"{ex_literal}, "
                f"'{ts_for_cql(row['customer_eta'])}', "
                f"'{note}');\n"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parcels", type=int, default=40, help="Number of parcels to generate.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible output.")
    parser.add_argument(
        "--output-dir",
        default="generated",
        help="Output directory for CSV and CQL files (default: generated).",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = generate_rows(args.parcels, args.seed)
    csv_path = output_dir / "parcel_events.csv"
    cql_path = output_dir / "parcel_events_seed.cql"
    write_csv(rows, csv_path)
    write_cql(rows, cql_path)

    print(f"Generated {args.parcels} parcel events")
    print(f"CSV: {csv_path}")
    print(f"CQL: {cql_path}")


if __name__ == "__main__":
    main()
