"""Global Parcel domain: hubs, lanes, driver notes, event shaping.

Reused from the hybrid lakehouse edition and extended for StreamHouse:
every event carries enough context to become a business-ready row after
the shift-left transform (surcharge, SLA risk, invoice total).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from shared.config import BASE_RATE_BY_REGION, DEFAULT_SURCHARGE


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

# Ordered hub hops. Capture walks each list: label/pickup at [0], delivery at [-1].
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


@dataclass
class JourneyCursor:
    """Where a parcel sits on its lane: next scan is step_to_event(lane, step)."""

    parcel_id: str
    lane: list[str]
    step: int
    customer_eta: datetime
    origin_hub: str = field(init=False)
    destination_hub: str = field(init=False)

    def __post_init__(self) -> None:
        self.origin_hub = self.lane[0]
        self.destination_hub = self.lane[-1]


def jitter(value: float, spread: float, rng: random.Random) -> float:
    return round(value + rng.uniform(-spread, spread), 6)


def delivery_note(
    status: str,
    hub: Hub,
    exception_code: str | None,
    rng: random.Random,
    *,
    driver_names: tuple[str, ...] = ("Marco", "Aisha", "Chen", "Sofia", "James"),
) -> str:
    driver = rng.choice(driver_names)
    cage = rng.randint(100, 999)
    if exception_code == "WX_DELAY":
        return (
            f"{hub.code}: weather delay — ramp closed for de-icing; "
            "linehaul held; customer ETA may slip."
        )
    notes: dict[str, list[str]] = {
        "LABEL_CREATED": [
            f"Label created at {hub.city}; manifest queued for first pickup.",
            f"Electronic label OK; awaiting pickup scan at {hub.code}.",
        ],
        "PICKED_UP": [
            f"Picked up from sender near {hub.city}; seal intact; cage GP-{cage}.",
            f"Collection scan by {driver}; parcel ID verified at origin.",
        ],
        "SORTED_AT_HUB": [
            f"Sorted into outbound lane at {hub.code}; cage GP-{cage}.",
            f"Hub scan {hub.city}: routed to correct departure belt.",
        ],
        "IN_TRANSIT": [
            f"Departed {hub.code} on linehaul; next hub in lane.",
            f"In transit from {hub.city}; GPS ping nominal.",
        ],
        "OUT_FOR_DELIVERY": [
            f"Loaded on van route 7; driver {driver}; ~{rng.randint(8, 18)} stops before this drop.",
            f"Out for delivery from {hub.code}; recipient phone on file.",
        ],
        "DELIVERED": [
            f"Delivered at {hub.city}; signed by recipient.",
            f"Left with concierge per building instructions; photo captured.",
            f"Delivered — handoff to front desk, signature on file.",
        ],
    }
    options = notes.get(status, [f"Scan recorded at {hub.code} ({status})."])
    return rng.choice(options)


def step_to_event(lane: list[str], step: int, rng: random.Random) -> tuple[str, str]:
    """Map journey step → (hub, status). Label/pickup at origin, delivery at destination."""
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
    max_step = 2 + (len(lane) - 1) + 2 - 1
    return step > max_step


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_scan_event(
    cursor: JourneyCursor,
    rng: random.Random,
    *,
    event_ts: datetime | None = None,
    delay_rate: float = 0.08,
) -> dict[str, Any]:
    """One hub scan as it would come off a scanner — no price or SLA yet.

    Weather delays (WX_DELAY) are injected at delay_rate on transit/sort scans.
    GPS is jittered around the hub so the map looks alive, not stacked.
    """
    hub_code, status = step_to_event(cursor.lane, cursor.step, rng)
    hub = HUBS[hub_code]
    spread = 0.03 if status in {"LABEL_CREATED", "PICKED_UP"} else 0.12
    exception_code = None
    if status in {"IN_TRANSIT", "SORTED_AT_HUB"} and rng.random() < delay_rate:
        exception_code = "WX_DELAY"
    ts = event_ts or datetime.now(UTC)
    return {
        "parcel_id": cursor.parcel_id,
        "event_ts": iso(ts),
        "status": status,
        "hub_code": hub.code,
        "hub_city": hub.city,
        "hub_country": hub.country,
        "region": hub.region,
        "latitude": jitter(hub.lat, spread, rng),
        "longitude": jitter(hub.lon, spread, rng),
        "exception_code": exception_code or "",
        "customer_eta": iso(cursor.customer_eta),
        "delivery_note": delivery_note(status, hub, exception_code, rng),
        "origin_hub": cursor.origin_hub,
        "destination_hub": cursor.destination_hub,
    }


def enrich_event(event: dict[str, Any], surcharge_by_region: dict[str, float]) -> dict[str, Any]:
    """Join the live surcharge, price the scan, and flag SLA risk.

    Called by the transform for every parcel.events record. Apps and SQL then
    read invoice_total / sla_risk instead of recomputing them.
    """
    region = event["region"]
    base_rate = BASE_RATE_BY_REGION.get(region, 20.0)
    fuel = float(surcharge_by_region.get(region, DEFAULT_SURCHARGE.get(region, 5.0)))
    status = event["status"]
    exception_code = event.get("exception_code") or ""
    eta = parse_iso(event.get("customer_eta"))
    event_ts = parse_iso(event.get("event_ts")) or datetime.now(UTC)

    sla_risk = False
    sla_reason = ""
    if exception_code == "WX_DELAY":
        sla_risk = True
        sla_reason = "Weather delay at hub — ETA at risk"
    elif status != "DELIVERED" and eta is not None and event_ts > eta:
        sla_risk = True
        sla_reason = "Past customer ETA without delivery scan"

    enriched = dict(event)
    enriched["base_rate"] = round(base_rate, 2)
    enriched["fuel_surcharge"] = round(fuel, 2)
    enriched["invoice_total"] = round(base_rate + fuel, 2)
    enriched["sla_risk"] = sla_risk
    enriched["sla_reason"] = sla_reason
    return enriched
