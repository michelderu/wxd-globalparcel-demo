"""Realtime operations API for audit and customer tracking views.

Run from 02-realtime-operations/:
    uvicorn realtime_ops_api:app --app-dir backend --host 0.0.0.0 --port 8081
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from cassandra.cluster import Cluster
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from opensearchpy import OpenSearch


CASSANDRA_HOST = "127.0.0.1"
CASSANDRA_PORT = 9042
KEYSPACE = "globalparcel_ops"


cluster: Cluster | None = None
session = None
os_client: OpenSearch | None = None
OS_INDEX = "parcel-events-live"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cluster, session, os_client
    cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
    session = cluster.connect(KEYSPACE)
    os_client = OpenSearch(hosts=["http://localhost:9200"])
    try:
        yield
    finally:
        if os_client is not None:
            os_client.close()
        if cluster is not None:
            cluster.shutdown()


app = FastAPI(title="Global Parcel Realtime Ops API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = Path(__file__).resolve().parent.parent / "frontend" / "audit-reconciliation"
app.mount("/audit-ui", StaticFiles(directory=frontend_dir, html=True), name="audit-ui")
customer_frontend_dir = Path(__file__).resolve().parent.parent / "frontend" / "customer-tracking"
app.mount("/customer-ui", StaticFiles(directory=customer_frontend_dir, html=True), name="customer-ui")


@app.get("/")
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/audit-ui/")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/audit/{parcel_id}")
def get_audit(parcel_id: str) -> dict[str, Any]:
    if session is None:
        raise HTTPException(status_code=503, detail="Cassandra session not ready")

    rows = session.execute(
        """
        SELECT parcel_id, event_ts, status, hub_code, region, latitude, longitude, exception_code, customer_eta
        FROM parcel_events_by_parcel
        WHERE parcel_id = %s
        """,
        [parcel_id],
    )
    events = list(rows)
    if not events:
        raise HTTPException(status_code=404, detail=f"No Cassandra events found for parcel {parcel_id}")

    timeline = [
        {
            "event_ts": r.event_ts.isoformat() if r.event_ts else None,
            "status": r.status,
            "hub_code": r.hub_code,
            "region": r.region,
            "geo_position": {
                "latitude": r.latitude,
                "longitude": r.longitude,
            },
            "exception_code": r.exception_code or "",
            "customer_eta": r.customer_eta.isoformat() if r.customer_eta else None,
        }
        for r in events
    ]

    latest = timeline[0]
    app_status = timeline[1]["status"] if len(timeline) > 1 else latest["status"]
    mismatch = app_status != latest["status"]

    return {
        "parcel_id": parcel_id,
        "summary": {
            "customer_claim": 'Customer says "Not delivered"',
            "customer_app_status": app_status,
            "cassandra_latest_status": latest["status"],
            "reconciliation_result": "Mismatch detected" if mismatch else "No mismatch",
            "index_lag_suspected": mismatch,
        },
        "timeline": timeline,
    }


@app.get("/api/customer/{parcel_id}")
def get_customer_view(parcel_id: str) -> dict[str, Any]:
    if os_client is None:
        raise HTTPException(status_code=503, detail="OpenSearch client not ready")

    query = {
        "size": 100,
        "sort": [{"event_ts": {"order": "desc"}}],
        "query": {"term": {"parcel_id": parcel_id}},
    }
    result = os_client.search(index=OS_INDEX, body=query)
    hits = result.get("hits", {}).get("hits", [])
    if not hits:
        raise HTTPException(status_code=404, detail=f"No customer events found for parcel {parcel_id}")

    timeline = []
    for hit in hits:
        source = hit.get("_source", {})
        geo = source.get("geo_position") or {}
        timeline.append(
            {
                "event_ts": source.get("event_ts"),
                "status": source.get("status"),
                "hub_code": source.get("hub_code"),
                "region": source.get("region"),
                "exception_code": source.get("exception_code") or "",
                "customer_eta": source.get("customer_eta"),
                "geo_position": {
                    "latitude": geo.get("lat"),
                    "longitude": geo.get("lon"),
                },
            }
        )

    latest = timeline[0]
    return {
        "parcel_id": parcel_id,
        "latest_status": latest.get("status") or "UNKNOWN",
        "latest_hub": latest.get("hub_code") or "-",
        "customer_eta": latest.get("customer_eta"),
        "latest_event_ts": latest.get("event_ts"),
        "timeline": timeline,
    }
