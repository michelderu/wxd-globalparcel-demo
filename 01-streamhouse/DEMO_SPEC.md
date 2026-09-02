# StreamHouse Global Parcel — demo spec

## Title

**Capture the business. Run the business.**  
One workshop: capture, query, operate, ask.

## Objective

In 20–25 minutes, developers should feel four verbs **and** the IBM engines:

1. Capture continuously (Kafka).
2. Transform on the stream into **Cassandra + OpenSearch + Iceberg**.
3. Query history and live in **watsonx.data**.
4. Run customer tracking (OpenSearch), audit (Cassandra), control tower, and **Orchestrate**.

## Live path

| Min | Move | Proof |
| --- | --- | --- |
| 0–3 | Teaser + fit-for-purpose engines | README mermaid |
| 3–7 | `cd 01-streamhouse` · `docker compose up -d` | Cassandra healthy, OpenSearch `:9200`, Kafka `:9092`, Kafka UI `:8080` |
| 7–10 | `PYTHONPATH=. python -m capture.produce` | Kafka topics grow |
| 10–14 | `PYTHONPATH=. python -m transform.shift_left` | Cassandra count grows; OpenSearch `_count` grows |
| 14–18 | Control tower + `/customer-ui/` + `/audit-ui/` | Same parcel, three products on `:8088` |
| 18–25 | Optional: Presto SQL, or an Orchestrate prompt | Same parcel IDs |

## Success

- Audience sees **one capture** feeding Cassandra, OpenSearch, and the lakehouse.
- Customer tracking is still OpenSearch; audit is still Cassandra.
- watsonx.data remains the governed SQL / federation plane.
- watsonx Orchestrate remains the agentic layer (no laptop chatbot stand-in).
