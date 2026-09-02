#!/usr/bin/env bash
# Until the Spark master pod is Running: print kubectl get events for that pod.
# Once Running: kubectl logs -f (full follow). Repeats after the log stream ends.

set -u

NAMESPACE="${1:-wxd}"
WAIT_WHEN_EMPTY_SEC="${2:-3}"
EVENTS_POLL_SEC="${3:-3}"

# Override if your cluster uses different master pod names, e.g.:
#   MASTER_POD_REGEX='^spark-master-deployment-.*$' ./watch_spark_master_logs.sh
_DEFAULT_MASTER_REGEX='^spark-master-.*$'
MASTER_POD_REGEX="${MASTER_POD_REGEX:-$_DEFAULT_MASTER_REGEX}"

echo "Spark master: events until Running, then kubectl logs -f (stdout)"
echo "Namespace: ${NAMESPACE}"
echo "Pod name regex: ${MASTER_POD_REGEX}"
echo "Poll when no pod / not Running: ${WAIT_WHEN_EMPTY_SEC}s / ${EVENTS_POLL_SEC}s"
echo

while true; do
  POD_NAME=""

  # 1) Wait until a master pod exists (any phase)
  while [[ -z "$POD_NAME" ]]; do
    POD_NAME="$(
      kubectl get pods -n "$NAMESPACE" --no-headers -o custom-columns=':metadata.name' 2>/dev/null \
        | grep -E "$MASTER_POD_REGEX" \
        | head -n 1
    )"
    if [[ -z "$POD_NAME" ]]; then
      echo "[$(date +'%Y-%m-%d %H:%M:%S')] No pod matching '${MASTER_POD_REGEX}' yet; waiting ${WAIT_WHEN_EMPTY_SEC}s..."
      sleep "$WAIT_WHEN_EMPTY_SEC"
    fi
  done

  echo "[$(date +'%Y-%m-%d %H:%M:%S')] Found master pod: ${POD_NAME}"

  # 2) Events until Running
  while true; do
    if ! kubectl get pod -n "$NAMESPACE" "$POD_NAME" &>/dev/null; then
      echo "[$(date +'%Y-%m-%d %H:%M:%S')] Pod '${POD_NAME}' gone; rescanning..."
      continue 2
    fi

    phase="$(kubectl get pod -n "$NAMESPACE" "$POD_NAME" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
    if [[ "$phase" == "Running" ]]; then
      echo "[$(date +'%Y-%m-%d %H:%M:%S')] Pod '${POD_NAME}' is Running; switching to log follow."
      break
    fi

    ts="$(date +'%Y-%m-%d %H:%M:%S')"
    echo
    echo "==================== ${ts} ${POD_NAME} phase=${phase} ===================="
    echo "kubectl get events -n ${NAMESPACE} --field-selector involvedObject.name=${POD_NAME},involvedObject.kind=Pod --sort-by=.lastTimestamp"
    kubectl get events -n "$NAMESPACE" \
      --field-selector "involvedObject.name=${POD_NAME},involvedObject.kind=Pod" \
      --sort-by='.lastTimestamp' -o wide 2>&1

    sleep "$EVENTS_POLL_SEC"
  done

  # 3) Follow logs until stream ends
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] Following logs for pod: ${POD_NAME} (Ctrl+C to exit)"
  echo "kubectl logs -f --all-containers=true --prefix=true -n ${NAMESPACE} ${POD_NAME}"
  kubectl logs -f --all-containers=true --prefix=true -n "$NAMESPACE" "$POD_NAME" 2>&1 || true
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] Log stream ended; rescanning..."
done
