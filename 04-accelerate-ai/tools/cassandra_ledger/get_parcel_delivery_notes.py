"""Return delivery driver / hub operator notes from the Cassandra ledger."""

from ibm_watsonx_orchestrate.agent_builder.tools import tool

from cassandra_client import fetch_timeline


@tool()
def get_parcel_delivery_notes(parcel_id: str) -> dict:
    """List field notes left by drivers and hub operators for a parcel.

    Use when you need human context behind a scan — proof of delivery wording,
    weather delays, van route details — that the customer OpenSearch view does not show.

    Args:
        parcel_id: Parcel identifier (for example PCL-000001).

    Returns:
        dict: Newest-first notes with status and timestamp for each event.
    """
    timeline = fetch_timeline(parcel_id)
    if not timeline:
        return {
            "parcel_id": parcel_id,
            "found": False,
            "notes": [],
            "message": f"No Cassandra events found for {parcel_id}.",
        }

    notes = [
        {
            "event_ts": event["event_ts"],
            "status": event["status"],
            "hub_code": event["hub_code"],
            "delivery_note": event.get("delivery_note") or "",
        }
        for event in timeline
        if event.get("delivery_note")
    ]

    return {
        "parcel_id": parcel_id,
        "found": True,
        "note_count": len(notes),
        "latest_delivery_note": notes[0]["delivery_note"] if notes else "",
        "notes": notes,
    }
