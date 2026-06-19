# Cassandra ledger tools (session 02 → 03)

Python tools that read the **authoritative parcel ledger** from session `02-realtime-operations`:

- Keyspace: `globalparcel_ops`
- Table: `parcel_events_by_parcel`

| Tool | Purpose |
| --- | --- |
| `get_parcel_timeline` | Full event timeline for a parcel (includes `delivery_note`) |
| `get_parcel_latest_status` | Latest status, hub, region, ETA |
| `get_parcel_delivery_notes` | Driver / hub operator notes from the ledger |
| `reconcile_parcel_dispute` | Compare customer claim vs ledger (includes latest driver note) |

## Langflow flows

| Flow | Purpose |
| --- | --- |
| [langflow/parcel_opensearch_customer.json](langflow/parcel_opensearch_customer.json) | Customer-facing OpenSearch view via `GET /api/customer/{parcel_id}` |

Build: `python tools/langflow/build_customer_tracking_flow.py` — see [langflow/README.md](langflow/README.md). Reconciliation uses Cassandra Python tools on the agent, not Langflow.

## Prerequisites
2. wxO Developer Edition running (`orchestrate env activate local`).

```bash
cd 02-realtime-operations
docker compose up -d cassandra
# … create schema + seed (see 02 README)
```

## Import into wxO

From `03-accelerate-ai/`:

```bash
PKG=tools/cassandra_ledger

orchestrate tools import -k python -p "$PKG" -f "$PKG/get_parcel_timeline.py" -r "$PKG/requirements.txt"
orchestrate tools import -k python -p "$PKG" -f "$PKG/get_parcel_latest_status.py" -r "$PKG/requirements.txt"
orchestrate tools import -k python -p "$PKG" -f "$PKG/get_parcel_delivery_notes.py" -r "$PKG/requirements.txt"
orchestrate tools import -k python -p "$PKG" -f "$PKG/reconcile_parcel_dispute.py" -r "$PKG/requirements.txt"

orchestrate agents import -f agents/parcel_assistant.yml
```

## Networking (wxO container → host Cassandra)

Tools default to `CASSANDRA_HOST=host.docker.internal`. On Linux, if lookups fail:

```bash
export CASSANDRA_HOST=172.17.0.1   # or your docker bridge gateway
```

Optional overrides:

| Variable | Default |
| --- | --- |
| `CASSANDRA_HOST` | `host.docker.internal` |
| `CASSANDRA_PORT` | `9042` |
| `CASSANDRA_KEYSPACE` | `globalparcel_ops` |

## Test without wxO

```bash
cd 03-accelerate-ai
CASSANDRA_HOST=127.0.0.1 python scripts/test_ledger_tools.py PCL-000001
```

## Example agent prompts

- “What delivery notes are on the ledger for **PCL-000001**?”
- “Show the Cassandra timeline for **PCL-LIVE-000001**.”
- “Customer says **DELIVERED** for **PCL-000001** — reconcile and quote the latest driver note.”
