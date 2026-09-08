"""Fetch the full parcel timeline from the Cassandra ledger."""

from ibm_watsonx_orchestrate.agent_builder.tools import tool

from cassandra_client import fetch_timeline


@tool()
def get_parcel_timeline(parcel_id: str) -> dict:
    """Return the authoritative parcel event timeline from the Cassandra ledger.

    Use this when a user asks where a parcel is, what happened on its route,
    or needs the source-of-truth operational history. Session 01 stores events
    in globalparcel_ops.parcel_events_by_parcel.

    Args:
        parcel_id: Parcel identifier (for example PCL-LIVE-000001).

    Returns:
        dict: Parcel id, event count, and timeline ordered newest event first.
    """
    timeline = fetch_timeline(parcel_id)
    if not timeline:
        return {
            "parcel_id": parcel_id,
            "found": False,
            "message": (
                f"No events in Cassandra for {parcel_id}. "
                "Start session 01 StreamHouse (capture + transform) so Cassandra has parcel events."
            ),
            "timeline": [],
        }

    return {
        "parcel_id": parcel_id,
        "found": True,
        "event_count": len(timeline),
        "latest_status": timeline[0]["status"],
        "latest_hub": timeline[0]["hub_code"],
        "timeline": timeline,
    }
