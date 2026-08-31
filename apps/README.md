# 4 — Run the business

IBM engines plus the StreamHouse current view.

| App | URL | Engine |
| --- | --- | --- |
| Control tower | http://localhost:8088/tower/ | Lakehouse current view (Tableflow / watsonx.data) |
| Customer tracking | http://localhost:8088/customer-ui/ | **OpenSearch** (same UI as session 02) |
| Audit / reconciliation | http://localhost:8088/audit-ui/ | **Cassandra** (same UI as session 02) |
| Ask the business | http://localhost:8088/ask/ | Current-view tools |
| watsonx Orchestrate | session 03 | Cassandra ledger tools + Langflow customer API |

```bash
PYTHONPATH=. uvicorn apps.api:app --host 0.0.0.0 --port 8088
```

The API does not read Kafka. Capture and transform fill Cassandra, OpenSearch, and Iceberg; apps **run on those products**.

Full agent lab: [`../03-accelerate-ai/README.md`](../03-accelerate-ai/README.md).
