# Operate the business

One FastAPI process on `:8081` serves JSON **and** the UIs. `app.mount(...)` in [`api.py`](api.py) maps a URL path to a folder of static files (`index.html`, JS, CSS). The browser talks to `:8081`.

| URL | Mounted from | Reads |
| --- | --- | --- |
| http://localhost:8081/customer-ui/ | `apps/frontend/customer-tracking` | **OpenSearch** |
| http://localhost:8081/audit-ui/ | `apps/frontend/audit-reconciliation` | **Cassandra** |

`/` redirects to `/customer-ui/`.

```bash
uvicorn apps.api:app --host 0.0.0.0 --port 8081
```

Capture and transform in chapter 01 fill Cassandra and OpenSearch; these pages **run on those products**. The control tower stays on `:8088`.
