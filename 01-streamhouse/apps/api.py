"""Serve the control tower: current view of the business from lakehouse Parquet."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from shared.queries import business_snapshot

app = FastAPI(title="Global Parcel StreamHouse", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend = Path(__file__).resolve().parent / "frontend"
app.mount("/tower", StaticFiles(directory=frontend / "control-tower", html=True), name="tower")


@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/tower/")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "view": "streamhouse-current"}


@app.get("/api/snapshot")
def snapshot() -> dict:
    return business_snapshot()
