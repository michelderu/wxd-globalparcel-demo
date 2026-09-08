#!/usr/bin/env bash
# Wipe workshop stream data so the next capture/transform/tableflow run starts clean.
# - Kafka topics (recreated by capture.produce)
# - Cassandra ledger table
# - OpenSearch customer index
# - Local warehouse / Iceberg Parquet under 01-streamhouse/data/
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_DIR="${REPO}/01-streamhouse"
DATA_DIR="${COMPOSE_DIR}/data"

compose() {
  docker compose -f "${COMPOSE_DIR}/docker-compose.yml" --project-directory "$COMPOSE_DIR" "$@"
}

topics=(
  parcel.events
  fuel.surcharge
  parcel.events.enriched
  parcel.current
  ops.sla.alerts
)

# --- Kafka --------------------------------------------------------------------
if compose exec -T kafka \
  /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 \
  >/dev/null 2>&1; then
  echo "Pruning Kafka topics…"
  for t in "${topics[@]}"; do
    if compose exec -T kafka \
      /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:29092 --delete --topic "$t" \
      >/dev/null 2>&1; then
      echo "  deleted topic ${t}"
    else
      echo "  skipped topic ${t} (missing or already gone)"
    fi
  done
else
  echo "⚠ Kafka not ready — skip topic prune" >&2
fi

# --- Cassandra ----------------------------------------------------------------
if compose exec -T cassandra bash -c "nodetool status | grep -q '^UN'" >/dev/null 2>&1; then
  echo "Pruning Cassandra table globalparcel_ops.parcel_events_by_parcel…"
  if compose exec -T cassandra cqlsh -e \
    "TRUNCATE globalparcel_ops.parcel_events_by_parcel;" >/dev/null 2>&1; then
    echo "  truncated parcel_events_by_parcel"
  else
    echo "  skipped Cassandra table (keyspace/table not created yet)"
  fi
else
  echo "⚠ Cassandra not ready — skip table prune" >&2
fi

# --- OpenSearch ---------------------------------------------------------------
if curl -sf http://localhost:9200 >/dev/null 2>&1; then
  echo "Pruning OpenSearch index parcel-events-live…"
  code="$(curl -s -o /dev/null -w '%{http_code}' -X DELETE http://localhost:9200/parcel-events-live)"
  if [[ "$code" == "200" ]]; then
    echo "  deleted index parcel-events-live"
  else
    echo "  skipped index parcel-events-live (HTTP ${code})"
  fi
else
  echo "⚠ OpenSearch not ready — skip index prune" >&2
fi

# --- Local warehouse (tableflow Parquet / catalog) ----------------------------
echo "Pruning local warehouse under ${DATA_DIR}…"
if [[ -d "$DATA_DIR" ]]; then
  rm -rf "${DATA_DIR}/warehouse" "${DATA_DIR}/catalog.db"
  echo "  removed warehouse/ and catalog.db (if present)"
else
  echo "  skipped (no data/ directory yet)"
fi

echo "Done. Recreate streams with produce → shift_left → tableflow.materialize"
