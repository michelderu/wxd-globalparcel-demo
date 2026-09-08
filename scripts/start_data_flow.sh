#!/usr/bin/env bash
# Start the StreamHouse data flow (blocking jobs in the background):
#   capture.produce → transform.shift_left → tableflow.materialize
# Prerequisites: Compose up (./scripts/start_services.sh or docker compose in 01-streamhouse).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="${REPO}/.run"
COMPOSE_DIR="${REPO}/01-streamhouse"
OPS_DIR="${REPO}/03-realtime-operations"
VENV_ACTIVATE="${REPO}/.venv/bin/activate"

mkdir -p "$RUN_DIR"

note() { printf '%s\n' "$*"; }
warn() { printf '⚠ %s\n' "$*" >&2; }
ok() { printf '✓ %s\n' "$*"; }
die() { printf '✗ %s\n' "$*" >&2; exit 1; }

[[ -f "$VENV_ACTIVATE" ]] || die "Missing ${REPO}/.venv — create it first (see 01-streamhouse/README.md)"

compose() {
  docker compose -f "${COMPOSE_DIR}/docker-compose.yml" --project-directory "$COMPOSE_DIR" "$@"
}

if ! compose exec -T kafka \
  /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 \
  >/dev/null 2>&1; then
  die "Kafka is not ready — run ./scripts/start_services.sh first"
fi

stop_pidfile() {
  local pf="$1"
  if [[ -f "$pf" ]]; then
    local pid
    pid="$(cat "$pf" 2>/dev/null || true)"
    if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 1
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$pf"
  fi
}

background() {
  local name="$1"
  local cwd="$2"
  shift 2
  stop_pidfile "${RUN_DIR}/${name}.pid"
  (
    cd "$cwd"
    # shellcheck disable=SC1090
    source "$VENV_ACTIVATE"
    nohup "$@" >"${RUN_DIR}/${name}.log" 2>&1 &
    echo $! >"${RUN_DIR}/${name}.pid"
  )
  sleep 1
  if kill -0 "$(cat "${RUN_DIR}/${name}.pid")" 2>/dev/null; then
    ok "${name} (pid $(cat "${RUN_DIR}/${name}.pid")) — log ${RUN_DIR}/${name}.log"
  else
    warn "${name} failed to stay up — see ${RUN_DIR}/${name}.log"
  fi
}

note "== Starting data flow from ${COMPOSE_DIR} =="

background produce "$COMPOSE_DIR" python -m capture.produce
# Let produce create topics before the transform/tableflow consumers attach.
sleep 5
background shift_left "$COMPOSE_DIR" python -m transform.shift_left
# shift_left creates the Cassandra keyspace; restart ops so audit-ui can connect if it started earlier.
sleep 8
if [[ -f "${RUN_DIR}/ops.pid" ]] || curl -sf -o /dev/null http://127.0.0.1:8081/api/health; then
  note "Restarting ops API so audit-ui picks up Cassandra…"
  background ops "$OPS_DIR" uvicorn apps.api:app --host 0.0.0.0 --port 8081
fi
sleep 3
background tableflow "$COMPOSE_DIR" python -m tableflow.materialize

cat <<EOF

Data flow running (Ctrl+C does not stop these — kill via PIDs under ${RUN_DIR}/):
  produce      ${RUN_DIR}/produce.log
  shift_left   ${RUN_DIR}/shift_left.log
  tableflow    ${RUN_DIR}/tableflow.log

Suggested parcels once data lands: PCL-000001, PCL-LIVE-000001
  Control tower  http://localhost:8088/tower/
  Customer UI    http://localhost:8081/customer-ui/
  Audit UI       http://localhost:8081/audit-ui/
EOF
