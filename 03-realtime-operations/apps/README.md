# Operate the business

One FastAPI process on `:8081` serves JSON **and** the UIs. `app.mount(...)` in [`api.py`](api.py) maps a URL path to a folder of static files. The browser talks to `:8081`; the HTML lives next to this chapter.

| URL | Mounted from | Reads |
| --- | --- | --- |
| http://localhost:8081/customer-ui/ | `frontend/customer-tracking` | **OpenSearch** |
| http://localhost:8081/audit-ui/ | `frontend/audit-reconciliation` | **Cassandra** |

`/` redirects to `/customer-ui/`.

```bash
PYTHONPATH=. uvicorn apps.api:app --host 0.0.0.0 --port 8081
```

Capture and transform in chapter 01 fill Cassandra and OpenSearch; these pages **run on those products**. The control tower stays on `:8088`.
