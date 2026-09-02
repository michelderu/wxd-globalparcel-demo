"""Export StreamHouse warehouse parcel events as CSV for watsonx.data Spark ingest.

Primary path: read Tableflow Parquet from data/warehouse/.
Fallback: synthesize the same schema from shared.domain hubs when the warehouse
is empty (session 01 capture has not run yet).

Run from `02-lakehouse/` (chapter 01 warehouse under `01-streamhouse/data/`):

    PYTHONPATH=../01-streamhouse python scripts/export_streamhouse_history.py
"""

from __future__ import annotations

import csv
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKSHOP_ROOT = Path(__file__).resolve().parents[2]
STREAMHOUSE_DIR = WORKSHOP_ROOT / "01-streamhouse"
sys.path.insert(0, str(STREAMHOUSE_DIR))

from shared.config import BASE_RATE_BY_REGION, DEFAULT_SURCHARGE, TABLE_EVENTS  # noqa: E402
from shared.domain import HUBS, LANES, STATUSES  # noqa: E402
from shared.iceberg_io import scan_arrow  # noqa: E402

SESSION_DIR = Path(__file__).resolve().parents[1]
OUTPUT_CSV = SESSION_DIR / "shipping_history.csv"

FIELDNAMES = [
    "parcel_id",
    "origin_hub",
    "origin_city",
    "destination_hub",
    "region",
    "status",
    "hub_code",
    "hub_city",
    "exception_code",
    "base_rate",
    "fuel_surcharge",
    "invoice_total",
    "sla_risk",
]


def _row_from_event(record: dict) -> dict[str, object]:
    origin = record.get("origin_hub") or ""
    hub = HUBS.get(origin)
    return {
        "parcel_id": record.get("parcel_id") or "",
        "origin_hub": origin,
        "origin_city": hub.city if hub else (record.get("hub_city") or ""),
        "destination_hub": record.get("destination_hub") or "",
        "region": record.get("region") or "",
        "status": record.get("status") or "",
        "hub_code": record.get("hub_code") or "",
        "hub_city": record.get("hub_city") or "",
        "exception_code": record.get("exception_code") or "",
        "base_rate": round(float(record.get("base_rate") or 0), 2),
        "fuel_surcharge": round(float(record.get("fuel_surcharge") or 0), 2),
        "invoice_total": round(float(record.get("invoice_total") or 0), 2),
        "sla_risk": bool(record.get("sla_risk")),
    }


def rows_from_warehouse() -> list[dict[str, object]]:
    table = scan_arrow(TABLE_EVENTS)
    if table.num_rows == 0:
        return []
    columns = {name: table.column(name).to_pylist() for name in table.column_names}
    records = []
    for i in range(table.num_rows):
        records.append(_row_from_event({name: values[i] for name, values in columns.items()}))
    return records


def rows_from_domain(count: int = 400) -> list[dict[str, object]]:
    rng = random.Random(42)
    rows: list[dict[str, object]] = []
    for i in range(1, count + 1):
        lane = LANES[i % len(LANES)]
        origin = HUBS[lane[0]]
        dest = HUBS[lane[-1]]
        current = HUBS[rng.choice(lane)]
        status = rng.choice(STATUSES)
        exception = "WX_DELAY" if rng.random() < 0.08 else ""
        region = origin.region
        base = BASE_RATE_BY_REGION.get(region, 18.0)
        surcharge = DEFAULT_SURCHARGE.get(region, 6.0)
        rows.append(
            {
                "parcel_id": f"PCL-{i:06d}",
                "origin_hub": origin.code,
                "origin_city": origin.city,
                "destination_hub": dest.code,
                "region": region,
                "status": status,
                "hub_code": current.code,
                "hub_city": current.city,
                "exception_code": exception,
                "base_rate": round(base, 2),
                "fuel_surcharge": round(surcharge, 2),
                "invoice_total": round(base + surcharge, 2),
                "sla_risk": bool(exception) or status in {"IN_TRANSIT", "OUT_FOR_DELIVERY"} and rng.random() < 0.2,
            }
        )
    return rows


def write_csv(rows: list[dict[str, object]], path: Path = OUTPUT_CSV) -> Path:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    rows = rows_from_warehouse()
    source = "warehouse"
    if not rows:
        rows = rows_from_domain()
        source = "fallback (session 01 warehouse empty)"
        print(
            "No Tableflow files under data/warehouse/; writing a StreamHouse-shaped "
            "fallback CSV. Run session 01 capture + tableflow for live parcels.",
            flush=True,
        )
    path = write_csv(rows)
    print(f"Wrote {len(rows)} rows from {source} to {path} at {datetime.now(UTC).isoformat()}", flush=True)


if __name__ == "__main__":
    main()
