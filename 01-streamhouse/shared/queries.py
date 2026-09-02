"""Query the current view of Global Parcel from warehouse Parquet via PyArrow."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from shared.config import TABLE_CURRENT, TABLE_EVENTS, TABLE_SURCHARGE
from shared.iceberg_io import scan_arrow


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def business_snapshot() -> dict[str, Any]:
    current = scan_arrow(TABLE_CURRENT)
    events = scan_arrow(TABLE_EVENTS)
    surcharge = scan_arrow(TABLE_SURCHARGE)

    if current.num_rows == 0:
        return {
            "kpis": {
                "parcels": 0,
                "in_flight": 0,
                "delivered": 0,
                "sla_at_risk": 0,
                "weather_delays": 0,
                "live_cost_exposure": 0.0,
            },
            "by_status": [],
            "by_hub": [],
            "surcharge": [],
            "recent": [],
        }

    status = current.column("status").to_pylist()
    sla_risk = current.column("sla_risk").to_pylist()
    exception = current.column("exception_code").to_pylist()
    invoice = current.column("invoice_total").to_pylist()
    hub_code = current.column("hub_code").to_pylist()
    hub_city = current.column("hub_city").to_pylist()

    parcels = current.num_rows
    in_flight = sum(1 for s in status if s != "DELIVERED")
    delivered = sum(1 for s in status if s == "DELIVERED")
    at_risk = sum(1 for flag in sla_risk if flag)
    weather = sum(1 for code in exception if code == "WX_DELAY")
    exposure = sum(float(value or 0) for s, value in zip(status, invoice) if s != "DELIVERED")

    status_counts: dict[str, int] = defaultdict(int)
    for s in status:
        status_counts[s or "UNKNOWN"] += 1

    hubs: dict[str, dict[str, Any]] = {}
    for code, city, s, risk, exc, value in zip(hub_code, hub_city, status, sla_risk, exception, invoice):
        row = hubs.setdefault(
            code or "-",
            {
                "hub_code": code or "-",
                "hub_city": city or "",
                "in_flight": 0,
                "sla_at_risk": 0,
                "weather_delays": 0,
                "exposure": 0.0,
            },
        )
        if s != "DELIVERED":
            row["in_flight"] += 1
            row["exposure"] += float(value or 0)
        if risk:
            row["sla_at_risk"] += 1
        if exc == "WX_DELAY":
            row["weather_delays"] += 1

    by_hub = [
        {**row, "exposure": round(row["exposure"], 2)}
        for row in hubs.values()
        if row["in_flight"] > 0 or row["sla_at_risk"] > 0
    ]
    by_hub.sort(key=lambda row: (row["sla_at_risk"], row["in_flight"]), reverse=True)

    surcharge_rows = []
    if surcharge.num_rows:
        for region, value, ts in zip(
            surcharge.column("region").to_pylist(),
            surcharge.column("fuel_surcharge").to_pylist(),
            surcharge.column("updated_at").to_pylist(),
        ):
            surcharge_rows.append(
                {
                    "region": region,
                    "fuel_surcharge": round(float(value or 0), 2),
                    "updated_at": _iso(ts),
                }
            )
        surcharge_rows.sort(key=lambda row: row["region"] or "")

    recent = []
    if events.num_rows:
        order = events.sort_by([("event_ts", "descending")])
        take = min(12, order.num_rows)
        sliced = order.slice(0, take)
        for pid, ts, st, hub, risk, reason, note in zip(
            sliced.column("parcel_id").to_pylist(),
            sliced.column("event_ts").to_pylist(),
            sliced.column("status").to_pylist(),
            sliced.column("hub_code").to_pylist(),
            sliced.column("sla_risk").to_pylist(),
            sliced.column("sla_reason").to_pylist(),
            sliced.column("delivery_note").to_pylist(),
        ):
            recent.append(
                {
                    "parcel_id": pid,
                    "event_ts": _iso(ts),
                    "status": st,
                    "hub_code": hub,
                    "sla_risk": bool(risk),
                    "sla_reason": reason or "",
                    "delivery_note": note or "",
                }
            )

    return {
        "kpis": {
            "parcels": parcels,
            "in_flight": in_flight,
            "delivered": delivered,
            "sla_at_risk": at_risk,
            "weather_delays": weather,
            "live_cost_exposure": round(float(exposure), 2),
        },
        "by_status": [
            {"status": name, "parcels": count}
            for name, count in sorted(status_counts.items(), key=lambda item: item[1], reverse=True)
        ],
        "by_hub": by_hub,
        "surcharge": surcharge_rows,
        "recent": recent,
    }
