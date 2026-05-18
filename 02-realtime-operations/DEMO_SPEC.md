# Global Parcel - Realtime Operations Demo Spec

## 1) Demo title

**From Transaction to Customer Experience in Milliseconds**  
Global Parcel operational excellence with Cassandra + OpenSearch

---

## 2) Objective

Demonstrate how Global Parcel can:

1. Ingest parcel lifecycle events at high speed with durable transactional guarantees.
2. Expose rich, low-latency operational and customer-support queries.
3. Scale from startup to scale-up without redesigning the core data path.

---

## 3) Audience

- Business stakeholders (COO, Head of Operations, Customer Experience lead)
- Engineering leadership (CTO, platform lead, principal engineers)
- Delivery teams (backend, SRE, support tooling)

---

## 4) Scope and non-goals

### In scope

- Event ingestion into Cassandra.
- Near real-time indexing into OpenSearch.
- Live querying for customer and operations workflows.
- Narrative on reliability, scalability, and operational excellence.

### Out of scope

- Full production hardening (IAM, backups, DR automation, cost optimization).
- Multi-region active-active setup in this single demo run.
- End-user mobile UI implementation beyond simple simulated client views.

---

## 5) Architecture overview

### Components

- **Event producer**: emits parcel lifecycle events.
- **Cassandra cluster**: durable operational transaction store.
- **Indexer/stream processor**: propagates events to OpenSearch.
- **OpenSearch cluster**: search/query layer for exploratory and customer-facing lookups.
- **Demo API/UI**: queries latest status and exception slices.

### Logical flow

1. Producer generates event (`parcel_id`, `timestamp`, `status`, `location`, `exception_code`).
2. Event is written to Cassandra (append/update by parcel timeline model).
3. Event is indexed in OpenSearch with searchable fields.
4. API/UI reads OpenSearch for low-latency filtered lookup.
5. Optional verification reads Cassandra for source-of-truth audit.

### Functional use-cases: Cassandra vs OpenSearch

| Functional use-case | Cassandra | OpenSearch |
|---|---|---|
| Capture parcel lifecycle events (scan, in-transit, delay, delivered) | Primary event write path | Receives events after indexing |
| Keep authoritative parcel history | System of record for complete event timeline | Searchable copy of event history |
| Answer "where is my parcel?" quickly | Fallback/audit read when needed | Primary support/customer lookup |
| Find active delivery issues by region/hub/time | Not primary in this demo | Primary exception and filter queries |
| Detect delay patterns and hotspot hubs | Not primary in this demo | Primary aggregation and trend queries |
| Reconcile disputed parcel status | Primary source-of-truth validation | Used to compare user-visible result |

---

## 6) Data model (minimal)

### Cassandra table (example)

- `parcel_events_by_parcel`
  - `parcel_id` (partition key)
  - `event_ts` (clustering key, desc)
  - `status`
  - `hub_code`
  - `region`
  - `exception_code`
  - `customer_eta`
  - `geo_position` (latitude/longitude or geohash for parcel event location)

### OpenSearch index (example)

- `parcel-events-*`
  - `parcel_id` (keyword)
  - `event_ts` (date)
  - `status` (keyword)
  - `hub_code` (keyword)
  - `region` (keyword)
  - `exception_code` (keyword)
  - `message` (text)
  - `geo_position` (geo_point)   // latitude/longitude for parcel event location

---

## 7) Business narrative track

### Problem statement

Global Parcel processes millions of shipment events. Existing systems handle either transactional writes or rich search well, but not both together at sustained growth.

### Strategic response

- Use Cassandra for reliable, horizontally scalable event transactions.
- Use OpenSearch for flexible and fast query patterns needed by operations and customer service.

### Business impact statements

- Fewer "where is my parcel" escalations due to near real-time status visibility.
- Faster exception triage lowers SLA penalties and support costs.
- Platform can absorb growth spikes without emergency architecture changes.

---

## 8) Live demo script (20-25 minutes)

### Step 1 - Context and architecture (3 minutes)

- Introduce volume, latency, and reliability requirements.
- Show architecture slide/diagram and explain component roles.

### Step 2 - Baseline health check (2 minutes)

- **Platform operator:** verify Cassandra health (write path ready).
- **Platform operator:** verify OpenSearch health/templates (query path ready).

### Step 3 - Burst ingest simulation (5 minutes)

- Run producer to send parcel events at increasing throughput tiers.
- **Platform operator (Cassandra):** show durable write acknowledgements and ingestion counters.
- **Platform operator (OpenSearch):** show indexing throughput and lag from indexer.

### Step 4 - Search and operations query (5 minutes)

- **Operations analyst / support agent (OpenSearch primary):** query for:
  - latest status by `parcel_id`
  - all exceptions in last 15 minutes by region
  - top hubs by delayed shipments
- **Platform operator (Cassandra verification):** optionally read the same parcel timeline to validate source-of-truth vs indexed view.

### Step 5 - Customer experience view (4 minutes)

- **Customer support view (OpenSearch):** retrieve one parcel timeline and present "latest known status".
- **Audit/reconciliation view (Cassandra):** show source-of-truth read path for dispute workflows.
- Show sub-second response behavior under ongoing ingestion.

### Step 6 - Scale-up storyline and close (3-6 minutes)

- Explain startup -> scale-up path:
  - **Cassandra:** add capacity without downtime for sustained write growth
  - **OpenSearch:** tune shards/replicas for query and aggregation growth
- Summarize outcomes and Q&A.

### Implementation anchors (runbook alignment)

- Seed data artifact: `generated/parcel_events_seed.cql`
- Audit UI: `http://localhost:8080/audit-ui/`
- Customer tracking UI: `http://localhost:8080/customer-ui/`
- OpenSearch dashboard import: `opensearch-dashboards/globalparcel-ops-dashboard.ndjson`

---

## 9) Success criteria

Demo is successful when all are true:

1. Sustained event ingestion completes without dropped writes in demo window.
2. OpenSearch returns query results consistently with acceptable latency target (for demo, <= 1s median).
3. Latest parcel status displayed in near real-time after event production.
4. Audience understands clear separation of concerns:
   - Cassandra = reliable transactional write engine
   - OpenSearch = flexible operational query layer

---

## 10) Risks and mitigations

- **Risk:** Indexing lag causes stale query results.  
  **Mitigation:** include visible indexing-lag metric and set expectation on eventual consistency window.

- **Risk:** Cluster resource contention during live burst.  
  **Mitigation:** pre-warm nodes and cap burst profile to tested thresholds.

- **Risk:** Demo narrative drifts into implementation detail.  
  **Mitigation:** anchor every technical step to customer/operations outcome.

---

## 11) Operational excellence checklist (startup/scale-up lens)

- Defined SLOs for write latency and query latency.
- Basic observability for ingest rate, error rate, indexing lag, and cluster health.
- Runbook for incident triage (write path vs query path separation).
- Capacity test profile documented for expected growth tiers.
- Backlog items identified for production hardening after demo.

---

## 12) Optional extensions

- Add geospatial search on delivery route anomalies.
- Add alerting on exception-rate spikes by hub.
- Add handoff to session 03 for AI-assisted operations triage.
