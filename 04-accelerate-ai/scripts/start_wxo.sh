#!/usr/bin/env bash
# Patch Langflow SSRF into the installed ADK compose, then start Developer Edition.
# Re-run after `pip install -U ibm-watsonx-orchestrate` — the stock compose is restored.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python scripts/patch_langflow_ssrf.py
exec orchestrate server start -e .env --with-langflow --compose-file .adk/docker-compose.yml "$@"
