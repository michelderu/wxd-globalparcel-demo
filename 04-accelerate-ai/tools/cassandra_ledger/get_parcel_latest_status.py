"""Read the latest parcel status from the Cassandra ledger."""

from ibm_watsonx_orchestrate.agent_builder.tools import tool

from cassandra_client import fetch_timeline


@tool()
def get_parcel_latest_status(parcel_id: str) -> dict:
    """Return the latest parcel status from the Cassandra transactional ledger.

    Use for quick status checks when the user only needs the current operational
    state (status, hub, region, ETA) without the full event history.

    Args:
        parcel_id: Parcel identifier (for example PCL-LIVE-000001).

    Returns:
        dict: Latest ledger status fields for the parcel.
    """
    timeline = fetch_timeline(parcel_id)
    if not timeline:
        return {
            "parcel_id": parcel_id,
            "found": False,
            "message": f"No Cassandra events found for {parcel_id}.",
        }

    latest = timeline[0]
    return {
        "parcel_id": parcel_id,
        "found": True,
        "status": latest["status"],
        "hub_code": latest["hub_code"],
        "region": latest["region"],
        "exception_code": latest["exception_code"],
        "customer_eta": latest["customer_eta"],
        "last_event_ts": latest["event_ts"],
        "geo_position": {
            "latitude": latest["latitude"],
            "longitude": latest["longitude"],
        },
    }
