# Control tower

One FastAPI process on `:8088` serves the **current view of the business**. `app.mount(...)` in [`api.py`](api.py) maps `/tower/` to `apps/frontend/control-tower` (`index.html`, JS, CSS). The snapshot JSON comes from warehouse Parquet, not Kafka.

| URL | Reads |
| --- | --- |
| http://localhost:8088/tower/ | Lakehouse current view (`/api/snapshot`) |

`/` redirects to `/tower/`.

```bash
PYTHONPATH=. uvicorn apps.api:app --host 0.0.0.0 --port 8088
```

Customer tracking and audit live in chapter 03 ([`../../03-realtime-operations/README.md`](../../03-realtime-operations/README.md)). Ask the business is watsonx Orchestrate on `:3000` ([`../../04-accelerate-ai/README.md`](../../04-accelerate-ai/README.md)).
