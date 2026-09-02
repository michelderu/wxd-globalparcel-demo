# Global Parcel - Realtime Operations Demo Spec

## 1) Demo title

**From Transaction to Customer Experience in Milliseconds**  
Global Parcel operational excellence with Cassandra + OpenSearch

## 2) Objective

Show the ledger and the search index filling from the same transform, then walk:

1. Durable parcel timelines on Cassandra.
2. Low-latency customer tracking on OpenSearch.
3. Fit-for-purpose engines — ledger ≠ search.

## 3) Live path

| Min | Move | Proof |
| --- | --- | --- |
| 0–3 | Capture still up | Kafka UI, Cassandra `COUNT(*)`, OpenSearch `_count` |
| 3–8 | Audit UI | http://localhost:8088/audit-ui/ `PCL-000001` |
| 8–12 | Customer UI | http://localhost:8088/customer-ui/ `PCL-LIVE-000001` |
| 12–16 | Dashboards | http://localhost:5601 import `opensearch-dashboards/globalparcel-ops-dashboard.ndjson` |
| 16–20 | Handoff | Driver notes on the ledger → Orchestrate |

## 4) Success

- Audience sees **one capture** feeding Cassandra and OpenSearch.
- Customer tracking is OpenSearch; audit is Cassandra.
