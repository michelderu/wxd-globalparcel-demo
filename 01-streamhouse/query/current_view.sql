-- Current view of Global Parcel.
-- Run in watsonx.data Presto (session 02) against Iceberg tables Tableflow keeps
-- fresh from Kafka. History from three days ago and a scan from three seconds
-- ago are the same table.

-- 1. How is the business running right now?
SELECT
  COUNT(*) FILTER (WHERE status != 'DELIVERED') AS in_flight,
  COUNT(*) FILTER (WHERE status = 'DELIVERED') AS delivered,
  COUNT(*) FILTER (WHERE sla_risk) AS sla_at_risk,
  ROUND(SUM(invoice_total) FILTER (WHERE status != 'DELIVERED'), 2) AS live_cost_exposure
FROM globalparcel.parcel_current;

-- 2. Which hubs are creating SLA pressure this hour?
SELECT
  hub_code,
  hub_city,
  COUNT(*) FILTER (WHERE status != 'DELIVERED') AS in_flight,
  COUNT(*) FILTER (WHERE sla_risk) AS sla_at_risk
FROM globalparcel.parcel_current
GROUP BY hub_code, hub_city
ORDER BY sla_at_risk DESC, in_flight DESC;

-- 3. Combine historical and live: delay rate by origin over the whole captured stream
SELECT
  origin_hub,
  COUNT(*) AS scans,
  COUNT(*) FILTER (WHERE exception_code = 'WX_DELAY') AS weather_delays
FROM globalparcel.parcel_events
GROUP BY origin_hub
ORDER BY weather_delays DESC;

-- 4. One parcel, current picture (apps and AI use this too)
SELECT parcel_id, status, hub_code, event_ts, sla_risk, sla_reason, delivery_note, invoice_total
FROM globalparcel.parcel_current
WHERE parcel_id = 'PCL-LIVE-000001';
