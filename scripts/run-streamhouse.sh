#!/usr/bin/env bash
# Facilitator helper: start transform, tableflow, capture, and the API.
# Prefer four terminals in a teaching session so each verb is visible.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
export PYTHONUNBUFFERED=1

if ! docker compose ps --status running --services 2>/dev/null | grep -q kafka; then
  echo "Starting Kafka, Cassandra, OpenSearch…"
  docker compose up -d
fi

echo "Waiting for Kafka on localhost:9092…"
for _ in $(seq 1 30); do
  if python -c "from kafka import KafkaProducer; KafkaProducer(bootstrap_servers='localhost:9092').close()" 2>/dev/null; then
    break
  fi
  sleep 2
done

echo "Waiting for Cassandra (first boot can take ~2 minutes)…"
for _ in $(seq 1 60); do
  if python -c "from cassandra.cluster import Cluster; c=Cluster(['127.0.0.1'], port=9042); s=c.connect(); c.shutdown()" 2>/dev/null; then
    break
  fi
  sleep 2
done

python -m transform.shift_left &
python -m tableflow.materialize &
sleep 2
python -m capture.produce &
exec uvicorn apps.api:app --host 0.0.0.0 --port 8088
