#!/usr/bin/env bash
# Workshop-root wrapper. Session 01 lives in 01-streamhouse/.
exec "$(cd "$(dirname "$0")/.." && pwd)/01-streamhouse/scripts/run-streamhouse.sh"
