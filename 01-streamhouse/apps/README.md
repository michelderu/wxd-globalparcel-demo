# Run the business

IBM engines plus the StreamHouse current view.

| App | URL | Engine |
| --- | --- | --- |
| Control tower | http://localhost:8088/tower/ | Lakehouse current view |
| Customer tracking | http://localhost:8088/customer-ui/ | **OpenSearch** |
| Audit / reconciliation | http://localhost:8088/audit-ui/ | **Cassandra** |
| watsonx Orchestrate | http://localhost:3000/chat-lite | Ledger tools + Langflow customer API |

```bash
PYTHONPATH=. uvicorn apps.api:app --host 0.0.0.0 --port 8088
```

The API does not read Kafka. Capture and transform fill Cassandra, OpenSearch, and Iceberg; apps **run on those products**.

Full agent lab: [`../../04-accelerate-ai/README.md`](../../04-accelerate-ai/README.md).
