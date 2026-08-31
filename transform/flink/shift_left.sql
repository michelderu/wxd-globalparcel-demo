-- StreamHouse transform in production shape (Apache Flink SQL).
-- The Python job in shift_left.py implements this same contract locally.
--
-- Capture topics  →  business-ready topics  →  Tableflow / Iceberg
-- Laptop: Apache Kafka advertised as kafka:29092 on the compose network,
--         localhost:9092 from the host (same pattern as Cassandra :9042).

CREATE TABLE parcel_events (
  parcel_id STRING,
  event_ts TIMESTAMP_LTZ(3),
  status STRING,
  hub_code STRING,
  hub_city STRING,
  hub_country STRING,
  region STRING,
  latitude DOUBLE,
  longitude DOUBLE,
  exception_code STRING,
  customer_eta TIMESTAMP_LTZ(3),
  delivery_note STRING,
  origin_hub STRING,
  destination_hub STRING
) WITH (
  'connector' = 'kafka',
  'topic' = 'parcel.events',
  'properties.bootstrap.servers' = 'kafka:29092',
  'scan.startup.mode' = 'earliest-offset',
  'format' = 'json'
);

CREATE TABLE fuel_surcharge (
  region STRING,
  fuel_surcharge DOUBLE,
  updated_at TIMESTAMP_LTZ(3),
  PRIMARY KEY (region) NOT ENFORCED
) WITH (
  'connector' = 'upsert-kafka',
  'topic' = 'fuel.surcharge',
  'properties.bootstrap.servers' = 'kafka:29092',
  'key.format' = 'raw',
  'value.format' = 'json'
);

CREATE TABLE parcel_events_enriched (
  parcel_id STRING,
  event_ts TIMESTAMP_LTZ(3),
  status STRING,
  hub_code STRING,
  region STRING,
  base_rate DOUBLE,
  fuel_surcharge DOUBLE,
  invoice_total DOUBLE,
  sla_risk BOOLEAN,
  sla_reason STRING,
  delivery_note STRING
) WITH (
  'connector' = 'kafka',
  'topic' = 'parcel.events.enriched',
  'properties.bootstrap.servers' = 'kafka:29092',
  'format' = 'json'
);

CREATE TABLE parcel_current (
  parcel_id STRING,
  event_ts TIMESTAMP_LTZ(3),
  status STRING,
  hub_code STRING,
  region STRING,
  invoice_total DOUBLE,
  sla_risk BOOLEAN,
  sla_reason STRING,
  delivery_note STRING,
  PRIMARY KEY (parcel_id) NOT ENFORCED
) WITH (
  'connector' = 'upsert-kafka',
  'topic' = 'parcel.current',
  'properties.bootstrap.servers' = 'kafka:29092',
  'key.format' = 'raw',
  'value.format' = 'json'
);

-- Shift left: price and risk-flag each scan as it arrives.
INSERT INTO parcel_events_enriched
SELECT
  e.parcel_id,
  e.event_ts,
  e.status,
  e.hub_code,
  e.region,
  20.0 AS base_rate,
  COALESCE(s.fuel_surcharge, 5.0) AS fuel_surcharge,
  20.0 + COALESCE(s.fuel_surcharge, 5.0) AS invoice_total,
  (e.exception_code = 'WX_DELAY' OR (e.status <> 'DELIVERED' AND e.event_ts > e.customer_eta)) AS sla_risk,
  CASE
    WHEN e.exception_code = 'WX_DELAY' THEN 'Weather delay at hub — ETA at risk'
    WHEN e.status <> 'DELIVERED' AND e.event_ts > e.customer_eta THEN 'Past customer ETA without delivery scan'
    ELSE ''
  END AS sla_reason,
  e.delivery_note
FROM parcel_events e
LEFT JOIN fuel_surcharge FOR SYSTEM_TIME AS OF e.event_ts s
  ON e.region = s.region;

INSERT INTO parcel_current
SELECT
  parcel_id, event_ts, status, hub_code, region,
  invoice_total, sla_risk, sla_reason, delivery_note
FROM parcel_events_enriched;
