# Global Parcel - 03 Realtime operations

<p align="center">
  <img src="assets/global-parcel-realtime-operations.png" alt="Global Parcel Demo - Realtime Operations" width="100%">
</p>

Part of the **[StreamHouse workshop](../README.md)** — the **operate** chapter: **Cassandra (DataStax HCD)** as the parcel ledger and **OpenSearch** as customer tracking search.

The transform already lands every scan in both engines. This chapter is the product story and the UIs on `:8088` — audit on the ledger, tracking on search.

- **DataStax HCD (based on Apache Cassandra)** as the **trusted transactional backend ledger**: always-on, unbreakable-by-design architecture, and linearly scalable high-throughput writes.
- **OpenSearch** as the **customer-facing tracking search frontend**: low-latency lookup for parcel status, timeline retrieval, and support/operations drill-down.

The goal is to show how teams can go from **parcel event transaction** to **customer experience update in milliseconds**, without sacrificing reliability as volume scales.

You do not force every workload into the lakehouse. Ledger and search stay in engines built for those jobs; watsonx.data stays the governed SQL plane.

---

## Business case

Global Parcel is experiencing growth in parcel volume, regions, and service-level promises. Legacy operational patterns struggle with two opposing needs:

1. **Write every event fast and durably** (scan, handoff, delay, failed delivery, exception).
2. **Query current state flexibly** for contact-center, customer portal, and live operations.

### Why this matters now

- **Customer expectations:** "Where is my parcel?" must answer immediately and accurately.
- **Operational pressure:** dispatch teams need real-time exception visibility, not batch reports.
- **Growth risk:** startup/scale-up teams cannot repeatedly re-platform as volume increases.

### Value proposition of DataStax HCD + OpenSearch

- **DataStax HCD (based on Cassandra)** is the trusted, authoritative transaction ledger for parcel events, built for reliability and horizontal scale under sustained write load.
- **OpenSearch** is the customer-facing query layer that serves fast tracking/search experiences across parcel status, history, and exception views.
- Combined, they bridge the gap between **high-speed ingestion** and **deep query-ability**.
- **watsonx.data** provides the fit-for-purpose foundation: compose the right engine for each workload.

```mermaid
flowchart LR
    Kafka[Kafka] --> T[shift_left]
    T --> B[Cassandra<br/>Trusted transactional ledger]
    T --> C[OpenSearch<br/>Customer-facing search]
    C --> E[Customer Tracking UI :8088]
    B --> G[Audit/Reconciliation UI :8088]
```

---

## Hands-on

From **`01-streamhouse/`**, confirm the engines:

```bash
docker compose exec -T cassandra cqlsh -e "SELECT COUNT(*) FROM globalparcel_ops.parcel_events_by_parcel;"
curl -s "http://localhost:9200/parcel-events-live/_count"
```

### Audit / reconciliation (Cassandra)

Open [http://localhost:8088/audit-ui/](http://localhost:8088/audit-ui/).

This dashboard is the **Cassandra source-of-truth read path** for dispute workflows.

1. Load `PCL-000001` (replayed history) or `PCL-LIVE-000001` (live).
2. Compare **customer app status** with **Cassandra latest status**.
3. Use the map + timeline; look for `WX_DELAY` and **delivery driver notes**.
4. Close the dispute using Cassandra as the authoritative evidence trail.

```bash
# from 01-streamhouse/
docker compose exec -T cassandra cqlsh <<'EOF'
USE globalparcel_ops;
SELECT parcel_id, event_ts, status, hub_code, region, delivery_note
FROM parcel_events_by_parcel
WHERE parcel_id = 'PCL-000001';
EOF
```

### Customer tracking (OpenSearch)

Open [http://localhost:8088/customer-ui/](http://localhost:8088/customer-ui/) and track `PCL-LIVE-000001`.

This view is what the customer sees. It does **not** expose driver notes — those stay on the ledger for the agent chapter.

### OpenSearch Dashboards

1. Open [http://localhost:5601](http://localhost:5601).
2. **Management → Stack Management → Saved Objects → Import**.
3. Import `opensearch-dashboards/globalparcel-ops-dashboard.ndjson`.
4. Open **Global Parcel - Realtime Tracking Dashboard**.

---

## Delivery driver notes

**Delivery driver notes** are short field messages left at each scan. They live on the **Cassandra ledger**. Agents in the next chapter quote them for delays, disputes, or proof of delivery. The customer OpenSearch index exposes status and timeline only.

| Store | `delivery_note` |
| --- | --- |
| **Cassandra ledger** | Yes — every scan |
| **OpenSearch** `parcel-events-live` | No |
| **Audit UI** | Yes (timeline) |

Example notes:

- `Sorted into outbound lane at FRA-01; cage GP-412.`
- `Weather delay — ramp closed for de-icing; customer ETA may slip.`
- `Delivered at Chicago; signed by recipient.`

Continue with [`../04-accelerate-ai/README.md`](../04-accelerate-ai/README.md).
