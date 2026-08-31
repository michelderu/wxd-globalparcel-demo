"""Serve StreamHouse apps on IBM engines + the lakehouse current view.

Read paths (unchanged from the previous edition, now fed by one capture bus):

- /audit-ui/     Cassandra ledger (source of truth)
- /customer-ui/  OpenSearch customer tracking
- /tower/        current view of the business (Iceberg / watsonx.data materialization)
- /ask/          natural language over that current view
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
from pydantic import BaseModel

from shared.config import (
    CASSANDRA_HOST,
    CASSANDRA_KEYSPACE,
    CASSANDRA_PORT,
    OPENSEARCH_INDEX,
    OPENSEARCH_URL,
    REPO_ROOT,
)
from shared.queries import answer_question, business_snapshot

cluster: Cluster | None = None
session = None
os_client: OpenSearch | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global cluster, session, os_client
    try:
        cluster = Cluster([CASSANDRA_HOST], port=CASSANDRA_PORT)
        session = cluster.connect(CASSANDRA_KEYSPACE)
    except Exception:
        cluster = None
        session = None
    try:
        os_client = OpenSearch(hosts=[OPENSEARCH_URL])
        os_client.info()
    except Exception:
        os_client = None
    try:
        yield
    finally:
        if os_client is not None:
            os_client.close()
        if cluster is not None:
            cluster.shutdown()


app = FastAPI(title="Global Parcel StreamHouse", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend = Path(__file__).resolve().parent / "frontend"
ops_frontend = REPO_ROOT / "02-realtime-operations" / "frontend"
app.mount("/tower", StaticFiles(directory=frontend / "control-tower", html=True), name="tower")
app.mount("/ask", StaticFiles(directory=frontend / "ask", html=True), name="ask")
app.mount("/audit-ui", StaticFiles(directory=ops_frontend / "audit-reconciliation", html=True), name="audit-ui")
app.mount("/customer-ui", StaticFiles(directory=ops_frontend / "customer-tracking", html=True), name="customer-ui")
app.mount("/track", StaticFiles(directory=ops_frontend / "customer-tracking", html=True), name="track")


class AskRequest(BaseModel):
    question: str


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/tower/")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "view": "streamhouse-current",
        "cassandra": "ok" if session is not None else "down",
        "opensearch": "ok" if os_client is not None else "down",
    }


@app.get("/api/snapshot")
def snapshot() -> dict:
    return business_snapshot()


@app.get("/api/audit/{parcel_id}")
def get_audit(parcel_id: str) -> dict[str, Any]:
    if session is None:
        raise HTTPException(status_code=503, detail="Cassandra session not ready")

    rows = session.execute(
        """
        SELECT parcel_id, event_ts, status, hub_code, region, latitude, longitude, exception_code, customer_eta, delivery_note
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
            "delivery_note": getattr(r, "delivery_note", None) or "",
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
        "query": {"term": {"parcel_id": parcel_id.strip().upper()}},
    }
    result = os_client.search(index=OPENSEARCH_INDEX, body=query)
    hits = result.get("hits", {}).get("hits", [])
    if not hits:
        raise HTTPException(status_code=404, detail=f"No customer events found for {parcel_id}")

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
        "parcel_id": parcel_id.strip().upper(),
        "latest_status": latest.get("status") or "UNKNOWN",
        "latest_hub": latest.get("hub_code") or "-",
        "customer_eta": latest.get("customer_eta"),
        "latest_event_ts": latest.get("event_ts"),
        "timeline": timeline,
    }


@app.post("/api/ask")
def ask(body: AskRequest) -> dict:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is empty")
    return answer_question(question)
