# Global Parcel — Accelerate AI (watsonx Orchestrate)

Part of the **[workshop overview](../README.md)** and follows [`02-realtime-operations`](../02-realtime-operations/README.md).

This module builds on:
- session 01 federated cost context (`shipping_history` + `fuel_surcharge`)
- session 02 live operational signals (parcel status + exceptions)

Then it moves into **[IBM watsonx Orchestrate](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base)** to show agentic workflows, tools, and orchestration on top of those data products.

Official ADK and Developer Edition documentation live on **[developer.watson-orchestrate.ibm.com](https://developer.watson-orchestrate.ibm.com/)** (see also the [documentation index](https://developer.watson-orchestrate.ibm.com/llms.txt)).

---

## How to use this session

- **Live demo mode:** use a preconfigured `.env`, run `orchestrate server start`, and show one agent flow.
- **Self-paced mode:** complete full `.env` setup, optional features, and remote environment configuration.

---

## What runs “locally”

**watsonx Orchestrate Developer Edition** is IBM’s supported way to run an Orchestrate-compatible stack on your own machine: a local Orchestrate server, local API, optional supporting services (for example observability), and integration points for LLM inference. It is driven by the **`orchestrate` CLI** that ships with the `ibm-watsonx-orchestrate` Python package.

At a glance (from [What is watsonx Orchestrate Developer Edition?](https://developer.watson-orchestrate.ibm.com/developer_edition/wxOde_overview)):

- **Orchestrate server**: `http://localhost:4321` — OpenAPI docs at `http://localhost:4321/docs`
- **Local Orchestrate UI**: `http://localhost:3000`

The full install and `.env` reference is in **[Installing watsonx Orchestrate Developer Edition](https://developer.watson-orchestrate.ibm.com/developer_edition/wxOde_setup)**.

---

## Prerequisites

- **Python 3.11 or later** (see [Getting started with the ADK](https://developer.watson-orchestrate.ibm.com/getting_started/installing)).
- **Hardware** (from the install guide): plan for roughly **8 CPU cores** and **16 GB RAM minimum** (32 GB recommended). With **`--with-doc-processing`**, target **24 GB RAM minimum** (32 GB recommended).
- **LLM inference**: Developer Edition expects access to at least one provider — for example **watsonx Orchestrate SaaS**, **watsonx.ai**, **Groq**, or a **custom LLM via AI Gateway** (same source as the install guide).
- **License**: a valid Developer Edition entitlement (SaaS purchase, on-premises entitlement via myIBM, or IBM Sales). Trial users typically authenticate with a **watsonx Orchestrate account** as described in the install guide.

**Windows note:** If you already use Docker Desktop, the IBM documentation states you should **remove it** and let the ADK installer establish the container environment it expects. Do not install Developer Edition inside a Docker environment you created manually.

**Upgrade note:** If you used Developer Edition before **ADK 2.0**, run `orchestrate server reset` before upgrading so old containers do not conflict (see the install guide).

---

## 1) Install the ADK (CLI)

In a virtual environment (reuse repository-root `.venv` if you already have it):

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade ibm-watsonx-orchestrate
```

Verify the CLI is available:

```bash
orchestrate --help
```

---

## 2) Create and fill a `.env` file

The ADK reads credentials and service passwords from a **`.env`** file. The exact variables depend on how you authenticate to pull and run Developer Edition:

| Method | When to use | Primary variables (see install guide for full list) |
| --- | --- | --- |
| **watsonx Orchestrate account** | SaaS account or **30-day trial** | `WO_DEVELOPER_EDITION_SOURCE=orchestrate`, `WO_INSTANCE`, `WO_API_KEY` |
| **myIBM** | Sales or on-premises entitlement | `WO_DEVELOPER_EDITION_SOURCE=myibm`, `WO_ENTITLEMENT_KEY`, plus watsonx.ai-related keys as documented |
| **Custom image registry** | Images mirrored to your registry | `WO_DEVELOPER_EDITION_SOURCE=custom`, `REGISTRY_URL`, optional `REGISTRY_USERNAME` / `REGISTRY_PASSWORD` |

For **`WO_INSTANCE`** and **`WO_API_KEY`** (Orchestrate account path): log in to your tenant, open **Settings → API details**, copy the **service instance URL**, and **generate an API key**. IBM documents this flow under [Installing watsonx Orchestrate Developer Edition — watsonx Orchestrate account](https://developer.watson-orchestrate.ibm.com/developer_edition/wxOde_setup#watsonx-orchestrate-account).

You also define **embedded service credentials** (PostgreSQL, MinIO, Langfuse, MCP Gateway, ClickHouse, Elasticsearch/OpenSearch, Milvus, encryption key). The install guide lists example values; replace defaults with strong secrets before any shared or long-lived use, and **never commit** your `.env` to git.

If you are **not** in **us-south**, add the regional **`ASSISTANT_*`**, **`ROUTING_LLM_API_BASE`**, and **`WATSONX_URL`** variables described in the install guide.

---

## 3) Start the local server (and optional features)

From the same machine, run (path is your `.env`):

```bash
orchestrate server start -e /absolute/path/to/your/.env
```

Common optional flags (documented on the same page):

- `--with-langfuse` — observability / tracing
- `--with-doc-processing` — document understanding (higher RAM)
- `--with-voice`, `--with-langflow`, connections UI, AI Builder, etc.

The install guide states that **`server start` brings up the server**, not necessarily the web UI. To start the **local Orchestrate UI**, use **`orchestrate chat start`** and see **[Managing watsonx Orchestrate Developer Edition UI](https://developer.watson-orchestrate.ibm.com/developer_edition/manage_ui)**.

After the server is up, you can point the ADK at the local stack:

```bash
orchestrate env activate local
```

Stop or clean up when you are done (see **[Managing watsonx Orchestrate Developer Edition server](https://developer.watson-orchestrate.ibm.com/developer_edition/manage_local_server)**): for example `orchestrate server stop`, or `orchestrate server purge` to remove the local install and data.

---

## 4) Connect the ADK to a cloud Orchestrate tenant (agents in SaaS)

Developer Edition covers **local** runtime. To **author and deploy agents** against IBM-hosted Orchestrate, configure a remote **environment** after you have a service instance URL and API key (IBM Cloud vs AWS vs on-premises types differ). The pattern is documented in [Getting started with the ADK — Configure your environment](https://developer.watson-orchestrate.ibm.com/getting_started/installing#configure-your-environment-in-the-adk), for example:

```bash
orchestrate env add <environment-name> -u <service-instance-url> --type ibm_iam --activate
```

Use the procedure that matches your hosting (IBM Cloud `ibm_iam`, AWS `mcsp`, on-premises username/password or API key as described in that page).

---

## Full product on your own infrastructure

For **production-style** watsonx Orchestrate on OpenShift or other supported platforms (not the laptop Developer Edition), follow the IBM product documentation, for example **[Installing watsonx Orchestrate on-premises](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/base?topic=installing-watsonx-orchestrate-premises)** (and the version of that topic that matches your release).

---

## What’s next (this repo)

Later steps in `03-accelerate-ai` can add Global Parcel–specific agents, tools, and flows (for example calling APIs or summarizing operational metrics). Those assets will be added here as the demo grows.
