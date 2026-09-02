"""Synthetic delivery driver / hub operator notes for workshop parcel events."""

from __future__ import annotations

import random
from typing import Protocol


class HubLike(Protocol):
    code: str
    city: str


def delivery_note(
    status: str,
    hub: HubLike,
    exception_code: str | None,
    rng: random.Random,
    *,
    driver_names: tuple[str, ...] = ("Marco", "Aisha", "Chen", "Sofia", "James"),
) -> str:
    """Return a short field note a driver or hub operator would leave on scan."""
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
