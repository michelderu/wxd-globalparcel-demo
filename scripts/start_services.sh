#!/usr/bin/env bash
# Install (if needed) and start workshop services for chapters 01–04.
# Does not start capture / shift-left / tableflow pipelines.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="${REPO}/.run"
mkdir -p "$RUN_DIR"

VENV="${REPO}/.venv"
VENV_ACTIVATE="${VENV}/bin/activate"
COMPOSE_DIR="${REPO}/01-streamhouse"
LAKE_DIR="${REPO}/02-lakehouse"
OPS_DIR="${REPO}/03-realtime-operations"
WXO_DIR="${REPO}/04-accelerate-ai"
KIND_CLUSTER="${KIND_CLUSTER_NAME:-wxd}"

note() { printf '%s\n' "$*"; }
warn() { printf '⚠ %s\n' "$*" >&2; }
ok() { printf '✓ %s\n' "$*"; }
die() { printf '✗ %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

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

compose() {
  docker compose -f "${COMPOSE_DIR}/docker-compose.yml" --project-directory "$COMPOSE_DIR" "$@"
}

find_wxd_installer_dir() {
  local d
  for d in \
    "${LAKE_DIR}/watsonx.data-developer-edition-installer" \
    "${REPO}/watsonx.data-developer-edition-installer"
  do
    if [[ -f "${d}/Chart.yaml" ]] || [[ -f "${d}/values.yaml" ]]; then
      printf '%s\n' "$d"
      return 0
    fi
  done
  return 1
}

extract_wxd_installer_if_needed() {
  local tarf dir
  if find_wxd_installer_dir >/dev/null; then
    return 0
  fi
  for tarf in \
    "${LAKE_DIR}/watsonx.data-developer-edition-installer.tar" \
    "${REPO}/watsonx.data-developer-edition-installer.tar"
  do
    if [[ -f "$tarf" ]]; then
      dir="$(dirname "$tarf")"
      note "Extracting $(basename "$tarf") in ${dir}…"
      (cd "$dir" && rm -rf watsonx.data-developer-edition-installer && tar -xf "$(basename "$tarf")")
      find_wxd_installer_dir >/dev/null && return 0
    fi
  done
  return 1
}

# --- prerequisites ------------------------------------------------------------
need_cmd docker
need_cmd python3
need_cmd curl

# --- 01 venv + Python deps ----------------------------------------------------
note "== 01 Python environment =="
if [[ ! -x "${VENV}/bin/python" ]]; then
  note "Creating ${VENV}…"
  python3 -m venv "$VENV"
  ok "venv created"
else
  ok "venv already present"
fi
# shellcheck disable=SC1090
source "$VENV_ACTIVATE"

note "Ensuring chapter 01 (+03) Python packages…"
pip install -q -U pip
pip install -q -r "${COMPOSE_DIR}/requirements.txt"
ok "01 requirements installed"

# --- 01 Compose ---------------------------------------------------------------
if [[ -z "${KAFKA_HOST_IP:-}" ]]; then
  KAFKA_HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  KAFKA_HOST_IP="${KAFKA_HOST_IP:-localhost}"
  export KAFKA_HOST_IP
fi

note "== 01 StreamHouse Compose (KAFKA_HOST_IP=${KAFKA_HOST_IP}) =="
(
  cd "$COMPOSE_DIR"
  docker compose up -d
)

note "Waiting for Kafka, Cassandra, OpenSearch…"
deadline=$((SECONDS + 180))
kafka_ok=0
cass_ok=0
os_ok=0
while (( SECONDS < deadline )); do
  kafka_ok=0
  cass_ok=0
  os_ok=0
  compose exec -T kafka \
    /opt/kafka/bin/kafka-broker-api-versions.sh --bootstrap-server localhost:9092 \
    >/dev/null 2>&1 && kafka_ok=1
  compose exec -T cassandra \
    bash -c "nodetool status | grep -q '^UN'" \
    >/dev/null 2>&1 && cass_ok=1
  curl -sf http://localhost:9200 >/dev/null 2>&1 && os_ok=1
  if (( kafka_ok && cass_ok && os_ok )); then
    break
  fi
  sleep 5
done

if (( !kafka_ok || !cass_ok || !os_ok )); then
  warn "Compose not fully healthy yet (continuing):"
  (( kafka_ok )) || warn "  Kafka :9092"
  (( cass_ok )) || warn "  Cassandra (first boot can take 1–2 min)"
  (( os_ok )) || warn "  OpenSearch :9200"
else
  ok "Kafka, Cassandra, OpenSearch healthy"
fi

if (( kafka_ok || cass_ok || os_ok )); then
  note "Pruning workshop Kafka topics + tables…"
  "${REPO}/scripts/prune_data.sh" || warn "Data prune failed"
else
  warn "Skipping data prune — Compose engines not ready"
fi

# --- 02 watsonx.data ----------------------------------------------------------
note "== 02 watsonx.data (Kind + Helm) =="
wxd_ui="skipped"
wxd_installer=""

if ! command -v kubectl >/dev/null 2>&1 || ! command -v kind >/dev/null 2>&1 || ! command -v helm >/dev/null 2>&1; then
  warn "Need kind, kubectl, and helm on PATH for chapter 02 — skipping watsonx.data install"
else
  if ! kind get clusters 2>/dev/null | grep -Fxq "$KIND_CLUSTER"; then
    note "Creating Kind cluster ${KIND_CLUSTER}…"
    kind create cluster --name "$KIND_CLUSTER"
  else
    mapfile -t kind_nodes < <(docker ps -aq --filter "label=io.x-k8s.kind.cluster=${KIND_CLUSTER}" 2>/dev/null || true)
    if ((${#kind_nodes[@]})); then
      docker start "${kind_nodes[@]}" >/dev/null 2>&1 || true
    fi
    ok "Kind cluster ${KIND_CLUSTER} present"
  fi
  kubectl config use-context "kind-${KIND_CLUSTER}" >/dev/null

  if kubectl get svc -n wxd lhconsole-ui-svc >/dev/null 2>&1; then
    ok "watsonx.data already deployed (lhconsole-ui-svc found)"
  else
    if extract_wxd_installer_if_needed; then
      wxd_installer="$(find_wxd_installer_dir)"
    fi
    if [[ -z "$wxd_installer" ]]; then
      warn "watsonx.data not deployed and installer not found."
      warn "Place watsonx.data-developer-edition-installer.tar (or extracted dir) under 02-lakehouse/ or repo root,"
      warn "then re-run. Docs: https://www.ibm.com/docs/en/watsonxdata/standard/2.3.x?topic=version-installing"
    else
      note "Helm installing watsonx.data from ${wxd_installer} (can take 10+ minutes)…"
      (
        cd "$wxd_installer"
        helm dependency update
        helm upgrade --install wxd . \
          -f values.yaml \
          -f values-secret.yaml \
          --namespace wxd \
          --create-namespace \
          --timeout 15m
      )
      ok "Helm install/upgrade submitted"
      note "Waiting for lhconsole-ui-svc…"
      deadline=$((SECONDS + 900))
      while (( SECONDS < deadline )); do
        kubectl get svc -n wxd lhconsole-ui-svc >/dev/null 2>&1 && break
        sleep 10
      done
    fi
  fi

  if kubectl get svc -n wxd lhconsole-ui-svc >/dev/null 2>&1; then
    stop_pidfile "${RUN_DIR}/wxd-ui.pid"
    pkill -f 'kubectl port-forward -n wxd service/lhconsole-ui-svc 6443:443' 2>/dev/null || true
    sleep 1
    nohup kubectl port-forward -n wxd service/lhconsole-ui-svc 6443:443 \
      >"${RUN_DIR}/wxd-ui.log" 2>&1 &
    echo $! >"${RUN_DIR}/wxd-ui.pid"
    sleep 2
    if kill -0 "$(cat "${RUN_DIR}/wxd-ui.pid")" 2>/dev/null; then
      wxd_ui="https://localhost:6443  (ibmlhadmin / password)"
      ok "watsonx.data UI port-forward"
    else
      wxd_ui="failed — see ${RUN_DIR}/wxd-ui.log"
      warn "$wxd_ui"
    fi
  fi
fi

# --- 01 / 03 FastAPI apps -----------------------------------------------------
note "== 01 control tower + 03 ops API =="
background tower "$COMPOSE_DIR" \
  uvicorn apps.api:app --host 0.0.0.0 --port 8088
background ops "$OPS_DIR" \
  uvicorn apps.api:app --host 0.0.0.0 --port 8081

# --- 04 watsonx Orchestrate + Cassandra agent (no Langflow) -------------------
note "== 04 watsonx Orchestrate + agent (no Langflow) =="
wxo_status="skipped"
chat_status="skipped"
agent_status="skipped"

note "Ensuring chapter 04 Python packages…"
pip install -q -r "${WXO_DIR}/requirements.txt"
ok "04 requirements installed"

wait_wxo_api() {
  local deadline=$((SECONDS + 600))
  note "Waiting for Orchestrate API on :4321…"
  while (( SECONDS < deadline )); do
    if curl -sf -o /dev/null http://localhost:4321/docs; then
      return 0
    fi
    sleep 5
  done
  return 1
}

wire_cassandra_agent() {
  # Models + Cassandra ledger tools + Global Parcel Assistant (not Langflow/OpenSearch agent).
  orchestrate env activate local
  orchestrate models config default -n watsonx/ibm/granite-4-h-small >/dev/null 2>&1 || true
  orchestrate agents import -f agents/ask_orchestrate.yml >/dev/null 2>&1 || true

  local pkg=tools/cassandra_ledger
  # Tools run inside the wxO container and reach host Cassandra via host.docker.internal.
  export CASSANDRA_HOST="${CASSANDRA_HOST:-host.docker.internal}"
  orchestrate tools import -k python -p "$pkg" -f "$pkg/get_parcel_timeline.py" -r "$pkg/requirements.txt" || true
  orchestrate tools import -k python -p "$pkg" -f "$pkg/get_parcel_latest_status.py" -r "$pkg/requirements.txt" || true
  orchestrate tools import -k python -p "$pkg" -f "$pkg/get_parcel_delivery_notes.py" -r "$pkg/requirements.txt" || true
  orchestrate tools import -k python -p "$pkg" -f "$pkg/reconcile_parcel_dispute.py" -r "$pkg/requirements.txt" || true
  orchestrate agents import -f agents/parcel_assistant_cassandra.yml || true
}

if [[ ! -f "${WXO_DIR}/.env" ]]; then
  warn "Missing 04-accelerate-ai/.env — skip Orchestrate (script never creates or edits it)"
else
  (
    cd "$WXO_DIR"
    # Linux / self-managed Docker: avoid Lima+QEMU default (idempotent for workshops).
    orchestrate settings docker host --user-managed >/dev/null 2>&1 || true
    note "Starting Developer Edition without Langflow (may take several minutes)…"
    orchestrate server start -e .env
  )
  if wait_wxo_api; then
    wxo_status="http://localhost:4321"
    ok "Orchestrate Developer Edition"
    (
      cd "$WXO_DIR"
      wire_cassandra_agent
    )
    agent_status="Global Parcel Assistant (Cassandra ledger tools)"
    ok "Agent wired (Cassandra tools; Langflow skipped)"

    (
      cd "$WXO_DIR"
      orchestrate env activate local >/dev/null 2>&1 || true
      orchestrate chat start >/dev/null 2>&1 || true
    )
    chat_status="http://localhost:3000/chat-lite"
    ok "Chat UI start requested"
  else
    warn "Orchestrate API did not become ready on :4321 — skip agent wiring"
  fi
fi

cat <<EOF

========================================================================
Workshop services 01–04 (install-if-needed + start; stream data pruned)
------------------------------------------------------------------------
  Kafka UI                 http://localhost:8085
  OpenSearch               http://localhost:9200
  OpenSearch Dashboards    http://localhost:5601
  Cassandra                localhost:9042
  Kafka                    localhost:9092  (advertised ${KAFKA_HOST_IP}:9092)
  Control tower (01)       http://localhost:8088/tower/
  Ops apps (03)            http://localhost:8081/customer-ui/  |  /audit-ui/
  watsonx.data UI (02)     ${wxd_ui}
  watsonx Orchestrate (04) ${wxo_status}
  Agent (04)               ${agent_status}
  Chat UI (04)             ${chat_status}
------------------------------------------------------------------------
Logs / PIDs: ${RUN_DIR}/
Still manual (data generation / pipelines):
  ./scripts/start_data_flow.sh
Langflow MCP / OpenSearch agent: follow 04-accelerate-ai/README.md step 8
========================================================================
EOF
