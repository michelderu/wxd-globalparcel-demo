#!/usr/bin/env bash
# Thin wrapper — full 01–04 resume lives at repo root.
exec "$(cd "$(dirname "$0")/../.." && pwd)/scripts/start_services.sh" "$@"
