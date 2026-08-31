# StreamHouse Global Parcel — demo spec

## Title

**Capture the business. Run the business.**  
StreamHouse concepts on IBM watsonx.data, Cassandra, and OpenSearch.

## Objective

In 20–25 minutes, developers should feel four verbs **and** the IBM engines:

1. Capture continuously (Kafka).
2. Transform on the stream into **Cassandra + OpenSearch + Iceberg**.
3. Query history and live in **watsonx.data**.
4. Run customer tracking (OpenSearch), audit (Cassandra), control tower, and Orchestrate on that picture.

## Live path

| Min | Move | Proof |
| --- | --- | --- |
| 0–3 | Teaser + fit-for-purpose engines | README mermaid |
| 3–7 | `docker compose up -d` | Cassandra healthy, OpenSearch `:9200`, Kafka `:9092`, Kafka UI `:8080` |
| 7–10 | `python -m capture.produce` | Kafka topics grow |
| 10–14 | `python -m transform.shift_left` | Cassandra count grows; OpenSearch `_count` grows |
| 14–18 | Control tower + `/customer-ui/` + `/audit-ui/` | Same parcel, three products |
| 18–25 | Optional: watsonx.data federation SQL, or Orchestrate prompt | Session 01 / 03 |

## Success

- Audience sees **one capture** feeding Cassandra, OpenSearch, and the lakehouse.
- Customer tracking is still OpenSearch; audit is still Cassandra.
- watsonx.data remains the governed SQL / federation plane.
