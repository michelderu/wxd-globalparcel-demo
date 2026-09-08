"""Reconcile a customer dispute against the Cassandra ledger."""

from ibm_watsonx_orchestrate.agent_builder.tools import tool

from cassandra_client import fetch_timeline


@tool()
def reconcile_parcel_dispute(parcel_id: str, customer_claimed_status: str) -> dict:
    """Compare a customer's claimed status with the Cassandra source-of-truth ledger.

    Use when support needs to verify a dispute, delivery claim, or mismatch between
    what the customer says and what was durably written to the transactional ledger.

    Args:
        parcel_id: Parcel identifier (for example PCL-LIVE-000001).
        customer_claimed_status: Status the customer or app claims (for example DELIVERED).

    Returns:
        dict: Reconciliation summary and supporting timeline excerpt.
    """
    timeline = fetch_timeline(parcel_id)
    if not timeline:
        return {
            "parcel_id": parcel_id,
            "found": False,
            "message": f"No Cassandra events found for {parcel_id}.",
        }

    latest = timeline[0]
    ledger_status = latest["status"] or "UNKNOWN"
    claimed = customer_claimed_status.strip().upper()
    ledger = ledger_status.strip().upper()
    mismatch = claimed != ledger

    return {
        "parcel_id": parcel_id,
        "found": True,
        "customer_claimed_status": customer_claimed_status,
        "cassandra_latest_status": ledger_status,
        "reconciliation_result": "Mismatch detected" if mismatch else "Statuses match",
        "mismatch": mismatch,
        "latest_hub": latest["hub_code"],
        "latest_event_ts": latest["event_ts"],
        "latest_delivery_note": latest.get("delivery_note") or "",
        "evidence_timeline": timeline[:5],
        "recommendation": (
            "Use Cassandra timeline as authoritative evidence and refresh customer-facing indexes."
            if mismatch
            else "Ledger agrees with the customer claim."
        ),
    }
