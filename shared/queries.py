"""Query the current view of Global Parcel from Iceberg via DuckDB."""

from __future__ import annotations

from typing import Any

import duckdb
import pyarrow as pa

from shared.config import TABLE_ALERTS, TABLE_CURRENT, TABLE_EVENTS, TABLE_SURCHARGE
from shared.iceberg_io import empty_events_arrow, scan_arrow


def _register(con: duckdb.DuckDBPyConnection, name: str, table_ident: str) -> bool:
    arrow = scan_arrow(table_ident)
    if arrow.num_rows == 0:
        return False
    con.register(name, arrow)
    return True


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    loaded = {
        "parcel_current": _register(con, "parcel_current", TABLE_CURRENT),
        "parcel_events": _register(con, "parcel_events", TABLE_EVENTS),
        "fuel_surcharge": _register(con, "fuel_surcharge", TABLE_SURCHARGE),
        "sla_alerts": _register(con, "sla_alerts", TABLE_ALERTS),
    }
    empty = empty_events_arrow()
    if not loaded["parcel_current"]:
        con.register("parcel_current", empty)
    if not loaded["parcel_events"]:
        con.register("parcel_events", empty)
    if not loaded["fuel_surcharge"]:
        con.register(
            "fuel_surcharge",
            pa.table(
                {
                    "region": pa.array([], type=pa.string()),
                    "fuel_surcharge": pa.array([], type=pa.float64()),
                    "updated_at": pa.array([], type=pa.timestamp("us", tz="UTC")),
                }
            ),
        )
    if not loaded["sla_alerts"]:
        con.register("sla_alerts", empty)
    return con


def business_snapshot() -> dict[str, Any]:
    con = _connect()
    kpis = con.execute(
        """
        SELECT
          COUNT(*) AS parcels,
          COUNT(*) FILTER (WHERE status != 'DELIVERED') AS in_flight,
          COUNT(*) FILTER (WHERE status = 'DELIVERED') AS delivered,
          COUNT(*) FILTER (WHERE sla_risk) AS sla_at_risk,
          COUNT(*) FILTER (WHERE exception_code = 'WX_DELAY') AS weather_delays,
          COALESCE(SUM(invoice_total) FILTER (WHERE status != 'DELIVERED'), 0) AS live_cost_exposure
        FROM parcel_current
        """
    ).fetchone()
    by_status = con.execute(
        """
        SELECT status, COUNT(*) AS parcels
        FROM parcel_current
        GROUP BY status
        ORDER BY parcels DESC
        """
    ).fetchall()
    by_hub = con.execute(
        """
        SELECT
          hub_code,
          ANY_VALUE(hub_city) AS hub_city,
          COUNT(*) FILTER (WHERE status != 'DELIVERED') AS in_flight,
          COUNT(*) FILTER (WHERE sla_risk) AS sla_at_risk,
          COUNT(*) FILTER (WHERE exception_code = 'WX_DELAY') AS weather_delays,
          COALESCE(SUM(invoice_total) FILTER (WHERE status != 'DELIVERED'), 0) AS exposure
        FROM parcel_current
        GROUP BY hub_code
        HAVING in_flight > 0 OR sla_at_risk > 0
        ORDER BY sla_at_risk DESC, in_flight DESC
        """
    ).fetchall()
    surcharge = []
    try:
        surcharge = con.execute(
            "SELECT region, fuel_surcharge, updated_at FROM fuel_surcharge ORDER BY region"
        ).fetchall()
    except Exception:
        pass
    recent = []
    try:
        recent = con.execute(
            """
            SELECT parcel_id, event_ts, status, hub_code, sla_risk, sla_reason, delivery_note
            FROM parcel_events
            ORDER BY event_ts DESC
            LIMIT 12
            """
        ).fetchall()
    except Exception:
        pass

    parcels, in_flight, delivered, sla_at_risk, weather_delays, exposure = kpis
    return {
        "kpis": {
            "parcels": int(parcels or 0),
            "in_flight": int(in_flight or 0),
            "delivered": int(delivered or 0),
            "sla_at_risk": int(sla_at_risk or 0),
            "weather_delays": int(weather_delays or 0),
            "live_cost_exposure": round(float(exposure or 0), 2),
        },
        "by_status": [{"status": s, "parcels": int(n)} for s, n in by_status],
        "by_hub": [
            {
                "hub_code": hub,
                "hub_city": city,
                "in_flight": int(inflight),
                "sla_at_risk": int(risk),
                "weather_delays": int(wx),
                "exposure": round(float(exp or 0), 2),
            }
            for hub, city, inflight, risk, wx, exp in by_hub
        ],
        "surcharge": [
            {
                "region": region,
                "fuel_surcharge": round(float(value), 2),
                "updated_at": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            }
            for region, value, ts in surcharge
        ],
        "recent": [
            {
                "parcel_id": pid,
                "event_ts": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "status": status,
                "hub_code": hub,
                "sla_risk": bool(risk),
                "sla_reason": reason or "",
                "delivery_note": note or "",
            }
            for pid, ts, status, hub, risk, reason, note in recent
        ],
    }


def parcel_timeline(parcel_id: str) -> dict[str, Any] | None:
    con = _connect()
    current = con.execute(
        """
        SELECT parcel_id, status, hub_code, hub_city, region, customer_eta, event_ts,
               sla_risk, sla_reason, invoice_total, fuel_surcharge, delivery_note,
               origin_hub, destination_hub, latitude, longitude
        FROM parcel_current
        WHERE parcel_id = ?
        """,
        [parcel_id],
    ).fetchone()
    events = con.execute(
        """
        SELECT event_ts, status, hub_code, hub_city, region, exception_code,
               customer_eta, delivery_note, sla_risk, sla_reason, invoice_total,
               latitude, longitude
        FROM parcel_events
        WHERE parcel_id = ?
        ORDER BY event_ts DESC
        """,
        [parcel_id],
    ).fetchall()
    if not current and not events:
        return None

    def event_row(row: tuple[Any, ...]) -> dict[str, Any]:
        (
            event_ts,
            status,
            hub_code,
            hub_city,
            region,
            exception_code,
            customer_eta,
            delivery_note,
            sla_risk,
            sla_reason,
            invoice_total,
            latitude,
            longitude,
        ) = row
        return {
            "event_ts": event_ts.isoformat() if hasattr(event_ts, "isoformat") else event_ts,
            "status": status,
            "hub_code": hub_code,
            "hub_city": hub_city,
            "region": region,
            "exception_code": exception_code or "",
            "customer_eta": customer_eta.isoformat() if hasattr(customer_eta, "isoformat") else customer_eta,
            "delivery_note": delivery_note or "",
            "sla_risk": bool(sla_risk),
            "sla_reason": sla_reason or "",
            "invoice_total": round(float(invoice_total or 0), 2),
            "geo_position": {"latitude": latitude, "longitude": longitude},
        }

    timeline = [event_row(r) for r in events]
    latest = timeline[0] if timeline else {}
    if current:
        latest_status = current[1]
        latest_hub = current[2]
        latest_event_ts = current[6].isoformat() if hasattr(current[6], "isoformat") else current[6]
        customer_eta = current[5].isoformat() if hasattr(current[5], "isoformat") else current[5]
    else:
        latest_status = latest.get("status", "UNKNOWN")
        latest_hub = latest.get("hub_code", "-")
        latest_event_ts = latest.get("event_ts")
        customer_eta = latest.get("customer_eta")

    return {
        "parcel_id": parcel_id,
        "latest_status": latest_status,
        "latest_hub": latest_hub,
        "customer_eta": customer_eta,
        "latest_event_ts": latest_event_ts,
        "sla_risk": bool(current[7]) if current else bool(latest.get("sla_risk")),
        "sla_reason": (current[8] if current else latest.get("sla_reason")) or "",
        "invoice_total": round(float(current[9] if current else latest.get("invoice_total") or 0), 2),
        "delivery_note": (current[10] if current else latest.get("delivery_note")) or "",
        "timeline": timeline,
    }


def hubs_at_risk() -> list[dict[str, Any]]:
    snap = business_snapshot()
    return [h for h in snap["by_hub"] if h["sla_at_risk"] > 0]


def answer_question(question: str) -> dict[str, Any]:
    """Deterministic tool router over the current view — swap for an LLM later."""
    q = question.lower()
    if any(token in q for token in ("pcl-", "where is", "track", "status of", "notes for")):
        parcel_id = _extract_parcel_id(question)
        if not parcel_id:
            return {
                "tool": "get_parcel",
                "answer": "Ask about a specific tracking number, for example PCL-LIVE-000001.",
                "data": None,
            }
        data = parcel_timeline(parcel_id)
        if not data:
            return {
                "tool": "get_parcel",
                "answer": f"No current-view rows yet for {parcel_id}. Capture and transform may still be catching up.",
                "data": None,
            }
        note = data["delivery_note"] or "No driver note on the latest scan."
        risk = f" SLA risk: {data['sla_reason']}." if data["sla_risk"] else ""
        return {
            "tool": "get_parcel",
            "answer": (
                f"{data['parcel_id']} is {data['latest_status']} at {data['latest_hub']}. "
                f"Latest driver note: {note}.{risk} "
                f"Live invoice total (base + fuel surcharge): {data['invoice_total']:.2f}."
            ),
            "data": data,
        }

    if any(token in q for token in ("surcharge", "fuel", "cost", "invoice", "margin", "exposure")):
        snap = business_snapshot()
        lines = ", ".join(f"{row['region']} {row['fuel_surcharge']:.2f}" for row in snap["surcharge"][:8])
        return {
            "tool": "cost_exposure",
            "answer": (
                f"In-flight surcharge-adjusted exposure is {snap['kpis']['live_cost_exposure']:.2f}. "
                f"Live fuel surcharge ticks: {lines or 'not materialized yet'}."
            ),
            "data": {"kpis": snap["kpis"], "surcharge": snap["surcharge"], "by_hub": snap["by_hub"]},
        }

    if any(token in q for token in ("hub", "delay", "sla", "risk", "weather", "exception", "at risk")):
        hubs = hubs_at_risk()
        if not hubs:
            snap = business_snapshot()
            return {
                "tool": "hubs_at_risk",
                "answer": (
                    f"No hub currently has SLA-at-risk parcels in the current view. "
                    f"{snap['kpis']['in_flight']} parcels are in flight."
                ),
                "data": snap["by_hub"],
            }
        top = hubs[0]
        return {
            "tool": "hubs_at_risk",
            "answer": (
                f"{top['hub_code']} ({top['hub_city']}) is the hotspot: "
                f"{top['sla_at_risk']} parcels at SLA risk, {top['in_flight']} in flight through that hub."
            ),
            "data": hubs,
        }

    snap = business_snapshot()
    k = snap["kpis"]
    return {
        "tool": "business_snapshot",
        "answer": (
            f"Current view: {k['in_flight']} in flight, {k['delivered']} delivered, "
            f"{k['sla_at_risk']} at SLA risk, {k['weather_delays']} weather delays, "
            f"live cost exposure {k['live_cost_exposure']:.2f}."
        ),
        "data": snap,
    }


def _extract_parcel_id(question: str) -> str | None:
    tokens = question.replace(",", " ").replace("?", " ").split()
    for token in tokens:
        upper = token.strip().upper()
        if upper.startswith("PCL-"):
            return upper
    return None
