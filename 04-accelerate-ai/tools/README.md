# Cassandra ledger tools

Python tools that read the **authoritative parcel ledger** written by `transform.shift_left`:

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
| [langflow/parcel_opensearch_customer.json](langflow/parcel_openSearch_customer.json) | Customer-facing OpenSearch view via `GET /api/customer/{parcel_id}` on `:8088` |

Reconciliation uses Cassandra Python tools on the agent, not Langflow.

## Prerequisites

Capture still up (Cassandra `:9042`, apps `:8088`). wxO Developer Edition running (`orchestrate env activate local`).

## Import into wxO

From `04-accelerate-ai/`:

```bash
PKG=tools/cassandra_ledger

orchestrate tools import -k python -p "$PKG" -f "$PKG/get_parcel_timeline.py" -r "$PKG/requirements.txt"
orchestrate tools import -k python -p "$PKG" -f "$PKG/get_parcel_latest_status.py" -r "$PKG/requirements.txt"
orchestrate tools import -k python -p "$PKG" -f "$PKG/get_parcel_delivery_notes.py" -r "$PKG/requirements.txt"
orchestrate tools import -k python -p "$PKG" -f "$PKG/reconcile_parcel_dispute.py" -r "$PKG/requirements.txt"

orchestrate agents import -f agents/parcel_assistant_cassandra.yml
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
cd 04-accelerate-ai
CASSANDRA_HOST=127.0.0.1 python scripts/test_ledger_tools.py PCL-000001
```

## Example agent prompts

- “What delivery notes are on the ledger for **PCL-000001**?”
- “Show the Cassandra timeline for **PCL-LIVE-000001**.”
- “Customer says **DELIVERED** for **PCL-000001** — reconcile and quote the latest driver note.”
