#!/usr/bin/env bash
# Stop the StreamHouse data flow started by ./scripts/start_data_flow.sh
# (produce, shift_left, tableflow). Does not stop Compose or ops/tower UIs.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="${REPO}/.run"

note() { printf '%s\n' "$*"; }
ok() { printf '✓ %s\n' "$*"; }
warn() { printf '⚠ %s\n' "$*" >&2; }

stop_one() {
  local name="$1"
  local pf="${RUN_DIR}/${name}.pid"
  if [[ ! -f "$pf" ]]; then
    warn "${name}: no pid file"
    return 0
  fi
  local pid
  pid="$(cat "$pf" 2>/dev/null || true)"
  if [[ -z "${pid}" ]]; then
    rm -f "$pf"
    warn "${name}: empty pid file removed"
    return 0
  fi
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
    ok "${name} stopped (was pid ${pid})"
  else
    warn "${name}: pid ${pid} not running"
  fi
  rm -f "$pf"
}

note "== Stopping data flow =="
stop_one produce
stop_one shift_left
stop_one tableflow
note "Done. Restart with ./scripts/start_data_flow.sh"
