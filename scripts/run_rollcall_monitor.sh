#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI_ROOT="$REPO_ROOT/xmu-rollcall-cli"
LOG_DIR="${XMU_ROLLCALL_LOG_DIR:-$REPO_ROOT/.runtime}"
LOG_FILE="$LOG_DIR/xmu-rollcall-monitor.log"
PID_FILE="$LOG_DIR/xmu-rollcall-monitor.pid"

mkdir -p "$LOG_DIR"

export XMU_ROLLCALL_HERMES_REPO="${XMU_ROLLCALL_HERMES_REPO:-$HOME/.hermes/hermes-agent}"
export XMU_ROLLCALL_NOTIFY_TARGET="${XMU_ROLLCALL_NOTIFY_TARGET:-qqbot:31C7A9C6D26F148A5067E9A93B86EDA9}"

cd "$CLI_ROOT"

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "Monitor already running with PID $old_pid"
    exit 0
  fi
fi

if ! python -c 'import xmu_rollcall' >/dev/null 2>&1; then
  python -m pip install -e .
fi

nohup python -u -m xmu_rollcall.cli start >>"$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "Started xmu-rollcall monitor in background"
echo "PID: $(cat "$PID_FILE")"
echo "Log: $LOG_FILE"
